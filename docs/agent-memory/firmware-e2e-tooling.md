---
name: firmware-e2e-tooling
description: How to measure fps / parity on the real board from WSL; serial open/close resets the ESP32-S3 unless DTR=RTS=1 on open and RTS dropped before DTR on close; every p write is NVS-autosaved after 2 s
metadata:
  node_type: memory
  type: project
  originSessionId: 5e4b94a5-9ef3-487e-978f-84b859904c88
  modified: 2026-10-02T14:04:41.631Z
---

Firmware e2e loop (from `firmware/`): `tools/e2e.sh [--stages] [--no-ble]` = build → flash → `bench.py`
(pinned scene, median fps + per-stage ms) → `compare-device.py` (parity vs sim). `tools/device.py CMD` for
one-offs. Board may be on Windows (COM6) or usbipd-attached (`/dev/ttyACM0`); device.py handles both.
Baseline 2026-08-27 @ f0a3de7: 20.6 fps, digits = 20.7 of 44 ms.

**Why:** opening the port with DTR/RTS explicitly cleared hit the ESP32-S3 USB-JTAG reset combo (DTR0/RTS1)
intermittently (5/5 in one session, 0/2 later) and zeroed the fps window; dtr=rts=True never reset. Boot banner
prints `reset <reason>`; BLE disconnect verified NOT to reboot (tools/ble-session.py = bleak under python.exe, the Windows radio; PowerShell 5.1 WinRT can't write IBuffers). fps also swings 19–25 with fill level/tilt, so unpinned numbers are noise.
Closing the port also reset the board (Windows drops DTR with RTS still high) until 2026-09-18: device.py now
drops RTS then DTR before close, and dwells 2.5 s on close after any `p` write because the firmware autosaves
every write to NVS 2 s later (bench.py's `inputGain 0` pin once got persisted this way and killed tilt).
The browser's Web Serial still resets on close.
**How to apply:** always go through device.py / bench.py; never `p!` in scripts (overwrites NVS params
2 s later); compare only pinned-scene numbers; parity bar = mismatches not growing, 0 px > 12/255.
Since 2026-09-25 (b126af0): a Params schema change resets NVS to presets/1.json on flash, so pin a preset
across it (`--preset presets/x.json`); `--ref <commit>` does a same-params A/B (temp worktree, no parity);
`--runs 3` for random-position stages like fizz (±0.5 ms per run); `--live-imu` for moving-light cases;
bench.py exits 3 when the IMU reads exactly 0 even after its reboot retry (dead IMU after flash = not
comparable); `check_render_frames.py --list-diffs` lists differing scenes and whether all had fizz on.
The `>12/255` parity count swings ±50 px with the liquid position (meniscus crescents): not a strict gate.
Since 2026-10-02: `g <along> <across>` overrides the IMU tilt over serial and `tools/tilt.py` scripts poses /
swings with one `f` line per 2 s (motion cases without hands; `f` now splits physics / fizz step, push, rest and
fizz counts). See [[fizz-fps-collapse]].
Residue-near-a-skewed-edge stress (2026-10-02): `device.py w6` (minutes sweep: drains → fresh deposits; persists in
NVS — always `w0` after) + `tilt.py --hold 40 '-0.7,0.7'` (vertical held sideways); read the `m` core median after 5 s.
The pinned bench never deposits residue (no motion): add `traceFilm` to the pinned preset to get residue at all.
Refactor identity: `check_render_frames.py --reference <pre-change copy> --tolerance 0` (rebuild the copy by
reverting just the edit; a sloppy reconstruction gave a false diff once). See [[imminent-residue]].
