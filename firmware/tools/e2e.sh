#!/usr/bin/env bash
# End-to-end firmware check: build -> flash -> pinned fps bench -> pixel parity vs the sim.
#   tools/e2e.sh [--label TEXT] [--stages] [--stage name=v ...] [--no-ble] [--bare] [--no-flash] [--samples N]
#                [--preset FILE.json] [--fix-pose] [--live-imu] [--runs N] [--ref COMMIT] [--stages fizz,digits] [--quick] [--no-parity]
#                [--env NAME] [--res N]
# --env NAME = platformio.ini env to build and flash (else $LW_BOARD, else amoled191; lcd316 for the ESP32-S3-LCD-3.16);
#   --res TAG = the lcd316's res tag: canvas rows (RENDER_H 240 / 256 / 288 / 320) + tube widths (nothing narrow, f both
#   wide, fh / fm hours / minutes wide; tools/boardtag.py), else $LW_RES, else 320 = native, narrow. Parity renders the
#   sim at whatever the board reports (`v`). --define NAME=V adds -DNAME=V to the build (e.g. STRIPS_INTERNAL=1,
#   display_lcd316.cpp) and to the label. After a flash the board's `v` must report the tag of what was built (else
#   exit 4: the image did not take, or a --ref commit cannot build that tag). Which board: LW_PORT (required with
#   several attached; flash.sh / device.py refuse to guess).
# Faster runs: --stages with a comma list measures only those stages; --quick halves the sampling (3 base samples,
#   2 per stage, shorter settles); --no-parity skips the sim comparison when only timing matters; --ref reuses
#   .pio/libdeps in the worktree.
# --bare = no BLE and no IMU polling: USB serial + physics + render only (the ceiling); the bench then accepts
#   the all-zero IMU (--allow-dead-imu).
# --preset / --fix-pose / --live-imu / --runs / --stage go to bench.py (see its docstring). Pin a preset whenever the two sides
#   of a comparison straddle a Params change: a PARAMS_SCHEMA_CRC change resets NVS to presets/1.json on flash.
# --ref COMMIT = A/B in one go: first a temporary git worktree of COMMIT (under /tmp) is built and flashed with the
#   same flags and benched with the same preset/runs/stages (label "<label> ref <sha>", no parity step: the sim
#   is not that commit's), the worktree is removed, then the current tree runs the normal flow.
# Appends the bench lines + parity line to firmware/.compare/e2e.log. Board must be reachable (device.py).
# Exit 3 = bench.py found the IMU dead even after a reboot (the run is not comparable).
set -euo pipefail
USAGE="usage: $0 [--label TEXT] [--stages] [--stage name=v] [--no-ble] [--bare] [--no-flash] [--samples N] [--preset FILE] [--fix-pose] [--live-imu] [--runs N] [--ref COMMIT] [--stages LIST] [--quick] [--no-parity] [--env NAME] [--res N] [--define NAME=V]"
LABEL=""; BENCH=(); FLASH=1; PARITY=1; SAMPLES=5; FLAGS=""; SUFFIX=""; PRESET=""; REF=""; ENV="${LW_BOARD:-amoled191}"; RES="${LW_RES:-}"
while [ $# -gt 0 ]; do
    case "$1" in
        --label) LABEL="$2"; shift ;;
        --stages) if [ $# -gt 1 ] && [[ "$2" != --* ]]; then BENCH+=(--stages "$2"); shift; else BENCH+=(--stages); fi ;;
        --quick) BENCH+=(--quick) ;;
        --no-parity) PARITY=0 ;;
        --stage) BENCH+=(--stage "$2"); shift ;;
        --no-ble) FLAGS="-DNO_BLE"; SUFFIX=" no-ble" ;;
        --bare) FLAGS="-DNO_BLE -DNO_IMU"; SUFFIX=" bare"; BENCH+=(--allow-dead-imu) ;;
        --no-flash) FLASH=0 ;;
        --samples) SAMPLES="$2"; shift ;;
        --preset) PRESET="$(realpath -e "$2")"; shift ;;   # resolved before the cd below
        --live-imu) BENCH+=(--live-imu) ;;
        --fix-pose) BENCH+=(--fix-pose) ;;
        --runs) BENCH+=(--runs "$2"); shift ;;
        --ref) REF="$2"; shift ;;
        --env) ENV="$2"; shift ;;
        --res) RES="$2"; shift ;;
        --define) DEFINES="${DEFINES:-} -D$2"; SUFFIX="$SUFFIX $2"; shift ;;
        -h|--help) echo "$USAGE"; exit 0 ;;
        *) echo "$USAGE"; exit 2 ;;
    esac; shift
