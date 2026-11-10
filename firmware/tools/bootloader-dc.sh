#!/usr/bin/env bash
# Build env lcd316's DC-aware 2nd-stage bootloader (bootloader-dc/README.md) with the ESP-IDF that pioarduino installed
# in ~/.platformio/packages-lcd316 (cmake + ninja: idf.py needs PyYAML, which that venv lacks). Incremental; a change
# under bootloader-dc/ rebuilds from a clean dir. Last stdout line: the image path. Exit 1 unless the image's sha256
# equals bootloader-dc/bootloader-dc.sha256, the image tested on the board (--any-sha: build only, for a deliberate change).
# Used by flash-win.sh (lcd316: --full writes it, app-only flashes check the board's 0x0 against it).
set -euo pipefail
cd "$(dirname "$0")/.."
ANY=0; [ "${1:-}" = --any-sha ] && ANY=1
SRC="$PWD/bootloader-dc"; OUT="$PWD/.pio/bootloader-dc"
PKG="$HOME/.platformio/packages-lcd316"
PY="$HOME/.platformio/penv/.espidf-5.5.5/bin/python"   # pioarduino's IDF venv (kconfgen etc.), made by the first lcd316 build
for p in "$PKG/framework-espidf" "$PKG/toolchain-xtensa-esp-elf/bin" "$PKG/tool-cmake/bin" "$PKG/tool-ninja" "$PY"; do
    [ -e "$p" ] || { echo "bootloader-dc.sh: missing $p (run one lcd316 build first: tools/flash.sh / pkgdir.sh)" >&2; exit 1; }
done
export IDF_PATH="$PKG/framework-espidf" PATH="$PKG/toolchain-xtensa-esp-elf/bin:$PKG/tool-cmake/bin:$PKG/tool-ninja:$PATH"
export ESPTOOL_WRAPPER="$SRC/esptool_wrapper.py"   # IDF's elf2image step through PlatformIO's esptool (see the wrapper)
# __DATE__ / __TIME__ (esp_bootloader_desc.date_time, CONFIG_BOOTLOADER_COMPILE_TIME_DATE) pinned to the tested image's
# "Nov  9 2026 16:21:42": with it the build is byte-identical to that image. GCC formats SOURCE_DATE_EPOCH in UTC.
export SOURCE_DATE_EPOCH=1794241302
STAMP="$OUT/.inputs"
INPUTS="$(cd "$SRC" && find . -type f ! -name '*.sha256' ! -name README.md ! -name '*.pyc' | sort | xargs sha256sum)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$INPUTS" ]; then
    rm -rf "$OUT"; mkdir -p "$OUT"
    cmake -S "$SRC" -B "$OUT" -G Ninja -DPYTHON="$PY" -DPYTHON_DEPS_CHECKED=1 -DIDF_TARGET=esp32s3 \
          -DSDKCONFIG="$OUT/sdkconfig" -DSDKCONFIG_DEFAULTS="$SRC/sdkconfig.defaults" >"$OUT/cmake.log" 2>&1 \
        || { tail -20 "$OUT/cmake.log" >&2; echo "bootloader-dc.sh: cmake failed ($OUT/cmake.log)" >&2; exit 1; }
    printf '%s\n' "$INPUTS" >"$STAMP"
fi
ninja -C "$OUT" bootloader >"$OUT/ninja.log" 2>&1 || { tail -20 "$OUT/ninja.log" >&2; echo "bootloader-dc.sh: build failed ($OUT/ninja.log)" >&2; exit 1; }
BIN="$OUT/bootloader/bootloader.bin"
GOT="$(sha256sum "$BIN" | cut -d' ' -f1)"; WANT="$(cut -d' ' -f1 "$SRC/bootloader-dc.sha256")"
if [ "$GOT" != "$WANT" ] && [ "$ANY" -eq 0 ]; then
    echo "bootloader-dc.sh: $BIN sha256 $GOT, expected $WANT (bootloader-dc/bootloader-dc.sha256): not the tested image" >&2
    exit 1
fi
echo "$BIN"
