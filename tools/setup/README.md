# Linux dev setup (Ubuntu 26.04)

## Root part, once
```
sudo bash tools/setup/linux-sudo.sh
```
Idempotent. apt: picocom, python3-serial/-pil/-numpy/-bleak (host side of firmware/tools), playwright's missing
fonts + xvfb, imagemagick, libosmesa6, f3d; snap: freecad; udev: `udev/60-esp32s3.rules` (Espressif 303a: tty +
raw USB for OpenOCD, uaccess, ModemManager off) and PlatformIO's `99-platformio-udev.rules`; `usermod -aG dialout,plugdev`.

After it: log out and in (groups), replug the board. Check: `ls -l /dev/ttyACM0`, `id | grep dialout`.

## User level (already installed)
| What | Where | Use |
|---|---|---|
| PlatformIO **6.1.19 (pinned)** + pioarduino 55.03.311 | `~/.platformio/penv` (Python 3.14), `pio` linked in `~/.local/bin` | scripts call `~/.platformio/penv/bin/pio`. The platform's penv setup may upgrade the core to 6.2.x, which breaks lcd316 (`No module named 'SCons.Tool.FortranCommon'`): re-pin with `uv pip install --python ~/.platformio/penv/bin/python pioarduino==6.1.19` |
| esptool 5.3 | penv | `~/.platformio/penv/bin/python -m esptool` |
| OpenOCD-esp32 0.12.0-20260424, xtensa gdb 17.1 | `~/.platformio/packages/tool-openocd-esp32`, `tool-xtensa-esp-elf-gdb` | below |
| uv | pipx (`~/.local/bin/uv`) | |
| Node 24.22.3 (nvm default) | `~/.nvm` | `sim/`: `npm ci` done |
| Playwright 1.61.1 chromium-1228 | `~/.cache/ms-playwright` | run-sim skill |
| build123d 0.13, OCP 8.0.1, pyvista/VTK 9.7, trimesh | `~/.venvs/cad` (Python 3.14) | `source ~/.venvs/cad/bin/activate`; add packages with `uv pip install --python ~/.venvs/cad/bin/python X` |

## lcd316: one-time packages dir (not done yet)
The first lcd316 build copies `~/.platformio/packages` to `~/.platformio/packages-lcd316` and recompiles the Arduino
libs (~7 min, also makes `~/.platformio/penv/.espidf-5.5.5` for `tools/bootloader-dc.sh`). `tools/flash.sh --env lcd316`
does it on first use; to do it without a board:
```
cd firmware && (ENV=lcd316; . tools/pkgdir.sh; pio run -e lcd316)
```
Note: a `pio run -e amoled191` in `firmware/` wipes `.pio/build/lcd316` (full LCD rebuild next time).

## Serial / debug (ESP32-S3 USB Serial/JTAG)
- Commands: `firmware/tools/device.py CMD`. Monitor: `pio device monitor -d firmware` (DTR/RTS off per platformio.ini) or `picocom -b 115200 /dev/ttyACM0`. One client at a time.
- JTAG: `~/.platformio/packages/tool-openocd-esp32/bin/openocd -s ~/.platformio/packages/tool-openocd-esp32/share/openocd/scripts -f board/esp32s3-builtin.cfg`,
  then `~/.platformio/packages/tool-xtensa-esp-elf-gdb/bin/xtensa-esp32s3-elf-gdb firmware/.pio/build/amoled191/firmware.elf -ex 'target extended-remote :3333'`.
  Or `debug_tool = esp-builtin` + `pio debug -e amoled191`.

## Sim
Port 5190 (vite strictPort) may be taken by another local server: check with `ss -ltnp | grep 5190` before "reusing" it.
Without root, chromium headless already renders (fonts fall back).

## 3D preview (headless)
```
~/.venvs/cad/bin/python tools/setup/cad_preview.py part.step out.png [--view iso|top|front|right|all]
~/.venvs/cad/bin/python tools/setup/cad_preview.py --smoke /tmp/cad-smoke   # box -> STEP/STL/3MF + PNG
```
GLX with a display, EGL (NVIDIA) without, OSMesa as fallback. Viewing: `f3d part.step`, `freecad` (snap).