done
cd "$(dirname "$0")/.."
LW_PORT="${LW_PORT:-$(python3 tools/device.py --find-port)}"   # pinned before anything flashes: a --ref commit's scripts
export LW_PORT                                                  # may still take "the first" port (refused: several attached)
[ -n "$LABEL" ] || LABEL="$(git rev-parse --short HEAD)$(git diff --quiet || echo '+dirty')"
[ "$ENV" = lcd316 ] || RES=""
FLAGS="$FLAGS${DEFINES:-}"
RES_FLAGS=""; [ "$ENV" = lcd316 ] && RES_FLAGS="$(python3 tools/boardtag.py flags "$RES")"   # a bad tag stops here
WANT_TAG="$(python3 tools/boardtag.py tag "$ENV" $FLAGS $RES_FLAGS)"   # what the build's `v` reports
export LW_BOARD="$ENV" LW_RES="$RES"   # flash.sh / flash-win.sh read them
# check_tag WHAT: the attached board's `v` against WANT_TAG (after a flash: exit 4 on a mismatch).
check_tag() {
    local got; got="$(python3 tools/device.py v | sed -n 's/^board \([^ ]*\).*/\1/p')"
    [ -n "$got" ] || got="nothing (no \`v\` reply: old firmware, or no board)"
    [ "$got" = "$WANT_TAG" ] && return 0
    echo "e2e.sh: $1: the board reports $got, expected $WANT_TAG" | tee -a .compare/e2e.log
    return 4
}
ENV_ARGS=(); [ "$ENV" = amoled191 ] || { SUFFIX="$SUFFIX $ENV${RES:+@$RES}"; ENV_ARGS=(--env "$ENV"); }   # default: no flag, so --ref works on commits before flash.sh took --env
LABEL="$LABEL$SUFFIX"
[ -n "$PRESET" ] && BENCH+=(--preset "$PRESET")
if [ -n "$PRESET" ]; then PRESET_TAG="preset $(basename "$PRESET")"; else PRESET_TAG="preset (board NVS)"; fi
mkdir -p .compare

# bench LABEL: header + bench.py into the log; returns bench.py's status (3 = dead IMU).
bench() {
    local rc
    set +e
    {
        echo "== $(date '+%F %T')  $1  $PRESET_TAG"
        python3 tools/bench.py --samples "$SAMPLES" --label "$1" ${BENCH[@]+"${BENCH[@]}"}
    } | tee -a .compare/e2e.log
    rc=${PIPESTATUS[0]}
    set -e
    [ "$rc" -eq 3 ] && echo "e2e.sh: IMU dead after a reboot (bench.py exit 3); run not comparable" | tee -a .compare/e2e.log
    return "$rc"
}

if [ -n "$REF" ]; then
    [ "$FLASH" -eq 1 ] || { echo "e2e.sh: --ref needs to flash (drop --no-flash)"; exit 2; }
    REF_SHA="$(git rev-parse --short "$REF^{commit}")"
    WT="$(mktemp -d /tmp/lw-ref-XXXXXX)"
    cleanup() { git worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"; git worktree prune; }
    trap cleanup EXIT
    git worktree add --detach "$WT" "$REF_SHA" >/dev/null
    [ -d .pio/libdeps ] && cp -r .pio/libdeps "$WT/firmware/.pio/" 2>/dev/null || { mkdir -p "$WT/firmware/.pio" && cp -r .pio/libdeps "$WT/firmware/.pio/"; }   # no library re-download
    # The worktree's flash scripts may predate $LW_PORT and the width suffix of a res tag: route the chosen board here
    # (they cd into its firmware/), the res as -D flags, LW_RES as plain rows (they add -DRENDER_H from it).
    REF_ENV=(env LW_RES="${RES:+$(python3 tools/boardtag.py flags "$RES" | sed 's/^-DRENDER_H=\([0-9]*\).*/\1/')}" PLATFORMIO_BUILD_FLAGS="$FLAGS $RES_FLAGS")
    case "${LW_PORT:-}" in
        COM*) "${REF_ENV[@]}" "$WT/firmware/tools/flash-win.sh" ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} "$LW_PORT" ;;
        ?*) (. tools/pkgdir.sh; cd "$WT/firmware" && "${REF_ENV[@]}" ~/.platformio/penv/bin/pio run -s -e "$ENV" -t upload --upload-port "$LW_PORT") ;;   # pkgdir.sh: lcd316's own packages dir
        *) "${REF_ENV[@]}" "$WT/firmware/tools/flash.sh" ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} ;;
    esac
    sleep 4
    check_tag "ref $REF_SHA" || exit 4
    bench "$LABEL ref $REF_SHA"
    cleanup; trap - EXIT
fi
if [ "$FLASH" -eq 1 ]; then
    PLATFORMIO_BUILD_FLAGS="$FLAGS" tools/flash.sh ${ENV_ARGS[@]+"${ENV_ARGS[@]}"}
    sleep 4
    check_tag "after the flash" || exit 4
else
    check_tag "--no-flash (label only)" || true   # benches what the board runs; the label may not say it
fi
bench "$LABEL"
if [ "$PARITY" -eq 1 ]; then python3 tools/compare-device.py | grep '^mismatched' | tee -a .compare/e2e.log; fi
