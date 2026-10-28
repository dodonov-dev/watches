// Waveshare ESP32-S3-LCD-3.16: ST7701 RGB LCD, 320x820, scanned portrait (320-px lines, 820 lines) out of a
// PSRAM framebuffer by the LCD_CAM peripheral; the panel has no frame memory and cannot rotate. The face renders
// into the PANEL_W x PANEL_H canvas of layout.h (the panel's aspect, RENDER_H rows), shown on the whole 820x320 panel
// (nearest-neighbour, 1:1 at RENDER_H 320) by a scan-line fill from the strips (below). Pushes hand over, nothing is
// left in flight, so the wait calls return at once.
// Pins, init sequence and RGB timings from Waveshare's ESP32-S3-LCD-3.16 demo (07_LVGL_V8_Test). LCD CS is
// GPIO0 through R38 in both schematic revisions (the wiki's pin table says IO42).
#include "display.h"
#include <Arduino.h>
#include <string.h>
#include "driver/gpio.h"
#include "esp_lcd_panel_rgb.h"
#include "esp_lcd_panel_ops.h"
#include "esp_heap_caps.h"
#include "esp_cpu.h"
#include "esp_cache.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_rom_sys.h"
#include "layout.h"

#define LCD_H_RES   LCD_PANEL_H   // 320 pixels per scan line: across the landscape face
#define LCD_V_RES   LCD_PANEL_W   // 820 scan lines: along the face

#define PIN_SPI_CS  0     // ST7701 3-wire SPI (9-bit: D/C + 8), init only
#define PIN_SPI_SCK 2
#define PIN_SPI_SDA 1
#define PIN_LCD_RST 16
#define PIN_BL      6     // backlight PWM, active low
#define PIN_DE      40
#define PIN_PCLK    41
#define PIN_VSYNC   39
#define PIN_HSYNC   38
// RGB565 data bus, bit 0 first: B0..B4, G0..G5, R0..R4
static const int DATA_PINS[16] = {21, 5, 45, 48, 47,  14, 13, 12, 11, 10, 9,  17, 46, 3, 8, 18};

// USB_LEFT=1 (default): landscape with USB-C on the left (verified on the board; USB_LEFT=0 untested). Panel line 0
// is the end away from USB-C, column 0 the far long edge; the landscape face point (a along, b across; the canvas
// scaled to 820x320) maps to (line, column):
//   USB_LEFT=1: (LCD_V_RES-1 - a, b)     USB_LEFT=0: (a, LCD_H_RES-1 - b)
#ifndef USB_LEFT
#define USB_LEFT 1
#endif

