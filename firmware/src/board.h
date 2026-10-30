// Per-board pins and IMU frame (the display backends keep their own pins: display.cpp, display_lcd316.cpp).
// Default: Waveshare ESP32-S3-AMOLED-1.91; -DBOARD_LCD316: Waveshare ESP32-S3-LCD-3.16 (see platformio.ini).
#pragma once
#include "layout.h"

#define BOARD_STR_(x) #x
#define BOARD_STR(x)  BOARD_STR_(x)
#ifdef BOARD_LCD316
#define BOARD_NAME   "lcd316"
#if LCD_FILL
#define BOARD_TAG    "lcd316@" BOARD_STR(RENDER_H) "f"   // board + canvas rows (+ f: LCD_FILL), as the sim names it (spec/layout.ts BOARD_TAG)
#else
#define BOARD_TAG    "lcd316@" BOARD_STR(RENDER_H)
#endif
#define BOARD_PANEL_W LCD_PANEL_W
#define BOARD_PANEL_H LCD_PANEL_H
#define PIN_I2C_SDA  15      // QMI8658 + PCF85063 RTC (0x51)
#define PIN_I2C_SCL  7
#define HAS_RTC      1       // PCF85063: keeps time while powered (SH1.0 header for a backup cell), rtc.cpp
#define PIN_BAT_ADC  4       // LiPo through 200k / 200k
#else
#define BOARD_NAME   "amoled191"
#define BOARD_TAG    BOARD_NAME
#define BOARD_PANEL_W PANEL_W
#define BOARD_PANEL_H PANEL_H
#define PIN_I2C_SDA  40      // QMI8658
#define PIN_I2C_SCL  39
#define HAS_RTC      0
#endif

// imu_read turns the sample into the AMOLED-1.91 board's IMU frame, in which the axis mapping of layout.h /
// layout.ts was measured, so the `i` stream, the sim and the physics read every board alike.
// IMU_REF(v, a) = component a (0 = x, 1 = y, 2 = z) of the reference-frame vector, from this board's raw v[3].
#ifdef BOARD_LCD316
// Measured 2026-10-27, USB-C on the left: screen up az = -1 (z into the screen), lifting the USB-C end ay < 0,
// lifting the far long edge ax > 0 -> the reference frame is this one turned 180 degrees about y.
#define IMU_REF(v, a) ((a) == 1 ? (v)[1] : -(v)[a])
#else
#define IMU_REF(v, a) ((v)[a])
#endif
