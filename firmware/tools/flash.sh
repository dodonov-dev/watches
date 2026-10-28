#!/usr/bin/env bash
# Build + flash the app. Board attached to WSL/Linux (/dev/ttyACM*) -> pio upload; else -> flash-win.sh
# (board on the Windows side, via python.exe esptool). NVS (tuned params) is preserved either way.
# Usage: tools/flash.sh [--env NAME] [--res N] [args for pio upload / flash-win.sh]
# Board: --env NAME, else $LW_BOARD, else amoled191 (platformio.ini env). lcd316 renders N canvas rows (RENDER_H,
# spec/layout.h): --res N, else $LW_RES, else 320 = native. $LW_PORT picks the board as in device.py: COMx =
# Windows side, else a Linux tty (e.g. /dev/ttyACM1).
set -euo pipefail
cd "$(dirname "$0")/.."
ENV="${LW_BOARD:-amoled191}"; RES="${LW_RES:-}"
while [ $# -gt 0 ]; do
    case "$1" in
        --env) ENV="$2"; shift 2 ;;
        --res) RES="$2"; shift 2 ;;
        *) break ;;
    esac
done
[ "$ENV" = lcd316 ] || RES=""
. tools/pkgdir.sh
win() { exec env LW_RES="$RES" tools/flash-win.sh --env "$ENV" "$@"; }
up() { PLATFORMIO_BUILD_FLAGS="${PLATFORMIO_BUILD_FLAGS:-}${RES:+ -DRENDER_H=$RES}" ~/.platformio/penv/bin/pio run -s -e "$ENV" -t upload --upload-port "$@"; }
case "${LW_PORT:-}" in
    COM*) win "$@" "$LW_PORT" ;;
    ?*) up "$LW_PORT" "$@"; exit ;;
esac
if ls /dev/ttyACM* >/dev/null 2>&1; then
    up "$(ls /dev/ttyACM* | head -1)" "$@"
else
    win "$@"
fi
