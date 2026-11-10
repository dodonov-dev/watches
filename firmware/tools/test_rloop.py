#!/usr/bin/env python3
"""rloop.check_restart on mocked `r` transcripts (no board): python3 firmware/tools/test_rloop.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rloop import check_restart
from device import PORT_LOST, PORT_BACK, PORT_GONE

ROM = 'ESP-ROM:esp32s3-20210327\nrst:0xc (RTC_SW_CPU_RST),boot:0xb (SPI_FAST_FLASH_BOOT)\nSaved PC:0x4038ed06\n'
def banner(r): return f'liquid-watch | lcd316@320w10-8-6+t3 820x320 | cpu 240 MHz | psram 8192 KB | heap 111 KB | reset {r}\n'
CASES = {
    'clean sw restart': (ROM + banner('sw') + 'params: restored from nvs\nimu: ok\nready. ? for commands\n', True),
    # Astra's mock: a sw restart whose boot panics, then a task-wdt boot that reaches ready.
    'sw -> panic -> task-wdt -> ready': (ROM + banner('sw') + "Guru Meditation Error: Core  0 panic'ed (LoadProhibited)\n"
                                         'Rebooting...\n' + banner('task-wdt') + 'ready. ? for commands\n', False),
    'two banners, both sw': (ROM + banner('sw') + banner('sw') + 'ready. ? for commands\n', False),
    'reason not sw': (banner('task-wdt') + 'ready. ? for commands\n', False),
    'no ready': (ROM + banner('sw') + 'imu: ok\n', False),
    'ready before banner': ('ready. ? for commands\n' + ROM + banner('sw'), False),
    'second ROM reset line': (ROM + 'rst:0x10 (RTCWDT_RTC_RESET),boot:0xb\n' + banner('sw') + 'ready. ? for commands\n', False),
    'RTC WDT ROM reset': ('rst:0x10 (RTCWDT_RTC_RESET),boot:0xb\n' + banner('sw') + 'ready. ? for commands\n', False),
    'no banner': ('ready. ? for commands\n', False),
    # The LCD firmware's USB re-enumeration after a CPU-only reset: ROM + bootloader on the old port, then a drop that
    # device.py re-opens (PORT_LOST / PORT_BACK lines), then the app's banner.
    're-enumeration: dropped once, back': (ROM + f'\n{PORT_LOST}\n{PORT_BACK} 0.4 s]\n' + banner('sw') + 'ready. ? for commands\n', True),
    'dropped, not back in time': (ROM + f'\n{PORT_LOST}\n{PORT_GONE}\n', False),
    'dropped, no re-open line': (ROM + f'\n{PORT_LOST}\n' + banner('sw') + 'ready. ? for commands\n', False),
    'dropped twice': (ROM + f'\n{PORT_LOST}\n{PORT_BACK} 0.4 s]\n{PORT_LOST}\n{PORT_BACK} 0.3 s]\n' + banner('sw')
                      + 'ready. ? for commands\n', False),
    're-enumerated, banner lost (dead CDC)': (ROM + f'\n{PORT_LOST}\n{PORT_BACK} 0.4 s]\n', False),
    're-enumerated into a panic': (ROM + f'\n{PORT_LOST}\n{PORT_BACK} 0.4 s]\n' + banner('sw') + "Guru Meditation Error: Core  1 panic'ed\n"
                                   + 'ready. ? for commands\n', False),
}
bad = 0
for name, (out, want) in CASES.items():
    ok, why = check_restart(out)
    print(f'{"PASS" if ok == want else "FAIL"}  {name}: {ok} ({why})')
    bad += ok != want
sys.exit(1 if bad else 0)