struct InitCmd { uint8_t cmd, n; uint16_t delayMs; uint8_t d[16]; };
// Verbatim from Waveshare 07_LVGL_V8_Test lvgl_port.c, preceded by what its esp_lcd_st7701 driver sends first
// (Command2 off, MADCTL RGB order, COLMOD 16 bpp).
static const InitCmd lcd_init_cmds[] = {
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x00}},
  {0x36, 1, 0, {0x00}},
  {0x3A, 1, 0, {0x55}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x13}},
  {0xEF, 1, 0, {0x08}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x10}},
  {0xC0, 2, 0, {0xE5, 0x02}},
  {0xC1, 2, 0, {0x15, 0x0A}},
  {0xC2, 2, 0, {0x07, 0x02}},
  {0xCC, 1, 0, {0x10}},
  {0xB0, 16, 0, {0x00, 0x08, 0x51, 0x0D, 0xCE, 0x06, 0x00, 0x08, 0x08, 0x24, 0x05, 0xD0, 0x0F, 0x6F, 0x36, 0x1F}},
  {0xB1, 16, 0, {0x00, 0x10, 0x4F, 0x0C, 0x11, 0x05, 0x00, 0x07, 0x07, 0x18, 0x02, 0xD3, 0x11, 0x6E, 0x34, 0x1F}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x11}},
  {0xB0, 1, 0, {0x4D}},
  {0xB1, 1, 0, {0x37}},
  {0xB2, 1, 0, {0x87}},
  {0xB3, 1, 0, {0x80}},
  {0xB5, 1, 0, {0x4A}},
  {0xB7, 1, 0, {0x85}},
  {0xB8, 1, 0, {0x21}},
  {0xB9, 2, 0, {0x00, 0x13}},
  {0xC0, 1, 0, {0x09}},
  {0xC1, 1, 0, {0x78}},
  {0xC2, 1, 0, {0x78}},
  {0xD0, 1, 0, {0x88}},
  {0xE0, 3, 100, {0x80, 0x00, 0x02}},
  {0xE1, 11, 0, {0x0F, 0xA0, 0x00, 0x00, 0x10, 0xA0, 0x00, 0x00, 0x00, 0x60, 0x60}},
  {0xE2, 13, 0, {0x30, 0x30, 0x60, 0x60, 0x45, 0xA0, 0x00, 0x00, 0x46, 0xA0, 0x00, 0x00, 0x00}},
  {0xE3, 4, 0, {0x00, 0x00, 0x33, 0x33}},
  {0xE4, 2, 0, {0x44, 0x44}},
  {0xE5, 16, 0, {0x0F, 0x4A, 0xA0, 0xA0, 0x11, 0x4A, 0xA0, 0xA0, 0x13, 0x4A, 0xA0, 0xA0, 0x15, 0x4A, 0xA0, 0xA0}},
  {0xE6, 4, 0, {0x00, 0x00, 0x33, 0x33}},
  {0xE7, 2, 0, {0x44, 0x44}},
  {0xE8, 16, 0, {0x10, 0x4A, 0xA0, 0xA0, 0x12, 0x4A, 0xA0, 0xA0, 0x14, 0x4A, 0xA0, 0xA0, 0x16, 0x4A, 0xA0, 0xA0}},
  {0xEB, 7, 0, {0x02, 0x00, 0x4E, 0x4E, 0xEE, 0x44, 0x00}},
  {0xED, 16, 0, {0xFF, 0xFF, 0x04, 0x56, 0x72, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x27, 0x65, 0x40, 0xFF, 0xFF}},
  {0xEF, 6, 0, {0x08, 0x08, 0x08, 0x40, 0x3F, 0x64}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x13}},
  {0xE8, 2, 0, {0x00, 0x0E}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x00}},
  {0x11, 0, 120, {}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x13}},
  {0xE8, 2, 10, {0x00, 0x0C}},
  {0xE8, 2, 0, {0x00, 0x00}},
  {0xFF, 5, 0, {0x77, 0x01, 0x00, 0x00, 0x00}},
  {0x3A, 1, 0, {0x55}},
  {0x36, 1, 0, {0x00}},
  {0x35, 1, 0, {0x00}},
  {0x29, 0, 20, {}},
  {0xC3, 1, 0, {0x80}},
};

// One 9-bit word, MSB first, D/C bit leading (1 = parameter); data latched on SCK rising, ~500 kHz.
static void spi9(bool param, uint8_t v) {
  const uint16_t w = (param ? 0x100 : 0) | v;
  gpio_set_level((gpio_num_t)PIN_SPI_CS, 0); esp_rom_delay_us(1);
  for (int b = 8; b >= 0; b--) {
    gpio_set_level((gpio_num_t)PIN_SPI_SDA, (w >> b) & 1);
    gpio_set_level((gpio_num_t)PIN_SPI_SCK, 0); esp_rom_delay_us(1);
    gpio_set_level((gpio_num_t)PIN_SPI_SCK, 1); esp_rom_delay_us(1);
  }
  gpio_set_level((gpio_num_t)PIN_SPI_SCK, 0); gpio_set_level((gpio_num_t)PIN_SPI_SDA, 0); esp_rom_delay_us(1);
  gpio_set_level((gpio_num_t)PIN_SPI_CS, 1); esp_rom_delay_us(1);
}

static esp_lcd_panel_handle_t panel = NULL;
// Face -> canvas (nearest neighbour, identity at RENDER_H 320): face column a (along) shows canvas column colOf[a],
// face row b (across) canvas row rowOf[b]. Built at boot.
static int16_t colOf[LCD_V_RES], rowOf[LCD_H_RES];

