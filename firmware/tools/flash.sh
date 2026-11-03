#!/usr/bin/env bash
# Build + flash the app. Board attached to WSL/Linux (/dev/ttyACM*) -> pio upload; else -> flash-win.sh
# (board on the Windows side, via python.exe esptool). NVS (tuned params) is preserved either way.
# Usage: tools/flash.sh [--env NAME] [--res N] [args for pio upload / flash-win.sh]
# Board: --env NAME, else $LW_BOARD, else amoled191 (platformio.ini env). lcd316 res tag (tools/boardtag.py): --res
# TAG, else $LW_RES, else 320 = native rows, both tubes narrow; TAG = rows 240 / 256 / 288 / 320 + nothing (narrow) /
# f (both wide) / fh / fm (hours / minutes wide), e.g. 320f. Prints the board tag it builds (`v` reports the same).
# $LW_PORT picks the board as in device.py: COMx = Windows side, else a Linux tty (e.g. /dev/ttyACM1). With several
# boards attached it is required (refused otherwise): they share the USB IDs, nothing tells which one is "first".
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
FLAGS="${PLATFORMIO_BUILD_FLAGS:-}"
if [ "$ENV" = lcd316 ]; then FLAGS="$FLAGS $(python3 tools/boardtag.py flags "$RES")"; fi
. tools/pkgdir.sh
win() { exec env LW_RES="$RES" tools/flash-win.sh --env "$ENV" "$@"; }
up() {
    echo "flash.sh: building $(python3 tools/boardtag.py tag "$ENV" $FLAGS)"
    PLATFORMIO_BUILD_FLAGS="$FLAGS" ~/.platformio/penv/bin/pio run -s -e "$ENV" -t upload --upload-port "$@"
}
PORT="${LW_PORT:-$(python3 tools/device.py --find-port)}"   # device.py's choice: refuses none / several attached
case "$PORT" in
    COM*) win "$@" "$PORT" ;;
    *) up "$PORT" "$@" ;;
esac
