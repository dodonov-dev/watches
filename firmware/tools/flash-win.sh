#!/usr/bin/env bash
# Flash from WSL through Windows' esptool: the board stays on the Windows side (Web Serial in the
# browser keeps working), no usbipd attach/detach. Needs once: python.exe -m pip install esptool
# Usage: tools/flash-win.sh [--full] [--env NAME] [--res N] [--tubes 2|3] [COMx | /dev/ttyX]   (port: COMx, else $LW_PORT if
# COMx, else the one Espressif port; several attached: refused, name one — both boards share the USB IDs). A /dev/tty
# port (board attached to WSL) flashes with PlatformIO's esptool instead: flash.sh routes env lcd316 here for it.
# Default: flash the application only, preserving NVS. --full flashes the factory image (bootloader + partition
# table too: needed once on a board that came with other firmware). --env: platformio.ini env, else $LW_BOARD,
# else amoled191. --res: lcd316 res tag (rows + tube widths, flash.sh / tools/boardtag.py), else $LW_RES, else 320.
# --tubes: 2 / 3 (+ seconds), else $LW_TUBES, else 2.
# env lcd316 runs its flash at 120 MHz in HPM dummy-cycle mode, which needs the DC-aware bootloader of bootloader-dc/
# (tools/bootloader-dc.sh builds it and checks its sha256): pio's factory image carries Arduino's bootloader instead.
# So for lcd316 --full writes bootloader-dc + partition table + otadata + app (image headers kept as built) and verifies
# the bootloader's bytes; an app-only flash first checks the board's 0x0 against bootloader-dc and refuses on a
# mismatch (that pairing wedges at the next reset), leaving the board running what it had.
# --app-bin FILE: no build, flash FILE as the app (app-only, same bootloader check): e2e.sh --ref's reference images.
# Prints the board tag it builds (`v` reports the same).
set -euo pipefail
cd "$(dirname "$0")/.."
FULL=0
PORT=""
APP_BIN=""
ENV="${LW_BOARD:-amoled191}"; RES="${LW_RES:-}"; TUBES="${LW_TUBES:-2}"
while [ $# -gt 0 ]; do
    case "$1" in
        --full) FULL=1 ;;
        --env) ENV="$2"; shift ;;
        --res) RES="$2"; shift ;;
        --tubes) TUBES="$2"; shift ;;
        --app-bin) APP_BIN="$(realpath -e "$2")"; shift ;;
        COM[0-9]*|/dev/tty*) PORT="$1" ;;
        *) echo "usage: tools/flash-win.sh [--full] [--env NAME] [--res N] [--tubes 2|3] [--app-bin FILE] [COMx | /dev/ttyX]"; exit 2 ;;
    esac; shift
done
[ -z "$APP_BIN" ] || [ "$FULL" -eq 0 ] || { echo "flash-win.sh: --app-bin is app-only (no --full)"; exit 2; }
case "${LW_PORT:-}" in COM*) PORT="${PORT:-$LW_PORT}" ;; esac
if [ -z "$PORT" ]; then
    PORTS="$(powershell.exe -NoProfile -c "Get-PnpDevice -Class Ports -PresentOnly | Where-Object InstanceId -like 'USB\VID_303A*' | ForEach-Object { \$_.FriendlyName -replace '.*\((COM\d+)\).*','\$1' }" | tr -d '\r' | grep '^COM' || true)"
    [ "$(printf '%s\n' "$PORTS" | grep -c '^COM')" -le 1 ] || { echo "several boards attached ($(echo $PORTS)): name one (COMx or LW_PORT)"; exit 1; }
    PORT="$PORTS"
fi
[ -n "$PORT" ] || { echo "no Espressif COM port found"; exit 1; }
case "$PORT" in
    COM*) ESPT=(python.exe -m esptool); winpath() { wslpath -w "$1"; } ;;
    *) ESPT=("$HOME/.platformio/penv/bin/python" -m esptool); winpath() { echo "$1"; } ;;
esac
ESPT+=(--chip esp32s3 --port "$PORT" --baud 921600)
KEEP=(--flash-mode keep --flash-freq keep --flash-size keep)   # never patch an image header (bootloader-dc must stay DOUT)
[ "$ENV" = lcd316 ] || RES=""
FLAGS="${PLATFORMIO_BUILD_FLAGS:-} $(python3 tools/boardtag.py tubes "$TUBES")"
if [ "$ENV" = lcd316 ]; then FLAGS="$FLAGS $(python3 tools/boardtag.py flags "$RES" "$TUBES")"; fi
. tools/pkgdir.sh
B=.pio/build/$ENV; APP="$B/firmware.bin"
if [ -n "$APP_BIN" ]; then
    echo "flash-win.sh: flashing $APP_BIN (no build) to $PORT"; APP="$APP_BIN"
else
    echo "flash-win.sh: building $(python3 tools/boardtag.py tag "$ENV" $FLAGS), flashing $PORT"
    PLATFORMIO_BUILD_FLAGS="$FLAGS" ~/.platformio/penv/bin/pio run -s -e "$ENV"
fi
if [ "$ENV" = lcd316 ]; then
    BOOT="$(tools/bootloader-dc.sh | tail -1)"   # exit 1 (set -e) unless it is the tested image
    if [ "$FULL" -eq 1 ]; then
        "${ESPT[@]}" --after no-reset write-flash "${KEEP[@]}" 0x0 "$(winpath "$BOOT")" 0x8000 "$(winpath "$B/partitions.bin")" \
            0xe000 "$(winpath "$PLATFORMIO_PACKAGES_DIR/framework-arduinoespressif32/tools/partitions/boot_app0.bin")" \
            0x10000 "$(winpath "$APP")"
        "${ESPT[@]}" --before no-reset verify-flash "${KEEP[@]}" 0x0 "$(winpath "$BOOT")"
    else
        if ! "${ESPT[@]}" --after no-reset verify-flash "${KEEP[@]}" 0x0 "$(winpath "$BOOT")"; then
            "${ESPT[@]}" --before no-reset chip-id >/dev/null 2>&1 || true   # hard reset: back to what it ran
            echo "flash-win.sh: the board's bootloader at 0x0 is not bootloader-dc (or esptool failed above). An HPM-DC"
            echo "  app on another bootloader wedges at the next reset: nothing flashed. Use --full (NVS is kept)."
            exit 1
        fi
        "${ESPT[@]}" --before no-reset write-flash "${KEEP[@]}" 0x10000 "$(winpath "$APP")"
    fi
    exit 0
fi
if [ "$FULL" -eq 1 ]; then
    OFFSET=0x0
    IMAGE=$B/firmware.factory.bin
else
    OFFSET=0x10000
    IMAGE=$APP
fi
"${ESPT[@]}" write-flash "$OFFSET" "$(winpath "$IMAGE")"