// Two ways to feed the panel (build switch, -DLCD_SCAN=0/1; same strips API to main.cpp):
//   LCD_SCAN 0  (default) PSRAM framebuffer scanned by the LCD DMA; each push turns the strips into it on the CPU,
//               once per rendered frame.
//   LCD_SCAN 1  no framebuffer, an ISR fills each scan line from the shown strips (below). It gathers the frame at
//               every refresh (46 Hz) from PSRAM, missing the cache on every row: 39-50 % of core 1, no fps gain over
//               the push (user preset 2026-10-27: 240 27.0 vs 26.4 fps, native 13.7 vs 14.1), and the image tears —
//               the fill misses its deadline under the renders' PSRAM traffic. Kept for experiments only.
#ifndef LCD_SCAN
#define LCD_SCAN 0
#endif
const bool display_row_map = true;   // both ways read strip rows through a table: the lens row map rides along

// Reset, the ST7701 init sequence over bit-banged SPI, and the RGB timings / pins both ways share.
static void panel_bringup(esp_lcd_rgb_panel_config_t &cfg) {
  for (int a = 0; a < LCD_V_RES; a++) colOf[a] = (int16_t)(a * PANEL_W / LCD_V_RES);
  for (int b = 0; b < LCD_H_RES; b++) rowOf[b] = (int16_t)(b * PANEL_H / LCD_H_RES);
  pinMode(PIN_BL, OUTPUT); digitalWrite(PIN_BL, HIGH);   // dark until the scan is black
  const int outs[] = {PIN_SPI_CS, PIN_SPI_SCK, PIN_SPI_SDA, PIN_LCD_RST};
  for (int p : outs) { gpio_reset_pin((gpio_num_t)p); gpio_set_direction((gpio_num_t)p, GPIO_MODE_OUTPUT); }
  gpio_set_level((gpio_num_t)PIN_SPI_CS, 1); gpio_set_level((gpio_num_t)PIN_SPI_SCK, 0); gpio_set_level((gpio_num_t)PIN_SPI_SDA, 0);
  gpio_set_level((gpio_num_t)PIN_LCD_RST, 0); delay(10);
  gpio_set_level((gpio_num_t)PIN_LCD_RST, 1); delay(120);
  for (const InitCmd &c : lcd_init_cmds) {
    spi9(false, c.cmd);
    for (int i = 0; i < c.n; i++) spi9(true, c.d[i]);
    if (c.delayMs) delay(c.delayMs);
  }
  cfg = {};
  cfg.clk_src = LCD_CLK_SRC_DEFAULT;
  // 386 x 900 clocks per frame -> 46.1 Hz. With the DMA reading a PSRAM framebuffer, Waveshare's 18 MHz (51.8 Hz)
  // made the picture jump sideways and back now and then (the DMA fell behind until the restart at VSYNC); 16 and
  // 14 MHz were steady (2026-10-27).
#ifndef LCD_PCLK_MHZ
#define LCD_PCLK_MHZ 16
#endif
  cfg.timings.pclk_hz = LCD_PCLK_MHZ * 1000 * 1000;
  cfg.timings.h_res = LCD_H_RES;
  cfg.timings.v_res = LCD_V_RES;
  cfg.timings.hsync_pulse_width = 6;
  cfg.timings.hsync_back_porch = 30;
  cfg.timings.hsync_front_porch = 30;
  cfg.timings.vsync_pulse_width = 40;
  cfg.timings.vsync_back_porch = 20;
  cfg.timings.vsync_front_porch = 20;
  cfg.data_width = 16;
  cfg.bits_per_pixel = 16;
  cfg.dma_burst_size = 64;
  cfg.hsync_gpio_num = PIN_HSYNC;
  cfg.vsync_gpio_num = PIN_VSYNC;
  cfg.de_gpio_num = PIN_DE;
  cfg.pclk_gpio_num = PIN_PCLK;
  cfg.disp_gpio_num = -1;
  for (int i = 0; i < 16; i++) cfg.data_gpio_nums[i] = DATA_PINS[i];
}
static void backlight_on(void) {
  delay(50);   // two scans of black before the backlight comes on
  ledcAttach(PIN_BL, 50000, 8);
  display_set_brightness(0);
}

