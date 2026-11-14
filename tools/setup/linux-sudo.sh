#!/usr/bin/env bash
# Root-only setup for Liquid Watch work on Ubuntu / Debian (written for Ubuntu 26.04). Idempotent: safe to re-run.
#   sudo bash tools/setup/linux-sudo.sh
# Everything else (PlatformIO, node, playwright, CAD venv) is user level: tools/setup/README.md.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo: sudo bash $0" >&2; exit 1; }
USR="${SUDO_USER:-}"
[ -n "$USR" ] && [ "$USR" != root ] || { echo "run via sudo from your own user (SUDO_USER is the one added to groups)" >&2; exit 1; }
. /etc/os-release
case " ${ID:-} ${ID_LIKE:-} " in *" ubuntu "*|*" debian "*) ;; *) echo "unsupported distro: ${ID:-?} (apt-based only)" >&2; exit 1 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"

PKGS=(
    # board: serial monitor; host Python for firmware/tools (device.py, bench.py: pyserial; sprite tools: PIL, numpy;
    # ble-session.py: bleak); libusb for esptool / OpenOCD (PlatformIO brings esptool, OpenOCD and xtensa gdb itself)
    picocom python3-serial python3-pil python3-numpy python3-bleak libusb-1.0-0
    # sim: the system libs/fonts playwright's chromium reports missing (`npx playwright install-deps --dry-run chromium`);
    # ImageMagick for the digit-sprites skill (identify / convert)
    fonts-freefont-ttf fonts-ipafont-gothic fonts-tlwg-loma-otf fonts-unifont fonts-wqy-zenhei xfonts-cyrillic xvfb
    imagemagick
    # 3D: OSMesa, the last-resort headless GL for VTK / pyvista previews when neither X nor EGL (NVIDIA) is there
    libosmesa6
    # viewing: f3d (STL / STEP / 3MF viewer, OCCT built in)
    f3d
)
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends "${PKGS[@]}"

# viewing: FreeCAD (not in Ubuntu 26.04's apt; the snap is published by the FreeCAD project)
command -v snap >/dev/null || apt-get install -y snapd
snap list freecad >/dev/null 2>&1 || snap install freecad

# board / debug: udev rules. 60-esp32s3: Espressif VID 303a (USB Serial/JTAG tty + raw USB for OpenOCD), ModemManager
# off it. 99-platformio: PlatformIO's stock rules (vendored copy of platformio/assets/system/99-platformio-udev.rules).
install -m 0644 "$HERE/udev/60-esp32s3.rules" /etc/udev/rules.d/60-esp32s3.rules
install -m 0644 "$HERE/udev/99-platformio-udev.rules" /etc/udev/rules.d/99-platformio-udev.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb --subsystem-match=tty

# board: serial (dialout) and raw USB (plugdev) without the seat ACL, e.g. over ssh. Effective after log out / in.
usermod -aG dialout,plugdev "$USR"

echo "done. Log out and back in (groups: dialout, plugdev), then replug the board."
