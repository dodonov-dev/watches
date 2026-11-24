#!/bin/bash
# build_noise.sh SRC_DIR OUT : noise.cpp against SRC_DIR's render.cpp / physics.cpp (lcd316 320w8-8, tiles); W = the
# worktree whose headers go with SRC_DIR (default this one)
D=$(cd $(dirname $0) && pwd); W=${W:-$(cd $D/../../.. && pwd)}; SRC=$1; ST=$(dirname $2)/stub
mkdir -p $ST   # ESP stubs (as check_board_render.py), beside OUT
printf '#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\ninline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n' > $ST/esp_heap_caps.h
printf '#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 0xabcdef01; }\n' > $ST/esp_random.h
FL=$(cd $W/firmware/tools && python3 -c "import boardtag; print(' '.join(boardtag.res_flags('320w8-8', 2)+boardtag.tubes_flags(2)))")
c++ -std=c++17 -O2 ${NOISE_FLAGS:-} -ffp-contract=off -DTILE_RENDER=1 -DPUSH_LENS=0 -DBOARD_LCD316 $FL -I $ST -I $W/firmware/src -I $W/spec $D/noise.cpp $SRC/render.cpp $SRC/physics.cpp -o $2
