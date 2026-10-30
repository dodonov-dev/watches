#include "display.h"
#include <Arduino.h>
#include <string.h>
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "esp_heap_caps.h"
#include "esp_lcd_sh8601.h"
#include "layout.h"

// Pins — from Waveshare demo 03_LVGL_V8_Test and arduino-esp32 variant
// waveshare_esp32_s3_touch_amoled_191/pins_arduino.h (identical).
#define PIN_LCD_CS     6
#define PIN_LCD_PCLK   47
#define PIN_LCD_D0     18
#define PIN_LCD_D1     7
#define PIN_LCD_D2     48
#define PIN_LCD_D3     5
#define PIN_LCD_RST    17
#define LCD_HOST       SPI2_HOST

// USB_LEFT=1 (default): landscape with USB-C on the left (180° from Waveshare demo's 0xF0).
#ifndef USB_LEFT
#define USB_LEFT 1
#endif
#define MADCTL_VAL (USB_LEFT ? 0x30 : 0xF0)

// Verbatim from Waveshare 03_LVGL_V8_Test.ino (except MADCTL value and the explicit HBM off)
static const sh8601_lcd_init_cmd_t lcd_init_cmds[] = {
  {0x11, (uint8_t []){0x00}, 0, 120},
  {0x36, (uint8_t []){MADCTL_VAL}, 1, 0},   // orientation, see USB_LEFT
  {0x3A, (uint8_t []){0x55}, 1, 0},  // 16-bit RGB565
  {0x2A, (uint8_t []){0x00,0x00,0x02,0x17}, 4, 0},
  {0x2B, (uint8_t []){0x00,0x00,0x00,0xEF}, 4, 0},
  {0x51, (uint8_t []){0x00}, 1, 10},
  {0xB0, (uint8_t []){0x04}, 1, 0},  // HBM off: the bit survives RESX, only a power cycle or this clears it
  {0x29, (uint8_t []){0x00}, 0, 10},
  {0x51, (uint8_t []){0xFF}, 1, 0},
};

static esp_lcd_panel_io_handle_t io_handle = NULL;
static esp_lcd_panel_handle_t panel = NULL;
static SemaphoreHandle_t done_sem = NULL;

// Two tube-strip buffers in internal DMA RAM. The liquid face renders straight into them and the
// panel DMA reads them directly; full-frame pushes from the PSRAM canvas are staged through them too.
#define BAND_ROWS 40                 // max rows per DMA transfer (spi max_transfer_sz)
#define STRIP_ROWS TUBE_HEIGHT_MAX
static uint16_t *strips[2];
static int pending = 0;

static bool IRAM_ATTR on_trans_done(esp_lcd_panel_io_handle_t, esp_lcd_panel_io_event_data_t *, void *) {
  BaseType_t hp = pdFALSE;
  xSemaphoreGiveFromISR(done_sem, &hp);
  return hp == pdTRUE;
}

bool display_init(void) {
  done_sem = xSemaphoreCreateCounting(32, 0);
  for (int i = 0; i < 2; i++) {
    strips[i] = (uint16_t *)heap_caps_malloc(PANEL_W * STRIP_ROWS * 2, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (!strips[i]) { log_e("band buf alloc failed"); return false; }
  }
  const spi_bus_config_t buscfg = SH8601_PANEL_BUS_QSPI_CONFIG(PIN_LCD_PCLK, PIN_LCD_D0, PIN_LCD_D1,
                                                               PIN_LCD_D2, PIN_LCD_D3, PANEL_W * BAND_ROWS * 2);
  ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &buscfg, SPI_DMA_CH_AUTO));

  const esp_lcd_panel_io_spi_config_t io_config = SH8601_PANEL_IO_QSPI_CONFIG(PIN_LCD_CS, on_trans_done, NULL);
  sh8601_vendor_config_t vendor_config = {
    .init_cmds = lcd_init_cmds,
    .init_cmds_size = sizeof(lcd_init_cmds) / sizeof(lcd_init_cmds[0]),
    .flags = { .use_qspi_interface = 1 },
  };
  ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST, &io_config, &io_handle));

  const esp_lcd_panel_dev_config_t panel_config = {
    .reset_gpio_num = PIN_LCD_RST,
    .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
    .bits_per_pixel = 16,
    .vendor_config = &vendor_config,
  };
  ESP_ERROR_CHECK(esp_lcd_new_panel_sh8601(io_handle, &panel_config, &panel));
  ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
  ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
  // Orientation comes from MADCTL (0x36 = 0xF0) in the init sequence; the sh8601
  // driver does not support swap_xy, so no rotation calls here.
  ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));
  return true;
}

void display_next_strips(uint16_t *s[2]) { s[0] = strips[0]; s[1] = strips[1]; }
uint32_t display_busy_cycles(void) { return 0; }
DisplayRefill display_refill_health(void) { return {0, 0, 0}; }

const bool display_row_map = false;   // the panel DMA reads strip rows as they are
void display_push_strip_async(const uint16_t *buf, int y0, int rows, const int16_t *) {
  for (int y = 0; y < rows; y += BAND_ROWS) {
    int n = min(BAND_ROWS, rows - y);
    esp_lcd_panel_draw_bitmap(panel, 0, y0 + y, PANEL_W, y0 + y + n, buf + (size_t)y * PANEL_W);
    pending++;
  }
}
const bool display_push_any_core = false;   // one SPI queue, the strips reused once their bands are out
int display_bands(int rows) { return (rows + BAND_ROWS - 1) / BAND_ROWS; }
void display_wait_pending(int n) {
  while (pending > n) { xSemaphoreTake(done_sem, portMAX_DELAY); pending--; }
}
void display_wait_all(void) { display_wait_pending(0); }

// Stage rows of a PSRAM framebuffer through the strips, alternating, up to STRIP_ROWS per chunk.
void display_push_rows(const uint16_t *fb, int y0, int y1) {
  display_wait_all();
  int b = 0;
  for (int y = y0; y < y1; y += STRIP_ROWS) {
    int rows = min(STRIP_ROWS, y1 - y);
    memcpy(strips[b], fb + (size_t)y * PANEL_W, (size_t)rows * PANEL_W * 2);
    display_push_strip_async(strips[b], y, rows);
    b ^= 1;
    display_wait_all();   // simple and safe: the next memcpy may target either strip
  }
}

void display_push_frame(const uint16_t *fb) { display_push_rows(fb, 0, PANEL_H); }

void display_set_brightness(uint8_t v) {
  esp_lcd_panel_io_tx_param(io_handle, 0x02000000 | (0x51 << 8), &v, 1);
}

void display_set_hbm(bool on) {
  uint8_t v = on ? 0x06 : 0x04;   // bit2 is a fixed '1' in the datasheet, bit1 = HBM_EN
  esp_lcd_panel_io_tx_param(io_handle, 0x02000000 | (0xB0 << 8), &v, 1);
}

