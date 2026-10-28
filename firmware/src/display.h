#pragma once
#include <stdint.h>
#include <stdbool.h>

// Panel backend, one per board (platformio.ini picks the file); both speak the PANEL_W x PANEL_H canvas of layout.h:
//   display.cpp         RM67162 AMOLED 536x240 over QSPI, via Waveshare's esp_lcd_sh8601 driver
//                       (same command set; init sequence taken verbatim from Waveshare demo).
//   display_lcd316.cpp  ST7701 RGB LCD 320x820, no framebuffer: an ISR fills each scan line from the shown strips
//                       (triple-buffered in PSRAM) or canvas; pushes hand over, so the wait calls complete at once.
bool display_init(void);
// Push a full 536x240 RGB565 frame (buffer may live in PSRAM). Blocking.
// NOTE: the panel takes big-endian RGB565; the framebuffer must already hold byte-swapped
// pixels (PsramCanvas in main.cpp does this), so the copy to DMA memory is a plain memcpy.
void display_push_frame(const uint16_t *fb);
// Push a horizontal band [y0, y1) of a full-width framebuffer (staged through the strips, blocking).
void display_push_rows(const uint16_t *fb, int y0, int y1);
// The two TUBE_HEIGHT_MAX-row strip buffers (hours, minutes) to render the next frame into, owned by the display
// module: AMOLED the same two every frame (internal DMA RAM: wait for their previous push first); LCD a set neither
// scanned nor waiting to be (PSRAM). Call once per frame, then push both.
void display_next_strips(uint16_t *strip[2]);
// CPU cycles spent so far feeding the panel from an ISR (LCD scan-line fill; 0 on the AMOLED), a wrapping counter.
uint32_t display_busy_cycles(void);
void display_set_brightness(uint8_t v);   // 0..255 (AMOLED: cmd 0x51; LCD: backlight PWM)
// RM67162 High Brightness Mode (SetHBMMode B0h, bit1 HBM_EN). On this module it is not a usable
// brightness step: the image goes bright cyan and a lit face trips the brownout detector. Kept for
// experiments only (serial 'H'); never enable it on the boot path. No-op on the LCD.
void display_set_hbm(bool on);
// Queue a push of `rows` full-width rows starting at panel row y0, read by DMA straight from
// `buf` (must be internal DMA-capable RAM, byte-swapped pixels). Returns immediately; call
// display_wait_all() before `buf` is modified again. Not to be mixed with display_push_rows in flight.
// rowMap (backends with display_row_map only): strip row r shows buf row rowMap[r] (the deferred whole-tube lens,
// render.h renderTube); nullptr = rows as they are.
void display_push_strip_async(const uint16_t *buf, int y0, int rows, const int16_t *rowMap = nullptr);
extern const bool display_row_map;
// true: display_push_strip_async may run on either core, while the other one renders (not two pushes at once), and
// display_next_strips hands out the same two strips every frame, so a strip pushed late still holds its frame (LCD
// framebuffer push). false: push both strips from the loop after both renders, in order (AMOLED: one SPI DMA queue).
extern const bool display_push_any_core;
#ifdef AB_COMPARE
// The A/B face's second strip, from the AB_COMPARE-row canvas of render_ab.cpp (LCD push path only).
void display_push_strip_ab(const uint16_t *buf, int y0, int rows, const int16_t *rowMap);
#endif   // the push can remap strip rows (LCD): main lets the renderer defer its lens
void display_wait_all(void);
// Number of DMA transfers a push of `rows` rows is split into.
int display_bands(int rows);
// Block until at most `n` transfers are still in flight. Transfers complete in queue order, so
// after display_wait_pending(display_bands(rowsB)) a strip A pushed before strip B is free again.
void display_wait_pending(int n);
