#pragma once
#include <stdint.h>
#include <stdbool.h>

// Panel backend, one per board (platformio.ini picks the file); both speak the PANEL_W x PANEL_H canvas of layout.h:
//   display.cpp         RM67162 AMOLED 536x240 over QSPI, via Waveshare's esp_lcd_sh8601 driver
//                       (same command set; init sequence taken verbatim from Waveshare demo).
//   display_lcd316.cpp  ST7701 RGB LCD 320x820 (PSRAM framebuffer, canvas shown 1:1 centred, turned a quarter):
//                       pushes are synchronous copies, so the async / wait calls below complete at once there.
bool display_init(void);
// Push a full 536x240 RGB565 frame (buffer may live in PSRAM). Blocking.
// NOTE: the panel takes big-endian RGB565; the framebuffer must already hold byte-swapped
// pixels (PsramCanvas in main.cpp does this), so the copy to DMA memory is a plain memcpy.
void display_push_frame(const uint16_t *fb);
// Push a horizontal band [y0, y1) of a full-width framebuffer (staged through the strips, blocking).
void display_push_rows(const uint16_t *fb, int y0, int y1);
// The two TUBE_HEIGHT_MAX-row strip buffers (internal RAM, DMA-capable on the AMOLED) owned by the display module.
uint16_t *display_strip(int i);
void display_set_brightness(uint8_t v);   // 0..255 (AMOLED: cmd 0x51; LCD: backlight PWM)
// RM67162 High Brightness Mode (SetHBMMode B0h, bit1 HBM_EN). On this module it is not a usable
// brightness step: the image goes bright cyan and a lit face trips the brownout detector. Kept for
// experiments only (serial 'H'); never enable it on the boot path. No-op on the LCD.
void display_set_hbm(bool on);
// Queue a push of `rows` full-width rows starting at panel row y0, read by DMA straight from
// `buf` (must be internal DMA-capable RAM, byte-swapped pixels). Returns immediately; call
// display_wait_all() before `buf` is modified again. Not to be mixed with display_push_rows in flight.
void display_push_strip_async(const uint16_t *buf, int y0, int rows);
void display_wait_all(void);
// Number of DMA transfers a push of `rows` rows is split into.
int display_bands(int rows);
// Block until at most `n` transfers are still in flight. Transfers complete in queue order, so
// after display_wait_pending(display_bands(rowsB)) a strip A pushed before strip B is free again.
void display_wait_pending(int n);
