#!/usr/bin/env python3
"""Serial transport to the Liquid Watch board, usable from WSL or Linux.

    from device import Device
    d = Device()                 # auto: /dev/ttyACM* if attached to Linux, else Windows COMx via python.exe
    d.talk('f')                  # -> 'fps 19.8  render 46.48 ms ...'
    d.talk('x', end='END', timeout=60, ok=lambda r: ...)   # ok: is this reply whole? (default: non-empty, `end` in it)
    d.set('inputGain', 0)        # volatile `p~` write (never autosaved); `p` on firmware without `p~`

CLI:  tools/device.py [--port P] CMD [CMD ...]     e.g. tools/device.py f s 'p?'

On WSL the board normally stays on the Windows side (Web Serial in the browser keeps working, see
flash-win.sh); we then run this very file under python.exe as a persistent bridge (--bridge) talking
a line protocol over its stdin/stdout. The port is opened with DTR/RTS low so the ESP32-S3 USB-JTAG
does not reset the board (both lines held high; pyserial's default clears DTR before RTS = reset). Port detection: $LW_PORT, /dev/ttyACM0 if present, else the first
Espressif (VID 303A) COM port on Windows.
"""
import argparse, glob, json, os, subprocess, sys, time

SENTINEL = '\x1e<<END>>\x1e'

def is_wsl():
    return os.path.exists('/proc/sys/fs/binfmt_misc/WSLInterop') or 'microsoft' in os.uname().release.lower()

def find_port():
    p = os.environ.get('LW_PORT')
    if p: return p
    acm = sorted(glob.glob('/dev/ttyACM*'))
    if acm: return acm[0]
    if is_wsl():
        ps = ("(Get-PnpDevice -Class Ports -PresentOnly | Where-Object InstanceId -like 'USB\\VID_303A*' "
              "| Select-Object -First 1).FriendlyName -replace '.*\\((COM\\d+)\\).*','$1'")
        out = subprocess.run(['powershell.exe', '-NoProfile', '-c', ps], capture_output=True, text=True).stdout.strip()
        if out.startswith('COM'): return out
    raise SystemExit('no board found: attach it (usbipd) or set LW_PORT=COMx')

def open_serial(port):
    import serial
    s = serial.Serial(None, 115200, timeout=0.1)
    s.port = port; s.dtr = True; s.rts = True       # both high = no reset on open (DTR0/RTS1 is the ESP32-S3 reset combo)
    for attempt in range(40):                       # Windows: a previous bridge may still hold the port for a few s
        try: s.open(); break
        except serial.SerialException as e:
            if 'denied' not in str(e).lower() or attempt == 39: raise
            time.sleep(0.25)
    time.sleep(0.1); s.reset_input_buffer()
    return s

def close_serial(s):
    # Closing the handle drops DTR while RTS stays high = the S3's reset combo (USB-serial-JTAG acts
    # only when exactly one line is asserted). Drop RTS first, then DTR, so the close changes nothing.
    try: s.rts = False; s.dtr = False
    except Exception: pass
    s.close()

def serial_talk(s, cmd, end, timeout):
    s.reset_input_buffer()
    s.write((cmd + '\n').encode()); s.flush()
    t0 = time.monotonic(); out = b''; endb = end.encode()
    echo = cmd.strip().encode() + b'\r\n'             # firmware echoes the command line first
    while time.monotonic() - t0 < timeout:
        c = s.read(65536); out += c
        body = out[len(echo):] if out.startswith(echo) else out
        k = body.find(endb) if endb else -1
        if k >= 0 and (endb.endswith(b'\n') or b'\n' in body[k:]): break   # the end marker's whole line
        if not endb and out and c == b'': break        # no terminator: stop at the first quiet gap
    return out.decode(errors='replace')

