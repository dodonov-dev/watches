// Waveshare ESP32-S3-LCD-3.16: ST7701 RGB LCD, 320x820, scanned portrait (320-px lines, 820 lines) out of a
// PSRAM framebuffer by the LCD_CAM peripheral; the panel has no frame memory and cannot rotate. The face keeps
// the 536x240 landscape canvas of layout.h and is shown 1:1, centred: each strip is turned a quarter into the
// framebuffer as it is pushed (synchronous CPU copy; nothing is left in flight, so the wait calls return at once).
// Pins, init sequence and RGB timings from Waveshare's ESP32-S3-LCD-3.16 demo (07_LVGL_V8_Test). LCD CS is
// GPIO0 through R38 in both schematic revisions (the wiki's pin table says IO42).
#include "display.h"
#include <Arduino.h>
#include <string.h>
#include "driver/gpio.h"
#include "esp_lcd_panel_rgb.h"
#include "esp_lcd_panel_ops.h"
#include "esp_heap_caps.h"
#include "esp_cache.h"
#include "esp_rom_sys.h"
#include "layout.h"

#define LCD_H_RES   320   // pixels per scan line: across the landscape face
#define LCD_V_RES   820   // scan lines: along the face
#define OFF_X       ((LCD_V_RES - PANEL_W) / 2)   // canvas placement on the 820x320 face
#define OFF_Y       ((LCD_H_RES - PANEL_H) / 2)

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
// is the end away from USB-C, column 0 the far long edge; the canvas maps to (line, column):
//   USB_LEFT=1: (LCD_V_RES-1 - (x+OFF_X), y+OFF_Y)     USB_LEFT=0: (x+OFF_X, LCD_H_RES-1 - (y+OFF_Y))
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
static uint16_t *fbuf = NULL;   // LCD_V_RES lines x LCD_H_RES px, native RGB565, PSRAM (owned by the RGB driver)

// Two tube-strip buffers (internal RAM): the liquid face renders into them; a push turns them into fbuf.
#define STRIP_ROWS TUBE_HEIGHT_MAX
static uint16_t *strips[2];

bool display_init(void) {
  for (int i = 0; i < 2; i++) {
    strips[i] = (uint16_t *)heap_caps_malloc(PANEL_W * STRIP_ROWS * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!strips[i]) { log_e("strip buf alloc failed"); return false; }
  }
  pinMode(PIN_BL, OUTPUT); digitalWrite(PIN_BL, HIGH);   // dark until the framebuffer is black
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

  esp_lcd_rgb_panel_config_t cfg = {};
  cfg.clk_src = LCD_CLK_SRC_DEFAULT;
  // 386 x 900 clocks per frame -> 46.1 Hz. Waveshare's 18 MHz (51.8 Hz) makes the picture jump sideways and back
  // now and then: the DMA falls behind reading PSRAM (no bounce buffers here) until the restart at VSYNC. 16 and
  // 14 MHz were steady on the board (2026-10-27); 16 keeps the refresh near the ~50 fps render (pinned scene:
  // 50.0 fps vs 50.8 at 14 MHz, which shows only 40 of them).
  cfg.timings.pclk_hz = 16 * 1000 * 1000;
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
  cfg.num_fbs = 1;
  cfg.bounce_buffer_size_px = 0;   // DMA reads PSRAM (bounce buffers: internal RAM we lack + CPU copies); CONFIG_LCD_RGB_RESTART_IN_VSYNC (Arduino libs) heals a drift each frame
  cfg.dma_burst_size = 64;
  cfg.hsync_gpio_num = PIN_HSYNC;
  cfg.vsync_gpio_num = PIN_VSYNC;
  cfg.de_gpio_num = PIN_DE;
  cfg.pclk_gpio_num = PIN_PCLK;
  cfg.disp_gpio_num = -1;
  for (int i = 0; i < 16; i++) cfg.data_gpio_nums[i] = DATA_PINS[i];
  cfg.flags.fb_in_psram = 1;
  if (esp_lcd_new_rgb_panel(&cfg, &panel) != ESP_OK) { log_e("rgb panel alloc failed"); return false; }
  ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
  ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
  void *fb0 = NULL;
  ESP_ERROR_CHECK(esp_lcd_rgb_panel_get_frame_buffer(panel, 1, &fb0));
  fbuf = (uint16_t *)fb0;
  memset(fbuf, 0, (size_t)LCD_H_RES * LCD_V_RES * 2);
  esp_cache_msync(fbuf, (size_t)LCD_H_RES * LCD_V_RES * 2, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
  delay(40);                                         // two scans of black before the backlight comes on
  ledcAttach(PIN_BL, 50000, 8);
  display_set_brightness(0);
  return true;
}

uint16_t *display_strip(int i) { return strips[i & 1]; }

// Turn `rows` canvas rows from y0 on (src: PANEL_W wide, byte-swapped) into fbuf: one canvas column is a
// contiguous run of `rows` pixels on one scan line. Bound by PSRAM traffic (each run fills and writes back
// its cache lines while the LCD DMA scans out), not by the loop: ~3.7 ms per 72-row strip, 32-bit stores
// or pushing the two strips from both cores at once gain nothing. One framebuffer, written while it is scanned:
// a moving edge could be cut where push and beam cross, not visible on a sloshing board (2026-10-27); a VSYNC-locked
// push would cap the fps at 46 / 23.
static void turn_rows(const uint16_t *src, int y0, int rows) {
  if (rows <= 0) return;
#if USB_LEFT
  uint16_t *first = fbuf + (size_t)(LCD_V_RES - 1 - OFF_X) * LCD_H_RES + OFF_Y + y0;
  for (int x = 0; x < PANEL_W; x++) {
    uint16_t *d = first - (size_t)x * LCD_H_RES; const uint16_t *s = src + x;
    for (int r = 0; r < rows; r++) d[r] = __builtin_bswap16(s[r * PANEL_W]);
  }
  uint16_t *lo = first - (size_t)(PANEL_W - 1) * LCD_H_RES;
#else
  uint16_t *first = fbuf + (size_t)OFF_X * LCD_H_RES + (LCD_H_RES - 1 - OFF_Y - y0);
  for (int x = 0; x < PANEL_W; x++) {
    uint16_t *d = first + (size_t)x * LCD_H_RES; const uint16_t *s = src + x;
    for (int r = 0; r < rows; r++) d[-r] = __builtin_bswap16(s[r * PANEL_W]);
  }
  uint16_t *lo = first - (rows - 1);
#endif
  // The LCD DMA reads PSRAM behind the data cache: write the touched lines back.
  esp_cache_msync(lo, ((size_t)(PANEL_W - 1) * LCD_H_RES + rows) * 2, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
}

void display_push_strip_async(const uint16_t *buf, int y0, int rows) { turn_rows(buf, y0, rows); }
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

void display_set_brightness(uint8_t v) { ledcWrite(PIN_BL, 255 - v); }   // 0..255; ledcWrite takes 255 as fully high = dark

void display_set_hbm(bool) {}   // LCD: no high-brightness mode