#if LCD_SCAN
// No framebuffer: the LCD DMA streams two small internal bounce buffers, and on_bounce_empty (an ISR on the core
// that ran display_init, the loop's) fills each with the next BB_LINES scan lines straight from what is shown —
// one scan line = one canvas column, gathered down the canvas rows (scaled through colOf / rowOf), black outside
// the tube rows. The liquid face renders into sets of two tube strips (hours, minutes) in PSRAM, three of them:
// one scanned, one ready (finished, taken at the next frame start), one rendered into. The scan never shows a
// half-drawn strip, the render never waits for the scan, and the push is a hand-over, not a copy.
#define STRIP_ROWS TUBE_HEIGHT_MAX
#define STRIP_BYTES ((size_t)PANEL_W * STRIP_ROWS * 2)
#define SETS 3
#define FRAME_SRC SETS     // scan source of a whole canvas from display_push_frame (the other faces)
// Scan lines per bounce buffer (2 x 26 KB internal; the driver wants 820 / (2 x BB_LINES) whole). Each fill reads
// every shown canvas row once, BB_LINES columns of it in a row (~3 cache lines): the renders on both cores evict
// the strips' lines between fills, so fewer, wider fills miss less (10-line fills cost 63 % of a core, 2026-10-27).
#define BB_LINES 41
static uint16_t *strips[SETS][2];

// A scan source: per face row b the canvas row shown there (byte-swapped pixels; null = black) and the runs
// [b0, b1) of non-null rows, which the fill gathers (the rest of a bounce buffer stays black). pattern = the runs
// as one key: a bounce buffer last filled with another pattern is cleared first.
struct Src { const uint16_t *row[LCD_H_RES]; int16_t run[2][2]; int nRuns; uint64_t pattern; };
static Src srcs[SETS + 1];

// Who shows what, under `mux` (task and ISR): scanSrc = the source of the frame being scanned (a set or FRAME_SRC),
// readySrc = the one taken at the next frame start (-1 none). A set that is neither is free to render into.
static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
static volatile int scanSrc = FRAME_SRC, readySrc = -1;
static int backSet = 0;                       // the set display_next_strips handed out (task side)
static uint8_t pushed = 0;                    // bit i: strip i of backSet pushed
static int16_t pushY0[2] = {0, 0}, pushRows = 0;
static const int16_t *pushMap[2] = {nullptr, nullptr};   // their lens row maps
static const uint16_t *frameSrc = nullptr;    // canvas behind srcs[FRAME_SRC]
static volatile uint32_t fillCycles = 0;      // CPU cycles spent in the fill ISR (display_busy_cycles)
static void *bbPtr[2] = {nullptr, nullptr};
static uint64_t bbPattern[2] = {~0ull, ~0ull};

// Runs and pattern of a source whose rows are set (task side, on a source the ISR does not read).
static void finishSrc(Src &s) {
  s.nRuns = 0;
  for (int b = 0; b < LCD_H_RES;) {
    if (!s.row[b]) { b++; continue; }
    int e = b; while (e < LCD_H_RES && s.row[e]) e++;
    if (s.nRuns < 2) { s.run[s.nRuns][0] = (int16_t)b; s.run[s.nRuns][1] = (int16_t)e; s.nRuns++; }
    else s.run[1][1] = (int16_t)e;   // tubes overlapping a third way: gather the rows in between too
    b = e;
  }
  s.pattern = s.nRuns;
  for (int r = 0; r < s.nRuns; r++) s.pattern = s.pattern << 20 | (uint64_t)s.run[r][0] << 10 | (uint64_t)s.run[r][1];
}

