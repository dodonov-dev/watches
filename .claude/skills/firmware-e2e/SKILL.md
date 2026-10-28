---
name: firmware-e2e
description: Measure fps / stage costs and check sim parity on the real Liquid Watch board (build → flash → bench → compare). Use for any firmware perf step, before/after numbers, "does it still match the sim", or when a reboot/crash needs a reset reason.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Firmware e2e (all commands from `firmware/`)

## The one-liner
```bash
tools/e2e.sh --label "hand-off 1 step 2"            # build → flash → pinned bench → parity, appended to .compare/e2e.log
tools/e2e.sh --stages                                # + per-stage cost table (digits, ticks, fizz, glow, …), ~2 min
tools/e2e.sh --stages fizz,digits --quick --no-parity   # only those stages, half the samples, no sim compare: ~30 s after the flash
tools/e2e.sh --no-flash                              # measure what is already flashed
tools/e2e.sh --no-ble                                # -DNO_BLE build (baseline: BLE costs ~0 ms)
tools/e2e.sh --preset ../presets/cola.json --runs 3  # pinned preset, median of 3 runs (+ spread)
tools/e2e.sh --ref HEAD~1 --preset ../presets/cola.json --runs 3 --stage fizz=0
                                                     # A/B: flash+bench HEAD~1 (temp worktree, no parity), then this tree
LW_PORT=COM11 tools/e2e.sh --env lcd316              # ESP32-S3-LCD-3.16 board (default env: amoled191); LW_PORT picks the board when both are attached
LW_PORT=COM11 tools/e2e.sh --env lcd316 --res 240    # LCD canvas 615x240 upscaled to 820x320 (RENDER_H 240/256/288/320; default 320 = native)
tools/e2e.sh --env lcd316 --define STRIPS_INTERNAL=1 # any -D for the build, also put in the label
```
Board selection everywhere (flash.sh, flash-win.sh, e2e.sh): `--env` / `--res`, else `$LW_BOARD` / `$LW_RES`, else
amoled191. `export LW_BOARD=lcd316 LW_PORT=COM11` once per shell makes every tool target the LCD. The board says what it
runs: `tools/device.py v` → `board lcd316@320 canvas 820x320 panel 820x320` (old firmware: `error unknown command`);
compare-device.py renders the sim at that canvas by itself (`LAYOUT` line of the `x` dump).
Host parity without the board, every preset, any canvas: `python3 tools/check_board_render.py --res 320` (lcd316;
`--board amoled191` too). 22 presets are beyond 12/255 on a few px on the AMOLED as well (pre-existing, KAIZEN).
Env lcd316 builds with recompiled Arduino libs (64 KB data cache, platformio.ini `custom_sdkconfig`) from its own
packages dir `~/.platformio/packages-lcd316`: flash.sh / flash-win.sh set `PLATFORMIO_PACKAGES_DIR` (tools/pkgdir.sh;
first use copies ~/.platformio/packages and recompiles the libs, ~7 min); a bare `pio run -e lcd316` is refused
(tools/pio_pkgdir.py) — in the shared dir it would replace the AMOLED's stock libs.
First flash of a board that came with other firmware: `tools/flash-win.sh --full --env lcd316 COMx` (bootloader + partitions).
e2e.sh passes `--preset FILE`, `--live-imu`, `--runs N`, `--stage name=v` through to bench.py; the log header
names the preset. `--ref COMMIT` builds and flashes a temporary `git worktree` of COMMIT under /tmp with the same
flags, benches it with the same preset/runs/stages (label `<label> ref <sha>`, parity skipped: the sim is not that
commit's), removes the worktree (also on failure) and then runs the current tree. `--bare` implies `--allow-dead-imu`.
Exit 3 = dead IMU (below).
Pass = fps not lower than the previous log entry AND `mismatched pixels` not higher, `>12/255 off: 0`.
Baseline @ f0a3de7: **20.6 fps, render 44.4 ms**, digits 20.7 ms of it; parity ~200 px ≤1 LSB.

## Pieces
- `tools/device.py CMD…` — one-off serial (`f` fps, `s` status, `p?` params, `pname=v`, `t HH:MM`, `d0` freeze, `r` reboot).
  `f` also reports `phys N steps x (tube + fizz ms per step, max)`, `push`, `rest` and per tube `fizz live (foam, slots)`:
  fps = 1000 / (render + push + rest + steps x step cost), steps = frame / 20 ms capped at 5.
- `tools/tilt.py [--hold S] POSE…` — poses without touching the board, via the firmware's `g <along> <across>` tilt override
  (`g` alone = back to the IMU; not persisted). `-1,0` = vertical watch upright, `0,0` = face up, `a1,c1>a2,c2@T` = swing with
  period T. One compact `f` line per 2 s. `tools/tilt.py --hold 60 '-1,0>0.6,0@3'` = worst case for spring fizz (pool at its `fizzCount` share).
  Auto-detects `/dev/ttyACM*` (usbipd-attached) or Windows COMx. Prints `BOARD REBOOTED (<reason>)` if a
  boot banner shows up — reasons: poweron/sw/panic/task-wdt/brownout/usb.
- `tools/bench.py [--stages [LIST]] [--stage name=v] [--quick] [--samples N] [--preset FILE] [--runs N] [--live-imu] [--allow-dead-imu] [--json]`
  - Time budget: every sample is one 2 s fps window (firmware `f`), 5 base + 3 per stage by default, so the full
    table is ~130 s. `--stages fizz,digits` measures only those; `--quick` = 3 base / 2 per stage, shorter settles
    (~half, ±0.1 ms noisier). Use `--quick` for direction, full samples + `--runs 3` for a number you will quote.
  — pinned scene (optional preset, `t 10:09:30`, `d0`, `inputGain=0`), median fps. Never compare unpinned `f`
  numbers: fps swings 19–25 with fill level/tilt. First output line = header: scene, preset, `tilt along X across Y
  gyro G`, IMU pinned/live, runs.
  - `--preset FILE`: every key of the JSON the board knows is written with `p<name>=<v>` (unknown keys and `v`
    are listed once and skipped) and restored afterwards like any other touched param.
  - `--runs N`: repeats base + stages N times; each line shows the median across runs and the min–max spread.
    Fizz positions are random (±0.5 ms per run on heavy presets): budgets under ~0.5 ms need `--runs 3`+.
  - `--live-imu`: inputGain is not pinned (moving light); `--live-imu --stage fizz=0` is the moving-fizz case.
  - Dead IMU: `s` reading along/across/gyro exactly 0 after the pins = IMU dead after flash. bench.py reboots
    (`r`), re-applies the pins and re-checks once; still dead → exit 3 (e2e.sh exits 3 too).
    `--allow-dead-imu` skips the reboot and marks the header `IMU dead` (for -DNO_IMU builds).
- `tools/check_render_frames.py --reference OLD_render.cpp [--no-fizz] [--list-diffs]` — host-only (no board):
  every scene of the current render.cpp vs a saved copy. `--list-diffs` lists the differing scenes per group and
  whether all had fizz on (a fizz-only change: all on, and `--no-fizz` byte-identical).
- `tools/compare-device.py` — device strips vs `sim/tools/render-ref.ts`; writes `.compare/{device,ref,diff}.png`.
  Read `diff.png` when mismatches grow (yellow = >12/255).
- `tools/flash.sh` / `flash-win.sh` — app-only flash, NVS-tuned params survive; the clock resets to the last saved sim time (NVS, saved on `T` + each minute), else 10:09:30.
- `python.exe "$(wslpath -w tools/ble-session.py)" s f` — same protocol over BLE from the Windows radio.

## Rules
- Pin a preset (`--preset`) whenever before/after straddle a Params change: a flash that changes
  `PARAMS_SCHEMA_CRC` resets NVS to presets/1.json, so the two sides would otherwise bench different looks.
  `--ref` across a schema change resets NVS twice (the tuned params are lost either way).
- A run whose header shows `IMU dead` (or all-zero tilt) is not comparable with one that has a live IMU.
- Scripts restore params from a `p?` snapshot; never send `p!` (it overwrites NVS 2 s later).
- Open serial with DTR=RTS=1 (device.py does) — clearing them can reset the ESP32-S3.
- One serial client at a time; the port is exclusive.
