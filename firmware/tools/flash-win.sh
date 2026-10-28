#!/usr/bin/env bash
# Flash from WSL through Windows' esptool: the board stays on the Windows side (Web Serial in the
# browser keeps working), no usbipd attach/detach. Needs once: python.exe -m pip install esptool
# Usage: tools/flash-win.sh [--full] [--env NAME] [--res N] [COMx]   (port: COMx, else $LW_PORT if COMx, else the first Espressif port)
# Default: flash the application only, preserving NVS. --full flashes the factory image (bootloader + partition
# table too: needed once on a board that came with other firmware). --env: platformio.ini env, else $LW_BOARD,
# else amoled191. --res: lcd316 canvas rows (RENDER_H), else $LW_RES, else 320 = native.
set -euo pipefail
cd "$(dirname "$0")/.."
FULL=0
PORT=""
ENV="${LW_BOARD:-amoled191}"; RES="${LW_RES:-}"
while [ $# -gt 0 ]; do
    case "$1" in
        --full) FULL=1 ;;
        --env) ENV="$2"; shift ;;
        --res) RES="$2"; shift ;;
        COM[0-9]*) PORT="$1" ;;
        *) echo "usage: tools/flash-win.sh [--full] [--env NAME] [--res N] [COMx]"; exit 2 ;;
    esac; shift
done
case "${LW_PORT:-}" in COM*) PORT="${PORT:-$LW_PORT}" ;; esac
PORT="${PORT:-$(powershell.exe -NoProfile -c "(Get-PnpDevice -Class Ports -PresentOnly | Where-Object InstanceId -like 'USB\VID_303A*' | Select-Object -First 1).FriendlyName -replace '.*\((COM\d+)\).*','\$1'" | tr -d '\r')}"
[ -n "$PORT" ] || { echo "no Espressif COM port found"; exit 1; }
[ "$ENV" = lcd316 ] || RES=""
. tools/pkgdir.sh
PLATFORMIO_BUILD_FLAGS="${PLATFORMIO_BUILD_FLAGS:-}${RES:+ -DRENDER_H=$RES}" ~/.platformio/penv/bin/pio run -s -e "$ENV"
if [ "$FULL" -eq 1 ]; then
    OFFSET=0x0
    IMAGE=.pio/build/$ENV/firmware.factory.bin
else
    OFFSET=0x10000
    IMAGE=.pio/build/$ENV/firmware.bin
fi
python.exe -m esptool --chip esp32s3 --port "$PORT" --baud 921600 write-flash "$OFFSET" "$(wslpath -w "$IMAGE")"
