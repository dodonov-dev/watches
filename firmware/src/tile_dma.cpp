// LCD tile sink (tiles.h): each tube's finished tiles go to its PSRAM strip by GDMA mem-to-mem, one channel pair per
// tube (both cores render at once). The DMA writes PSRAM behind the data cache, so the strip's lines are dropped from
// the cache before the first tile (tile_begin) and nothing touches the strip until the last copy landed (tile_end):
// no line is fetched, none written back by the CPU. No interrupt: a copy polls the descriptor of the one before it.
// The same channel and the tube's slot memory also serve the push of that tube's strip (tile_gather_*, display_lcd316.cpp).
#if defined(BOARD_LCD316) && defined(__XTENSA__)
#include "tiles.h"
#if TILE_RENDER
#include <string.h>
#include "layout.h"
#include "esp_cache.h"
#include "esp_cpu.h"
#include "esp_system.h"
#include "esp_private/gdma.h"
#include "hal/dma_types.h"

#define TILE_BYTES (TILE_ROWS * PANEL_W * 2)
// Bursts per direction: the RX side writes the PSRAM strip (tiles: 32-B blocks, all a 4-row tile of 1,640-B rows is a
// whole number of, and RX into PSRAM must be aligned to its burst), the TX side reads it for the push (64 B: a strip
// read took ~2.7 ms by 64-B bursts vs ~4.4 by 32-B ones under the renders' load, probe 2026-10-30).
#define RX_BURST 32
#define TX_BURST 64
#define DESC_MAX 4064     // largest descriptor buffer that is a whole number of RX blocks (the size field is 12 bits)
#define LAND_TIMEOUT_CYC (240u * 1000000u)   // 1 s at 240 MHz (waitLanded)
#define NDESC ((TILE_BYTES + DESC_MAX - 1) / DESC_MAX)
static_assert(TILE_BYTES % RX_BURST == 0, "a tile must be a whole number of PSRAM DMA blocks");

// Two slots per tube, internal DMA-capable RAM (.bss), static: TILE_ROWS x PANEL_W each. While the tube's strip is
// pushed they hold the push's gather units and, at TILE_SCRATCH_FREE, the gather descriptors instead.
struct GatherSet { dma_descriptor_t tx[TILE_GATHER_ROWS], rx[2]; };
static_assert(TILE_SCRATCH_FREE % 4 == 0 && TILE_SCRATCH_FREE + 2 * sizeof(GatherSet) <= 2 * TILE_BYTES,
              "gather units + descriptors fit the two slots");
static uint16_t tileBuf[2][2][TILE_ROWS * PANEL_W] __attribute__((aligned(64)));
struct TileChan {
  gdma_channel_handle_t tx = nullptr, rx = nullptr;
  dma_descriptor_t txd[NDESC], rxd[NDESC];
  const dma_descriptor_t *pending = nullptr;   // the last RX descriptor of the copy in flight
  uint32_t prof[5] = {};   // cycles: tile_begin (cache drop), waits in tile_put, wait in tile_end, put set-up, gather waits
};
static TileChan chans[2];

bool tiles_init() {
  for (TileChan &c : chans) {
    gdma_channel_alloc_config_t txc = {}; txc.direction = GDMA_CHANNEL_DIRECTION_TX; txc.flags.reserve_sibling = 1;
    if (gdma_new_ahb_channel(&txc, &c.tx) != ESP_OK) return false;
    gdma_channel_alloc_config_t rxc = {}; rxc.direction = GDMA_CHANNEL_DIRECTION_RX; rxc.sibling_chan = c.tx;
    if (gdma_new_ahb_channel(&rxc, &c.rx) != ESP_OK) return false;
    gdma_trigger_t trig = GDMA_MAKE_TRIGGER(GDMA_TRIG_PERIPH_M2M, 0);
    uint32_t mask = 0;
    if (gdma_get_free_m2m_trig_id_mask(c.tx, &mask) != ESP_OK || !mask) return false;
    trig.instance_id = __builtin_ctz(mask);
    if (gdma_connect(c.rx, trig) != ESP_OK || gdma_connect(c.tx, trig) != ESP_OK) return false;
    gdma_strategy_config_t st = {};
    st.owner_check = true; st.auto_update_desc = true; st.eof_till_data_popped = true;
    gdma_apply_strategy(c.tx, &st); gdma_apply_strategy(c.rx, &st);
    gdma_transfer_config_t tc = {}; tc.access_ext_mem = true;
    tc.max_data_burst_size = TX_BURST; if (gdma_config_transfer(c.tx, &tc) != ESP_OK) return false;
    tc.max_data_burst_size = RX_BURST; if (gdma_config_transfer(c.rx, &tc) != ESP_OK) return false;
    size_t intA = 0, extA = 0;
    gdma_get_alignment_constraints(c.rx, &intA, &extA);
    if (extA > RX_BURST || intA > 4) return false;
  }
  return true;
}

