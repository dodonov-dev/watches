// Liquid Watch — single source of truth for panel layout.
// Mirrored in spec/layout.ts. Landscape, origin top-left.
// The face renders into a PANEL_W x PANEL_H canvas. Params and presets are in design px: the AMOLED's 536x240
// canvas (DESIGN_H rows). A board with a taller canvas scales every px param by PX_SCALE (sim board.ts
// boardParams, firmware main.cpp), so a preset keeps its proportions on every board.
// Boards (-D in platformio.ini; LW_BOARD / LW_RES for the tools, ?board= / ?res= in the sim):
//   default        Waveshare ESP32-S3-AMOLED-1.91: canvas = panel, 536x240, PX_SCALE 1
//   BOARD_LCD316   Waveshare ESP32-S3-LCD-3.16, panel 820x320 (LCD_PANEL_W x LCD_PANEL_H): the canvas has the
//                  panel's aspect, RENDER_H rows (default 320 = native; 240 / 256 / 288 render fewer pixels and
//                  are upscaled to the panel on push, display_lcd316.cpp)
#pragma once

#define DESIGN_H           240   // canvas rows the params / presets are tuned on
#define DESIGN_TUBE_HEIGHT_MAX 80   // largest tubeHeight a preset may ask for, design px

#ifdef BOARD_LCD316
#define LCD_PANEL_W        820   // along the tubes (the LCD's 820 scan lines)
#define LCD_PANEL_H        320   // across them (its 320-px lines)
#ifndef RENDER_H
#define RENDER_H           320
#endif
#if RENDER_H % 16 || RENDER_H < DESIGN_H || RENDER_H > LCD_PANEL_H
#error "RENDER_H: a multiple of 16 in 240..320 (the canvas keeps the panel's 41:16 aspect in whole pixels)"
#endif
#define PANEL_W            (RENDER_H * LCD_PANEL_W / LCD_PANEL_H)
#define PANEL_H            RENDER_H
#else
#define PANEL_W            536
#define PANEL_H            240
#endif

#define PX_SCALE           ((float)PANEL_H / DESIGN_H)   // canvas px per design px (1 on the AMOLED)
#define TUBE_LENGTH_PX     PANEL_W   // full width; leather may mask the outer ~10px
// Strip buffer rows: the largest preset tube at this scale. Defaults below; runtime values come from params
// tubeHeight / hoursY / minutesY (design px, scaled).
#define TUBE_HEIGHT_MAX    ((DESIGN_TUBE_HEIGHT_MAX * PANEL_H + DESIGN_H - 1) / DESIGN_H)
#define TUBE_HEIGHT_PX     (72 * PANEL_H / DESIGN_H)    // ≈ 6 mm on the AMOLED at 0.083 mm/px
#define HOURS_TUBE_Y       0                            // along the top edge
#define MINUTES_TUBE_Y     (PANEL_H - TUBE_HEIGHT_PX)   // along the bottom edge
#define BRIDGE_Y0          TUBE_HEIGHT_PX               // bridge zone between the tubes must stay pure black
#define BRIDGE_Y1          MINUTES_TUBE_Y

// Colors (RGB888 reference; RGB565 derived, verify on AMOLED)
#define LIQUID_RGB888      0x5DCAA5
#define LIQUID_HI_RGB888   0x9FE1CB
#define BG_RGB888          0x000000

// mm per canvas px for the physical meniscus (tube radius vs capillary length): the AMOLED's pitch per design
// px, so a scaled bore stays the same bore in mm and the meniscus keeps its shape on every board.
#define DESIGN_MM_PER_PX   0.083f
#define MM_PER_PX          (DESIGN_MM_PER_PX / PX_SCALE)

#define RGB565(r,g,b)      ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))
#define LIQUID_RGB565      RGB565(0x5D,0xCA,0xA5)   // 0x5E54
#define LIQUID_HI_RGB565   RGB565(0x9F,0xE1,0xCB)

// ---- IMU axis mapping (QMI8658, measured 2026-08-20 with USB_LEFT=1 orientation) ----
// Board flat, screen up:  a ≈ (+0.03, -0.07, +0.94) g   (|a| ≈ 0.94 → accel scale ~6 % low, normalize)
// Lift USB-C (left) end:  ay → negative   → IMU Y is ALONG the tube; liquid flows toward the RIGHT.
// Lift far/top long edge: ax → negative   → IMU X is ACROSS the tube (toward viewer positive).
// Z points out of the screen. Other boards turn their IMU into this frame (board.h IMU_REF).
#define IMU_AXIS_ALONG_TUBE   1      // 0=x 1=y 2=z
#define IMU_ALONG_TUBE_SIGN  -1      // tilt_along = IMU_ALONG_TUBE_SIGN * ay  → positive = right end down
#define IMU_AXIS_ACROSS_TUBE  0
#define IMU_ACROSS_TUBE_SIGN -1      // positive = top (far) edge up
