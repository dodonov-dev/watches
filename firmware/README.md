# Firmware

Build + flash from `firmware/`. App only by default: the board's saved params (NVS) stay.

```
tools/flash.sh [--env amoled191|lcd316] [--res TAG] [--tubes 2|3] [--full]
```

| Face | Command |
|---|---|
| AMOLED 1.91, 2 tubes (default) | `tools/flash.sh` |
| AMOLED, 3 tubes | `tools/flash.sh --tubes 3` |
| LCD 3.16, 2 tubes, 6 mm | `tools/flash.sh --env lcd316` |
| LCD, 2 tubes, 8 mm | `tools/flash.sh --env lcd316 --res 320w8-8` |
| LCD, 3 tubes, 8 mm | `tools/flash.sh --env lcd316 --res 320w8-8-8 --tubes 3` |
| LCD, 3 tubes, 10 / 8 / 6 mm | `tools/flash.sh --env lcd316 --res 320w10-8-6 --tubes 3` |
| LCD, wide tubes (face scaled as on the AMOLED, ≈ 8.8 mm) | `tools/flash.sh --env lcd316 --res 320f` |
| LCD, fewer rows (faster, upscaled) | `--res 288f` (rows 240 / 256 / 288 / 320) |

- Res tag = rows + tube widths: nothing (6 mm) / `f` (wide) / `fh` `fm` `fs` (those tubes wide) / `w` + mm per tube,
  3 to 10 or `f`. All forms: `tools/boardtag.py`.
- `--full`: bootloader + partition table too. Once on a new board, or when an lcd316 flash refuses the bootloader.
- Port: `LW_PORT=COM7` (Windows side) or `/dev/ttyACMx`; required with several boards attached.
  `LW_BOARD` / `LW_RES` / `LW_TUBES` work in place of the flags.
- "Access is denied" / port busy: disconnect the sim's serial in the browser first.
- What the board runs: `tools/device.py v` → `board lcd316@320w8-8-8+t3 …`.
- A flash across a Params change resets the board to `presets/1.json`: save `tools/device.py 'p?'` before it.
- IMU reads 0 after a flash (`tools/device.py s`: `along 0.000 across 0.000`): `tools/device.py r`.
- lcd316: never `pio run -t upload` (it writes Arduino's bootloader). See `bootloader-dc/README.md`.
- No reflash needed: tube positions and stacking (`tubeStack`, `tubeGap`), `tubeHeight`, every other param.
- Build → flash → bench → parity: `tools/e2e.sh`.
