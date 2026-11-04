// Per-board pins and IMU frame (the display backends keep their own pins: display.cpp, display_lcd316.cpp).
// Default: Waveshare ESP32-S3-AMOLED-1.91; -DBOARD_LCD316: Waveshare ESP32-S3-LCD-3.16 (see platformio.ini).
#pragma once
#include "layout.h"

#define BOARD_STR_(x) #x
#define BOARD_STR(x)  BOARD_STR_(x)
#if TUBE_COUNT == 3
#define BOARD_TUBES_ "+t3"   // a three-tube face (layout.h TUBE_COUNT)
#else
#define BOARD_TUBES_ ""
#endif
#ifdef BOARD_LCD316
#define BOARD_NAME   "lcd316"
// Board + canvas rows + tube widths, as the sim names it (spec/layout.ts BOARD_TAG / resTag): no suffix all narrow,
// f all wide, else f + the wide tubes' letters in h / m / s order: fh the hours tube wide, fm the minutes tube wide; three
// tubes also fs, fhm, fhs, fms (layout.h LCD_FILL_H / LCD_FILL_M / LCD_FILL_S).
#if TUBE_COUNT == 3
#define BOARD_WIDE_ALL_ (LCD_FILL_H && LCD_FILL_M && LCD_FILL_S)
#define BOARD_WIDE_ANY_ (LCD_FILL_H || LCD_FILL_M || LCD_FILL_S)
#if LCD_FILL_S
#define BOARD_WIDE_S_ "s"
#else
#define BOARD_WIDE_S_ ""
#endif
#else
#define BOARD_WIDE_ALL_ (LCD_FILL_H && LCD_FILL_M)
#define BOARD_WIDE_ANY_ (LCD_FILL_H || LCD_FILL_M)
#define BOARD_WIDE_S_ ""
#endif
#if LCD_FILL_H
#define BOARD_WIDE_H_ "h"
#else
#define BOARD_WIDE_H_ ""
#endif
#if LCD_FILL_M
#define BOARD_WIDE_M_ "m"
#else
#define BOARD_WIDE_M_ ""
#endif
#if BOARD_WIDE_ALL_
#define BOARD_WIDE_  "f"
#elif BOARD_WIDE_ANY_
#define BOARD_WIDE_  "f" BOARD_WIDE_H_ BOARD_WIDE_M_ BOARD_WIDE_S_
#else
#define BOARD_WIDE_  ""
#endif
#define BOARD_TAG    "lcd316@" BOARD_STR(RENDER_H) BOARD_WIDE_ BOARD_TUBES_
#define BOARD_PANEL_W LCD_PANEL_W
#define BOARD_PANEL_H LCD_PANEL_H
#define PIN_I2C_SDA  15      // QMI8658 + PCF85063 RTC (0x51)
#define PIN_I2C_SCL  7
#define HAS_RTC      1       // PCF85063: keeps time while powered (SH1.0 header for a backup cell), rtc.cpp
#define PIN_BAT_ADC  4       // LiPo through 200k / 200k
#else
#define BOARD_NAME   "amoled191"
#define BOARD_TAG    BOARD_NAME BOARD_TUBES_
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