static bool IRAM_ATTR fill(esp_lcd_panel_handle_t, void *bb, int pos_px, int len_bytes, void *) {
  const uint32_t c0 = esp_cpu_get_cycle_count();
  if (pos_px == 0) {   // frame start: show the newest finished source
    portENTER_CRITICAL_ISR(&mux);
    if (readySrc >= 0) { scanSrc = readySrc; readySrc = -1; }
    portEXIT_CRITICAL_ISR(&mux);
  }
  const Src &s = srcs[scanSrc];
  int slot = bb == bbPtr[0] ? 0 : 1;
  if (!bbPtr[0]) { bbPtr[0] = bb; slot = 0; } else if (slot && !bbPtr[1]) bbPtr[1] = bb;
  if (bbPattern[slot] != s.pattern) { memset(bb, 0, len_bytes); bbPattern[slot] = s.pattern; }
  uint16_t *const out = (uint16_t *)bb;
  const int l0 = pos_px / LCD_H_RES, n = len_bytes / (2 * LCD_H_RES);
  int16_t xs[BB_LINES];   // canvas column of each scan line in this fill
  for (int k = 0; k < n; k++) xs[k] = colOf[USB_LEFT ? LCD_V_RES - 1 - (l0 + k) : l0 + k];
  for (int r = 0; r < s.nRuns; r++)
    for (int b = s.run[r][0]; b < s.run[r][1]; b++) {   // row by row: its BB_LINES pixels are adjacent in the strip
      const uint16_t *src = s.row[b];
      uint16_t *o = out + (USB_LEFT ? b : LCD_H_RES - 1 - b);
      for (int k = 0; k < n; k++, o += LCD_H_RES) *o = __builtin_bswap16(src[xs[k]]);
    }
  fillCycles += esp_cpu_get_cycle_count() - c0;
  return false;
}

bool display_init(void) {
  for (int i = 0; i < SETS; i++) for (int k = 0; k < 2; k++) {
    strips[i][k] = (uint16_t *)heap_caps_malloc(STRIP_BYTES, MALLOC_CAP_SPIRAM);
    if (!strips[i][k]) { log_e("strip buf alloc failed"); return false; }
  }
  esp_lcd_rgb_panel_config_t cfg;
  panel_bringup(cfg);
  cfg.num_fbs = 0;
  cfg.bounce_buffer_size_px = BB_LINES * LCD_H_RES;
  cfg.flags.no_fb = 1;
  if (esp_lcd_new_rgb_panel(&cfg, &panel) != ESP_OK) { log_e("rgb panel alloc failed"); return false; }
  esp_lcd_rgb_panel_event_callbacks_t cbs = {};
  cbs.on_bounce_empty = fill;
  ESP_ERROR_CHECK(esp_lcd_rgb_panel_register_event_callbacks(panel, &cbs, nullptr));
  ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
  ESP_ERROR_CHECK(esp_lcd_panel_init(panel));   // scanning starts: srcs[FRAME_SRC] has no rows yet = black
  backlight_on();
  return true;
}

void display_next_strips(uint16_t *s[2]) {
  portENTER_CRITICAL(&mux);
  for (int i = 0; i < SETS; i++) if (i != scanSrc && i != readySrc) { backSet = i; break; }
  portEXIT_CRITICAL(&mux);
  pushed = 0;
  s[0] = strips[backSet][0]; s[1] = strips[backSet][1];
}

// A strip of the set display_next_strips handed out is finished; the second one makes the set the next frame's.
void display_push_strip_async(const uint16_t *buf, int y0, int rows, const int16_t *rowMap) {
  const int k = buf == strips[backSet][0] ? 0 : buf == strips[backSet][1] ? 1 : -1;
  if (k < 0) return;
  pushY0[k] = (int16_t)y0; pushRows = (int16_t)rows; pushMap[k] = rowMap; pushed |= 1 << k;
  if (pushed != 3) return;
  Src &s = srcs[backSet];   // neither scanned nor ready: the ISR does not read it
  for (int b = 0; b < LCD_H_RES; b++) {
    const int y = rowOf[b];
    s.row[b] = nullptr;
    for (int t = 0; t < 2; t++)
      if (y >= pushY0[t] && y < pushY0[t] + pushRows)
        s.row[b] = strips[backSet][t] + (size_t)(pushMap[t] ? pushMap[t][y - pushY0[t]] : y - pushY0[t]) * PANEL_W;
  }
  finishSrc(s);
  portENTER_CRITICAL(&mux);
  readySrc = backSet;
  portEXIT_CRITICAL(&mux);
  pushed = 0;
}
const bool display_push_any_core = false;   // the second push of a set hands it over; a new set every frame
int display_bands(int) { return 0; }
void display_wait_pending(int) {}
void display_wait_all(void) {}
uint32_t display_busy_cycles(void) { return fillCycles; }

