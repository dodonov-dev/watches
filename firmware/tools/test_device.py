#!/usr/bin/env python3
"""device.serial_talk's drop / re-open handling on a mocked port (no board): python3 firmware/tools/test_device.py"""
import os, sys, termios, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
import device

class Fake:
    """A port whose methods fail on cue. fail: {method: exception} for this instance; reads: bytes or exceptions, in
    order. Every instance (the re-opened ones too) logs its writes to Fake.sent."""
    sent = []; reads = []; fail_next = []   # fail_next: per new instance (re-opens), its `fail` dict
    def __init__(self, *a, **k):
        self.port = None; self.dtr = self.rts = None
        self.fail = Fake.fail_next.pop(0) if Fake.fail_next else {}
    def _maybe(self, name):
        e = self.fail.pop(name, None)
        if e: raise e
    def open(self): self._maybe('open')
    def close(self): pass
    def reset_input_buffer(self): self._maybe('reset_input_buffer')
    @property
    def in_waiting(self): self._maybe('in_waiting'); return 0
    def write(self, b): Fake.sent.append(b); self._maybe('write'); return len(b)
    def flush(self): self._maybe('flush')
    def read(self, n):
        if not Fake.reads: time.sleep(0.01); return b''
        x = Fake.reads.pop(0)
        if isinstance(x, Exception): raise x
        return x

serial.Serial = Fake
GONE = serial.SerialException('ClearCommError failed')
REPLY = [b'r\r\nESP-ROM:esp32s3\r\n', GONE, b'liquid-watch | x | reset sw\r\n', b'ready. ? for commands\r\n']

def run(first_fail, reads, reopen=2, cmd='r', end='ready.'):
    Fake.sent = []; Fake.reads = list(reads); Fake.fail_next = [first_fail]
    s = Fake(); Fake.fail_next = []
    return device.serial_talk(s, cmd, end, 3, reopen, 'COM7')

def case(name, fn):
    try: ok, why = fn()
    except Exception as e: ok, why = False, f'raised {e!r}'
    print(f'{"PASS" if ok else "FAIL"}  {name}{"" if ok else ": " + why}')
    return ok

def delivered_then_flush_fails():
    out, s = run({'flush': serial.SerialException('FlushFileBuffers failed')}, REPLY[2:])
    return Fake.sent == [b'r\n'] and 'ready.' in out and device.PORT_BACK in out, f'sent {Fake.sent}, reply {out!r}'
def write_raises():
    out, s = run({'write': serial.SerialException('WriteFile failed')}, REPLY[2:])
    return Fake.sent == [b'r\n'] and 'ready.' in out, f'sent {Fake.sent}'
def stale_handle_before_send():
    out, s = run({'in_waiting': GONE}, REPLY)
    return Fake.sent == [b'r\n'] and out.count(device.PORT_LOST) == 2 and 'ready.' in out, f'sent {Fake.sent}, reply {out!r}'
def termios_on_reset():
    out, s = run({'reset_input_buffer': termios.error(5, 'Input/output error')}, REPLY)
    return Fake.sent == [b'r\n'] and 'ready.' in out, f'sent {Fake.sent}'
def termios_on_flush():
    out, s = run({'flush': termios.error(5, 'Input/output error')}, REPLY[2:])
    return Fake.sent == [b'r\n'] and 'ready.' in out, f'sent {Fake.sent}'
def drop_mid_reply():
    out, s = run({}, REPLY)
    return Fake.sent == [b'r\n'] and out.index(device.PORT_LOST) < out.index('liquid-watch') and s is not None, repr(out)
def end_newline_not_fooled_by_markers():
    out, s = run({'in_waiting': GONE}, [b'v\r\n', b'board lcd316@320\r\n'], cmd='v', end='\n')
    return 'board lcd316' in out, repr(out)
def no_reopen_raises():
    try: run({'flush': termios.error(5, 'Input/output error')}, [], reopen=0)
    except termios.error: return True, ''
    return False, 'did not raise'

CASES = [('delivered write, flush fails: sent once, reply read on', delivered_then_flush_fails),
         ('write raises: not resent', write_raises),
         ('stale handle before sending: re-open, sent once', stale_handle_before_send),
         ('termios.error on reset_input_buffer (Linux)', termios_on_reset),
         ('termios.error on flush (Linux): not resent', termios_on_flush),
         ('drop mid-reply: re-opened, reply continues', drop_mid_reply),
         ("end '\\n' waits for the board's line, not a PORT_* line", end_newline_not_fooled_by_markers),
         ('reopen 0: a drop still raises', no_reopen_raises)]
sys.exit(0 if all([case(n, f) for n, f in CASES]) else 1)
