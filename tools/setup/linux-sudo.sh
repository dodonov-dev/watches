#!/usr/bin/env bash
# Complete setup for Liquid Watch work on Kubuntu / Ubuntu 26.04. Safe to re-run.
#   sudo bash tools/setup/linux-sudo.sh
# System packages run as root; Python / npm / downloads run as the invoking user.
set -euo pipefail
trap 'echo "Setup failed at line $LINENO. Fix the reported error and rerun this script." >&2' ERR
[ "$(id -u)" -eq 0 ] || { echo "run with sudo: sudo bash $0" >&2; exit 1; }
USR="${SUDO_USER:-}"
[ -n "$USR" ] && [ "$USR" != root ] || { echo "run via sudo from your own user (SUDO_USER is the one added to groups)" >&2; exit 1; }
. /etc/os-release
case " ${ID:-} ${ID_LIKE:-} " in *" ubuntu "*) ;; *) echo "unsupported distro: ${ID:-?} (Ubuntu / Kubuntu 26.04 required)" >&2; exit 1 ;; esac
[ "${VERSION_ID:-}" = 26.04 ] || { echo "This package list targets Ubuntu / Kubuntu 26.04." >&2; exit 1; }
[ "$(dpkg --print-architecture)" = amd64 ] || { echo "The pinned OrcaSlicer download targets amd64." >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
USER_HOME="$(getent passwd "$USR" | cut -d: -f6)"
[ -d "$USER_HOME" ] || { echo "Cannot find home directory for $USR" >&2; exit 1; }
as_user() {
    runuser -u "$USR" -- env -u PYTHONPATH -u VIRTUAL_ENV -u PYTHONHOME \
        HOME="$USER_HOME" USER="$USR" LOGNAME="$USR" \
        PATH="$USER_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/snap/bin" "$@"
}

PKGS=(
    # Bootstrapping, native C++ parity checks, and the custom ESP-IDF bootloader.
    ca-certificates curl git unzip xz-utils build-essential pkg-config cmake ninja-build
    python3 python3-venv nodejs npm
    # board: serial monitor; host Python for firmware/tools (device.py, bench.py: pyserial; sprite tools: PIL, numpy;
    # ble-session.py: bleak); libusb for esptool / OpenOCD (PlatformIO brings esptool, OpenOCD and xtensa gdb itself)
    picocom python3-serial python3-pil python3-numpy python3-bleak libusb-1.0-0
    # sim: the system libs/fonts playwright's chromium reports missing (`npx playwright install-deps --dry-run chromium`);
    # ImageMagick for the digit-sprites skill (identify / convert)
    fonts-freefont-ttf fonts-ipafont-gothic fonts-tlwg-loma-otf fonts-unifont fonts-wqy-zenhei xfonts-cyrillic xvfb
    imagemagick
    # 3D: OSMesa, the last-resort headless GL for VTK / pyvista previews when neither X nor EGL (NVIDIA) is there
    libosmesa6 libgl1 libegl1 libglib2.0-0t64
    # viewing: f3d (STL / STEP / 3MF viewer, OCCT built in)
    f3d
    # OrcaSlicer 2.5.0's official Ubuntu 24.04 AppImage on this 26.04 host.
    libfuse2t64 libgtk-3-0t64 libwebkit2gtk-4.1-0 libsecret-1-0
    # xvfb-run needs xauth even with --no-install-recommends.
    xauth
)
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends "${PKGS[@]}"

# viewing: FreeCAD (not in Ubuntu 26.04's apt; the snap is published by the FreeCAD project)
command -v snap >/dev/null || apt-get install -y snapd
if ! snap list freecad >/dev/null 2>&1; then
    snap install freecad
fi

# board / debug: udev rules. 60-esp32s3: Espressif VID 303a (USB Serial/JTAG tty + raw USB for OpenOCD), ModemManager
# off it. 99-platformio: PlatformIO's stock rules (vendored copy of platformio/assets/system/99-platformio-udev.rules).
install -m 0644 "$HERE/udev/60-esp32s3.rules" /etc/udev/rules.d/60-esp32s3.rules
install -m 0644 "$HERE/udev/99-platformio-udev.rules" /etc/udev/rules.d/99-platformio-udev.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb --subsystem-match=tty

# board: serial (dialout) and raw USB (plugdev) without the seat ACL, e.g. over ssh. Effective after log out / in.
groupadd -f plugdev
usermod -aG dialout,plugdev "$USR"

cd "$REPO"
as_user bash "$HERE/linux-user.sh" --install-only

# Use the exact locked Playwright version's system dependency list. Node modules
# were installed as the user; only apt inside this command needs root.
/usr/bin/node "$REPO/sim/node_modules/playwright/cli.js" install-deps chromium
as_user bash "$HERE/linux-user.sh" --check

echo "Done. Log out and back in (groups: dialout, plugdev), then replug the board."