// The whole canvas `fb` (PANEL_W x PANEL_H, byte-swapped, kept by the caller: later drawing into it shows too)
// becomes what is scanned from the next frame on, until strips are pushed again.
void display_push_frame(const uint16_t *fb) {
  if (fb != frameSrc) {   // main pushes the same canvas every time: built once, at the first push, while the
    Src &s = srcs[FRAME_SRC];   // boot's black is scanned (rows before runs, on the ISR's core: a frame shows black or this)
    for (int b = 0; b < LCD_H_RES; b++) s.row[b] = fb + (size_t)rowOf[b] * PANEL_W;
    finishSrc(s);
    frameSrc = fb;
  }
  portENTER_CRITICAL(&mux);
  readySrc = FRAME_SRC;
  portEXIT_CRITICAL(&mux);
}
void display_push_rows(const uint16_t *fb, int, int) { display_push_frame(fb); }   // the whole canvas: rows are read live

#else   // LCD_SCAN 0: framebuffer + CPU push

static uint16_t *fbuf = NULL;   // LCD_V_RES lines x LCD_H_RES px, native RGB565, PSRAM (owned by the RGB driver)
// Two tube-strip buffers: the liquid face renders into them; a push turns them into fbuf. Internal RAM where they
// fit next to BLE, else PSRAM: decided at build time (-DSTRIPS_INTERNAL=0/1/2 overrides), never a fallback at run
// time. Both fit up to 2 x 85.8 KB (the 536x240 canvas, ~4 KB to spare); one up to 141.7 KB (RENDER_H 288: 13.9 KB
// left with BLE up). A PSRAM strip renders ~1.4x slower than an internal one, and two of them slow each other:
// RENDER_H 240 benched 28.0 fps with one internal vs 21.1 with none, 288 23.3 vs 17.0 (2026-10-27, preset 1).
#define STRIP_ROWS TUBE_HEIGHT_MAX
#define STRIP_BYTES ((size_t)PANEL_W * STRIP_ROWS * 2)
// Since the 64 KB data cache (-32 KB) and the 2 x 26 KB bounce buffers, ~72 KB stay free at native and no strip
// fits any more (240 rows: 98 KB): both in PSRAM by default.
#ifndef STRIPS_INTERNAL
#define STRIPS_INTERNAL 0
#endif
static uint16_t *strips[2];
static int16_t bStart[PANEL_H + 1];   // canvas row y covers face rows [bStart[y], bStart[y + 1])
static int32_t srcOff[2][LCD_H_RES];  // turn_rows scratch per core (either core pushes): strip offset of face row b
// A canvas a strip is pushed from: size and its face maps (colOf / rowOf / bStart as above).
struct Canvas { int W, H; const int16_t *colOf, *rowOf, *bStart; };
static const Canvas MAIN = {PANEL_W, PANEL_H, colOf, rowOf, bStart};
#ifdef AB_COMPARE   // the A/B face's second canvas (render_ab.cpp): AB_COMPARE rows of the panel's aspect
#define AB_W (AB_COMPARE * LCD_PANEL_W / LCD_PANEL_H)
static int16_t abColOf[LCD_V_RES], abRowOf[LCD_H_RES], abBStart[AB_COMPARE + 1];
static const Canvas AB = {AB_W, AB_COMPARE, abColOf, abRowOf, abBStart};
#endif

