#!/usr/bin/env bash
# Build + flash the app. Board attached to WSL/Linux (/dev/ttyACM*) -> pio upload; else -> flash-win.sh
# (board on the Windows side, via python.exe esptool). NVS (tuned params) is preserved either way.
# Usage: tools/flash.sh [--env NAME] [args for pio upload / flash-win.sh]   (env: platformio.ini, default amoled191)
# $LW_PORT picks the board as in device.py: COMx = Windows side, else a Linux tty (e.g. /dev/ttyACM1).
set -euo pipefail
cd "$(dirname "$0")/.."
ENV=amoled191
if [ "${1:-}" = "--env" ]; then ENV="$2"; shift 2; fi
case "${LW_PORT:-}" in
    COM*) exec tools/flash-win.sh --env "$ENV" "$@" "$LW_PORT" ;;
    ?*) exec ~/.platformio/penv/bin/pio run -s -e "$ENV" -t upload --upload-port "$LW_PORT" "$@" ;;
esac
if ls /dev/ttyACM* >/dev/null 2>&1; then
    ~/.platformio/penv/bin/pio run -s -e "$ENV" -t upload --upload-port "$(ls /dev/ttyACM* | head -1)" "$@"
else
    exec tools/flash-win.sh --env "$ENV" "$@"
fi