uint16_t *tile_slot(int idx, int slot) { return tileBuf[idx & 1][slot & 1]; }
uint8_t *tile_scratch(int idx) { return (uint8_t *)tileBuf[idx & 1][0]; }

static void waitLanded(TileChan &c, int k) {   // the RX engine hands the last descriptor back once the copy is written
  if (!c.pending) return;
  const uint32_t c0 = esp_cpu_get_cycle_count();
  // A copy takes ~0.3 ms (a gather ~1 ms); 1 s (above any flash-write stall, below the 5 s task WDT) means the engine
  // never ran: stop visibly instead of spinning.
  while (((const volatile dma_descriptor_t *)c.pending)->dw0.owner)
    if (esp_cpu_get_cycle_count() - c0 > LAND_TIMEOUT_CYC) esp_system_abort("tile DMA copy did not land (tile_dma.cpp)");
  c.prof[k] += esp_cpu_get_cycle_count() - c0;
  c.pending = nullptr;
}
static inline void desc(dma_descriptor_t &d, void *buf, int n, bool tx, bool last, dma_descriptor_t *next) {
  d.buffer = buf; d.next = last ? nullptr : next;
  d.dw0.size = n; d.dw0.length = tx ? n : 0; d.dw0.err_eof = 0; d.dw0.suc_eof = tx && last; d.dw0.owner = 1;
}
static void go(TileChan &c, dma_descriptor_t *tx0, dma_descriptor_t *rx0, const dma_descriptor_t *rxLast) {
  __asm__ __volatile__("memw" ::: "memory");   // descriptors in place before the engines start
  if (gdma_start(c.rx, (intptr_t)rx0) != ESP_OK || gdma_start(c.tx, (intptr_t)tx0) != ESP_OK)
    esp_system_abort("tile DMA start failed (tiles_init failed? see the boot log)");
  c.pending = rxLast;
}

void tile_begin(int idx, uint16_t *strip, int rows) {
  TileChan &c = chans[idx & 1];
  waitLanded(c, 2);
  const uint32_t c0 = esp_cpu_get_cycle_count();
  const size_t bytes = ((size_t)(rows + TILE_ROWS - 1) / TILE_ROWS * TILE_BYTES + 63) & ~(size_t)63;   // the strip has the slack
  esp_cache_msync(strip, bytes, ESP_CACHE_MSYNC_FLAG_DIR_M2C | ESP_CACHE_MSYNC_FLAG_TYPE_DATA);
  c.prof[0] += esp_cpu_get_cycle_count() - c0;
}

void tile_put(int idx, int slot, uint16_t *dst, int) {
  TileChan &c = chans[idx & 1];
  waitLanded(c, 1);
  const uint32_t c0 = esp_cpu_get_cycle_count();
  uint8_t *src = (uint8_t *)tileBuf[idx & 1][slot & 1], *d = (uint8_t *)dst;
  for (int k = 0; k < NDESC; k++) {
    const int n = k < NDESC - 1 ? DESC_MAX : TILE_BYTES - DESC_MAX * (NDESC - 1);
    const int nx = k + 1 < NDESC ? k + 1 : k;
    desc(c.txd[k], src + k * DESC_MAX, n, true, k == NDESC - 1, &c.txd[nx]);
    desc(c.rxd[k], d + k * DESC_MAX, n, false, k == NDESC - 1, &c.rxd[nx]);
  }
  go(c, &c.txd[0], &c.rxd[0], &c.rxd[NDESC - 1]);
  c.prof[3] += esp_cpu_get_cycle_count() - c0;
}

void tile_end(int idx) { waitLanded(chans[idx & 1], 2); }

void tile_gather_start(int idx, int set, uint8_t *dst, const uint16_t *src, const int32_t *off, int rows, int col, int bytes) {
  TileChan &c = chans[idx & 1];
  waitLanded(c, 4);
  GatherSet &g = ((GatherSet *)(tile_scratch(idx) + TILE_SCRATCH_FREE))[set & 1];
  for (int r = 0; r < rows; r++)
    desc(g.tx[r], (void *)(src + off[r] + col), bytes, true, r == rows - 1, &g.tx[r + 1 < rows ? r + 1 : r]);
  const int total = rows * bytes, h = rows > TILE_GATHER_ROWS / 2 ? TILE_GATHER_ROWS / 2 * bytes : total;   // RX: <= 16 rows each
  desc(g.rx[0], dst, h, false, h == total, &g.rx[1]);
  if (h < total) desc(g.rx[1], dst + h, total - h, false, true, &g.rx[1]);
  go(c, &g.tx[0], &g.rx[0], h < total ? &g.rx[1] : &g.rx[0]);
}
void tile_gather_wait(int idx) { waitLanded(chans[idx & 1], 4); }

const uint32_t *tile_prof(int idx) { return chans[idx & 1].prof; }
#endif   // TILE_RENDER
#endif