// Create and start the panel on core 0: the driver's ISR (the bounce-buffer refill, ~6 ms a frame) runs on the core
// that allocated it, and core 0's hours render is the lighter one (core 1 also runs the loop and the push).
#ifndef LCD_ISR_CORE
#define LCD_ISR_CORE 0
#endif
struct PanelJob { const esp_lcd_rgb_panel_config_t *cfg; bool ok; TaskHandle_t caller; };
static void panelTask(void *arg) {
  PanelJob &j = *(PanelJob *)arg;
  j.ok = esp_lcd_new_rgb_panel(j.cfg, &panel) == ESP_OK && esp_lcd_panel_reset(panel) == ESP_OK && esp_lcd_panel_init(panel) == ESP_OK;
  xTaskNotifyGive(j.caller);
  vTaskDelete(nullptr);
}
static bool create_panel(const esp_lcd_rgb_panel_config_t &cfg) {
  PanelJob j = {&cfg, false, xTaskGetCurrentTaskHandle()};
  if (xTaskCreatePinnedToCore(panelTask, "lcd-init", 4096, &j, 5, nullptr, LCD_ISR_CORE) != pdPASS) return false;
  ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
  return j.ok;
}

bool display_init(void) {
  for (int i = 0; i < 2; i++) {
    strips[i] = (uint16_t *)heap_caps_malloc(STRIP_BYTES, i < STRIPS_INTERNAL ? MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT : MALLOC_CAP_SPIRAM);
    if (!strips[i]) { log_e("strip buf alloc failed"); return false; }
  }
  for (int y = 0; y <= PANEL_H; y++) bStart[y] = (int16_t)((y * LCD_H_RES + PANEL_H - 1) / PANEL_H);
#ifdef AB_COMPARE
  for (int a = 0; a < LCD_V_RES; a++) abColOf[a] = (int16_t)(a * AB_W / LCD_V_RES);
  for (int b = 0; b < LCD_H_RES; b++) abRowOf[b] = (int16_t)(b * AB_COMPARE / LCD_H_RES);
  for (int y = 0; y <= AB_COMPARE; y++) abBStart[y] = (int16_t)((y * LCD_H_RES + AB_COMPARE - 1) / AB_COMPARE);
#endif
  esp_lcd_rgb_panel_config_t cfg;
  panel_bringup(cfg);
  cfg.num_fbs = 1;
  // The DMA streams two internal bounce buffers the driver refills from the PSRAM framebuffer (sequential copies in
  // its ISR): read straight from PSRAM, the DMA fell behind once the 64 KB / 64-B-line cache made the CPU's PSRAM
  // bursts longer, and the picture twitched sideways (2026-10-27; 14 MHz did not help). 10-line buffers still
  // twitched now and then, 41 lines are steady by eye. The refill costs the ISR's core ~6 ms a frame.
  // FB_BOUNCE_LINES 0 = DMA from PSRAM as before.
#ifndef FB_BOUNCE_LINES
#define FB_BOUNCE_LINES 41   // 820 / (2 x 41) whole, as the driver wants; 2 x 26 KB internal
#endif
  cfg.bounce_buffer_size_px = FB_BOUNCE_LINES * LCD_H_RES;
  cfg.flags.fb_in_psram = 1;
  if (!create_panel(cfg)) { log_e("rgb panel alloc failed"); return false; }
  void *fb0 = NULL;
  ESP_ERROR_CHECK(esp_lcd_rgb_panel_get_frame_buffer(panel, 1, &fb0));
  fbuf = (uint16_t *)fb0;
  memset(fbuf, 0, (size_t)LCD_H_RES * LCD_V_RES * 2);
  esp_cache_msync(fbuf, (size_t)LCD_H_RES * LCD_V_RES * 2, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
  backlight_on();
  return true;
}

void display_next_strips(uint16_t *s[2]) { s[0] = strips[0]; s[1] = strips[1]; }
uint32_t display_busy_cycles(void) { return 0; }

// Turn `rows` canvas rows from y0 on (src: PANEL_W wide, byte-swapped) into fbuf, scaled to the face: they cover
// face rows [b0, b1), a contiguous run on each of the 820 scan lines (one face column per line). Bound by PSRAM
// traffic (each run fills and writes back its cache lines while the LCD DMA scans out), not by the loop: ~3.7 ms
// per 536x72 strip at 1:1; 32-bit stores gain nothing, and two pushes at once on both cores are slower than one
// after the other (2026-10-28: 24 ms for both strips split by columns vs 18.8 serial), so main.cpp runs each push
// next to the other core's render instead. Either core may push (srcOff per core).
// One framebuffer, written while it is scanned: a moving edge could be cut where push and beam cross, not visible on
// a sloshing board (2026-10-27); a VSYNC-locked push would cap the fps at 46 / 23.
static void turn_rows(const uint16_t *src, int y0, int rows, const int16_t *rowMap = nullptr, const Canvas &cv = MAIN) {
  if (rows <= 0) return;
  const int b0 = cv.bStart[y0], n = cv.bStart[y0 + rows] - b0;
  if (n <= 0) return;
#if USB_LEFT
  uint16_t *const line0 = fbuf + (size_t)(LCD_V_RES - 1) * LCD_H_RES + b0;   // face column a = 0, row b0
#define LINE(a) (line0 - (size_t)(a) * LCD_H_RES)
#define PIX(d, r) (d)[r]
  uint16_t *const lo = fbuf + b0;
#else
  uint16_t *const line0 = fbuf + (LCD_H_RES - 1 - b0);
#define LINE(a) (line0 + (size_t)(a) * LCD_H_RES)
#define PIX(d, r) (d)[-(r)]
  uint16_t *const lo = fbuf + (LCD_H_RES - b0 - n);
#endif
#if PANEL_W == LCD_V_RES && PANEL_H == LCD_H_RES
  if (!rowMap && &cv == &MAIN) {
    for (int a = 0; a < LCD_V_RES; a++) {
      uint16_t *d = LINE(a); const uint16_t *s = src + a;
      for (int r = 0; r < n; r++) PIX(d, r) = __builtin_bswap16(s[r * PANEL_W]);
    }
  } else
#endif
  {
  int32_t *const off = srcOff[xPortGetCoreID()];
  for (int r = 0; r < n; r++) { const int sr = cv.rowOf[b0 + r] - y0; off[r] = (rowMap ? rowMap[sr] : sr) * cv.W; }
  for (int a = 0; a < LCD_V_RES; a++) {
    uint16_t *d = LINE(a); const uint16_t *s = src + cv.colOf[a];
    for (int r = 0; r < n; r++) PIX(d, r) = __builtin_bswap16(s[off[r]]);
  }
  }
#undef LINE
#undef PIX
  // The LCD DMA reads PSRAM behind the data cache: write the touched lines back.
  esp_cache_msync(lo, ((size_t)(LCD_V_RES - 1) * LCD_H_RES + n) * 2, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
}

const bool display_push_any_core = true;   // a CPU copy into fbuf; display_next_strips: always strips[0], strips[1]
void display_push_strip_async(const uint16_t *buf, int y0, int rows, const int16_t *rowMap) { turn_rows(buf, y0, rows, rowMap); }
#ifdef AB_COMPARE
void display_push_strip_ab(const uint16_t *buf, int y0, int rows, const int16_t *rowMap) { turn_rows(buf, y0, rows, rowMap, AB); }
#endif
int display_bands(int) { return 0; }
void display_wait_pending(int) {}
void display_wait_all(void) {}

// Stage rows of a PSRAM framebuffer through a strip (sequential reads), then turn them.
void display_push_rows(const uint16_t *fb, int y0, int y1) {
  for (int y = y0; y < y1; y += STRIP_ROWS) {
    int rows = min(STRIP_ROWS, y1 - y);
    memcpy(strips[0], fb + (size_t)y * PANEL_W, (size_t)rows * PANEL_W * 2);
    turn_rows(strips[0], y, rows);
  }
}

void display_push_frame(const uint16_t *fb) { display_push_rows(fb, 0, PANEL_H); }

#endif   // LCD_SCAN

void display_set_brightness(uint8_t v) { ledcWrite(PIN_BL, 255 - v); }   // 0..255; ledcWrite takes 255 as fully high = dark

void display_set_hbm(bool) {}   // LCD: no high-brightness mode