class Device:
    def __init__(self, port=None):
        self.port = port or find_port()
        self.windows = self.port.upper().startswith('COM')
        self._s = self._b = None
        self._wrote = False   # a `p` write happened: hold the session past the 2 s NVS autosave on close
        self._volatile = None # firmware takes `p~` writes (None = not asked yet)
        if self.windows:
            me = subprocess.run(['wslpath', '-w', os.path.abspath(__file__)], capture_output=True, text=True).stdout.strip()
            self._b = subprocess.Popen(['python.exe', me, '--bridge', self.port], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8')
        else:
            self._s = open_serial(self.port)

    def raw(self, cmd, end='\n', timeout=10):
        if self._s: return serial_talk(self._s, cmd, end, timeout)
        self._b.stdin.write(json.dumps([cmd, end, timeout]) + '\n'); self._b.stdin.flush()
        buf = []
        while True:
            line = self._b.stdout.readline()
            if not line: raise RuntimeError('bridge died')
            if line.rstrip('\n') == SENTINEL: break
            buf.append(line)
        return ''.join(buf)

    RETRY = 3   # the Windows bridge now and then returns a short or empty reply

    def talk(self, cmd, end='\n', timeout=10, ok=None):
        """Send one command, return the reply with the firmware's echo line stripped. A reply that is empty, misses
        `end` or fails ok(reply) is asked again (RETRY times in all; then returned as it is) - except for commands that
        are not idempotent (`r`, `i`) or silent by design (`l`, `h`, `c`: no reply, they always wait out `timeout`)."""
        if cmd.startswith('p') and not cmd.startswith('p~') and '=' in cmd: self._wrote = True
        if ok is None: ok = lambda r: r != '' and (end == '\n' or end in r)
        tries = 1 if cmd.strip()[:1] in ('r', 'i', 'l', 'h', 'c') else self.RETRY
        for i in range(tries):
            r = self._talk1(cmd, end, timeout)
            if ok(r): break
            if i + 1 < tries: print(f'device.py: {cmd[:20]!r}: short reply ({len(r)} chars), asking again', file=sys.stderr)
        return r

    def set(self, name, value):
        """Volatile param write (`p~name=value`: never reaches NVS); `p` on firmware without it. Returns the reply."""
        if self._volatile is not False:
            r = self.talk(f'p~{name}={value}')
            if self._volatile is None: self._volatile = not r.startswith('unknown param ~')
            if self._volatile: return r
            print('device.py: firmware without `p~`: pins go through `p` (autosaved)', file=sys.stderr)
        return self.talk(f'p{name}={value}')

    def _talk1(self, cmd, end, timeout):
        out = self.raw(cmd, end, timeout).replace('\r\n', '\n')
        lines = out.split('\n')
        for l in lines:                                   # boot banner in a reply = the board rebooted
            if l.startswith('liquid-watch |'):
                print(f'device.py: BOARD REBOOTED ({l.split("reset")[-1].strip() if "reset" in l else "old firmware"})', file=sys.stderr)
        if lines and lines[0].strip() == cmd.strip(): lines = lines[1:]
        return '\n'.join(lines).strip()

    def board(self):
        """(tag, canvas_w, canvas_h) the firmware renders, from `v` (`board lcd316@320 canvas 820x320 panel ...`);
        firmware older than `v` is the AMOLED build."""
        import re
        m = re.search(r'board (\S+) canvas (\d+)x(\d+)', self.talk('v'))
        return (m.group(1), int(m.group(2)), int(m.group(3))) if m else ('amoled191', 536, 240)

    def board_env(self):
        """os.environ plus LW_BOARD / LW_RES of the attached board, for the sim's node tools (spec/layout.ts)."""
        tag = self.board()[0]; b, _, res = tag.partition('@')
        return dict(os.environ, LW_BOARD=b, LW_RES=res)

    def close(self):
        if self._wrote: time.sleep(2.5); self._wrote = False
        if self._s: close_serial(self._s)
        if self._b:                                   # the Windows bridge can take > 5 s to release the port and exit
            self._b.stdin.close()
            try: self._b.wait(20)
            except subprocess.TimeoutExpired:
                print('device.py: bridge did not exit, killed', file=sys.stderr); self._b.kill(); self._b.wait()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()

def _bridge(port):
    s = open_serial(port)
    for line in sys.stdin:
        cmd, end, timeout = json.loads(line)
        out = serial_talk(s, cmd, end, timeout)
        sys.stdout.write(out if out.endswith('\n') or not out else out + '\n')
        sys.stdout.write(SENTINEL + '\n'); sys.stdout.flush()
    close_serial(s)

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--bridge':
        _bridge(sys.argv[2]); sys.exit(0)
    ap = argparse.ArgumentParser(); ap.add_argument('--port'); ap.add_argument('--end', default='\n')
    ap.add_argument('--timeout', type=float, default=10); ap.add_argument('cmd', nargs='+')
    a = ap.parse_args()
    with Device(a.port) as d:
        for c in a.cmd: print(d.talk(c, a.end, a.timeout))
