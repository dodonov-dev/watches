#!/usr/bin/env bash
# build.sh <tree> <env> [res]  -> builds firmware only, prints size
set -e
cd "$1/firmware"; ENV=$2; RES=${3:-}
FLAGS="$(python3 tools/boardtag.py tubes 2)"
[ "$ENV" = lcd316 ] && FLAGS="$FLAGS $(python3 tools/boardtag.py flags "$RES" 2)"
. tools/pkgdir.sh
echo "building $(python3 tools/boardtag.py tag "$ENV" $FLAGS) in $1"
PLATFORMIO_BUILD_FLAGS="$FLAGS" ~/.platformio/penv/bin/pio run -e "$ENV" 2>&1 | grep -E "RAM:|Flash:|SUCCESS|FAILED|error" | head -20
~/.platformio/penv/bin/pio run -e "$ENV" -t size 2>/dev/null | tail -0 || true
