# Linux dev setup (Kubuntu / Ubuntu 26.04, amd64)

## Install everything

From this checkout:

```
sudo bash tools/setup/linux-sudo.sh
```

Safe to rerun after an interruption. Requires internet and several GB of free space for CAD, Chromium and the ESP32
toolchains. System packages, FreeCAD and USB permissions run as root. Python environments, npm, Chromium and OrcaSlicer
run as the invoking user, so no root-owned files are created in the checkout or home directory.

- apt: native compiler/build tools, Node 22 + npm, Python venv support, picocom, pyserial/Pillow/numpy/bleak for host
  scripts, ImageMagick, VTK/OpenGL libraries, F3D, Xvfb + xauth, OrcaSlicer's FUSE/GTK/WebKit libraries.
- FreeCAD: official snap. Playwright: Chromium and its exact version's system dependencies.
- CAD: `~/.venvs/cad`, direct versions pinned in `requirements-cad.txt`.
- Firmware: pioarduino core 6.1.19, esptool 5.3, both boards' packages from `firmware/platformio.ini`, OpenOCD and Xtensa
  GDB. Separate LCD packages directory. Downloads dependencies without building firmware or flashing a board.
- OrcaSlicer 2.5.0: official AppImage in `~/.local/opt/orcaslicer`, `~/.local/bin/orca-slicer`, KDE application menu entry.
  Matches the branch's slicing review. SHA256 checked against the
  [official release asset metadata](https://api.github.com/repos/OrcaSlicer/OrcaSlicer/releases/tags/v2.5.0).
- USB: vendored Espressif/PlatformIO udev rules (tty + raw USB, uaccess, ModemManager off); groups `dialout,plugdev`.

Finishes by checking Python imports, debug CLIs, simulator build, Chromium canvas rendering, CAD STEP/STL/3MF export
and PNG preview, and OrcaSlicer CLI startup. Smoke outputs are retained in the printed `/tmp/watches-setup-*` directory.

After it: log out and in (groups), replug the board. Check: `ls -l /dev/ttyACM0`, `id | grep dialout`.

To rerun just user installs or checks after the system setup:

```
bash tools/setup/linux-user.sh --install-only
bash tools/setup/linux-user.sh --check
```

Without a flag, `linux-user.sh` runs both. It uses an existing nvm default when available; otherwise the apt Node.
Add `~/.local/bin` to your shell's PATH if it is not already there. It does not change your nvm default or shell files.

## Tool locations
| What | Where | Use |
|---|---|---|
| PlatformIO **6.1.19 (pinned)** + pioarduino 55.03.311 | `~/.platformio/penv` (Python 3.14), `pio` linked in `~/.local/bin` | scripts call `~/.platformio/penv/bin/pio`. The platform's penv setup may upgrade the core to 6.2.x, which breaks lcd316 (`No module named 'SCons.Tool.FortranCommon'`). Installer checks the running core and re-pins when needed. |
| esptool 5.3 | penv | `~/.platformio/penv/bin/python -m esptool` |
| OpenOCD-esp32 0.12.0-20260424, xtensa gdb 17.1 | `~/.platformio/packages/tool-openocd-esp32`, `tool-xtensa-esp-elf-gdb` | below |
| uv | `~/.local/bin/uv` | Existing install retained; bootstrapped in `~/.venvs/watch-setup` if absent. |
| Node 22+ | apt, or existing nvm default | `sim/`: `npm ci` from lockfile |
| Playwright 1.61.1 chromium-1228 | `~/.cache/ms-playwright` | run-sim skill |
| build123d 0.13, cadquery-ocp-novtk 8.0.1.1.0, pyvista 0.49.2 / VTK 9.7.2, trimesh, svgelements, OpenCV, numpy, Pillow | `~/.venvs/cad` (Python 3.14) | `source ~/.venvs/cad/bin/activate` |
| OrcaSlicer 2.5.0 | `~/.local/bin/orca-slicer` | GUI: `orca-slicer`; CLI: `xvfb-run -a orca-slicer --help` |

## lcd316: first build

The installer pre-populates `~/.platformio/packages-lcd316`. The first lcd316 build recompiles the Arduino libs
(~7 min, also makes `~/.platformio/penv/.espidf-5.5.5` for `tools/bootloader-dc.sh`). To do it without a board:
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
