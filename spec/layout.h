// Liquid Watch — single source of truth for panel layout.
// Mirrored in spec/layout.ts. Landscape, origin top-left.
// The face renders into a PANEL_W x PANEL_H canvas. Params and presets are in design px: the AMOLED's 536x240
// canvas (DESIGN_H rows). Another board scales every px param by its tube's px scale (sim params.ts boardParams,
// firmware physics.h): with the canvas height (a preset keeps its proportions), or on the LCD by default with the
// pitch (the tube keeps its physical width, below). Each tube has its own scale (TUBE_PX_SCALE(i), 0 = hours).
// Boards (-D in platformio.ini; LW_BOARD / LW_RES for the tools, ?board= / ?res= in the sim):
//   default        Waveshare ESP32-S3-AMOLED-1.91: canvas = panel, 536x240, px scale 1
//   BOARD_LCD316   Waveshare ESP32-S3-LCD-3.16, panel 820x320 (LCD_PANEL_W x LCD_PANEL_H): the canvas has the
//                  panel's aspect, RENDER_H rows (default 320 = native; 240 / 256 / 288 render fewer pixels and
//                  are upscaled to the panel on push, display_lcd316.cpp). Tube width per tube: narrow (LCD_FILL_x
//                  0, the default) = px params at the AMOLED's physical size (a design px = 0.083 mm, the LCD's
//                  pitch 0.0912 mm: 0.910 panel px), the tube still the panel's full length, the rows it leaves
//                  black; wide (1) = scaled with the canvas height (4/3 at native), filling the face as on the
//                  AMOLED. LCD_FILL sets both tubes, LCD_FILL_H / LCD_FILL_M one each. The board tag (`v`, sim
//                  ?res= / LW_RES) says which: lcd316@320 (both narrow), @320f (both wide), @320fh (hours wide),
//                  @320fm (minutes wide).
#pragma once

#define DESIGN_H           240   // canvas rows the params / presets are tuned on
#define DESIGN_TUBE_HEIGHT_MAX 80   // largest tubeHeight a preset may ask for, design px

// Slider limits (sim PARAM_META reads them) that the firmware's fixed buffers are sized from. Values pushed past a
// slider over serial are capped and reported, never written past a buffer.
#define FIZZ_COUNT_MAX     240   // fizzCount: bubbles in a full tube
#define FIZZ_POOL          (2 * FIZZ_COUNT_MAX)   // bubbles per tube: full agitation (<= 1) doubles fizzCount
#define DIGIT_SCALE_MAX    6     // digitScaleX / Y (and Min): design px per em cell
#define DIGIT_SHADOW_OFFSET_MAX 4   // digitShadowOffset, design px
#define GLYPH_EM_W         5     // the nominal em of the sprite fonts, cells (same as the bitmap fonts: a scale means the same)
#define GLYPH_EM_H         7
#define MARK_CONTRAST_MAX  120   // markContrast

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
#ifndef LCD_FILL
#define LCD_FILL           0
#endif
#ifndef LCD_FILL_H
#define LCD_FILL_H         LCD_FILL   // hours tube wide
#endif
#ifndef LCD_FILL_M
#define LCD_FILL_M         LCD_FILL   // minutes tube wide
#endif
#define PX_SCALE_WIDE      ((float)PANEL_H / DESIGN_H)
#define PX_SCALE_NARROW    ((float)(830 * RENDER_H) / (912 * LCD_PANEL_H))   // 0.083 / 0.0912 per panel px, exact ratio
#define PX_SCALE_H         (LCD_FILL_H ? PX_SCALE_WIDE : PX_SCALE_NARROW)
#define PX_SCALE_M         (LCD_FILL_M ? PX_SCALE_WIDE : PX_SCALE_NARROW)
#define PX_SCALED_H        (LCD_FILL_H ? RENDER_H != DESIGN_H : 1)
#define PX_SCALED_M        (LCD_FILL_M ? RENDER_H != DESIGN_H : 1)
#define PX_MIXED           (!LCD_FILL_H != !LCD_FILL_M)
#else
#define PANEL_W            536
#define PANEL_H            240
#define PX_SCALE_H         1.0f
#define PX_SCALE_M         1.0f
#define PX_SCALED_H        0
#define PX_SCALED_M        0
#define PX_MIXED           0
#endif
// PX_SCALE_H / _M: canvas px per design px of the hours / minutes tube (1 on the AMOLED); PX_SCALED_x: it is not 1
// (that tube's px params need scaling); PX_MIXED: the two differ (each tube runs on its own scaled params).
#define PX_SCALED          (PX_SCALED_H || PX_SCALED_M)
#define TUBE_PX_SCALE(i)   (PX_MIXED && (i) ? PX_SCALE_M : PX_SCALE_H)   // tube i (0 = hours); a constant unless PX_MIXED
#define PX_SCALE_MAX       (PX_SCALE_H > PX_SCALE_M ? PX_SCALE_H : PX_SCALE_M)   // what buffers are sized for
#define TUBE_LENGTH_PX     PANEL_W   // full width; leather may mask the outer ~10px
// Strip buffer rows: the largest preset tube at this scale. Defaults below; runtime values come from params
// tubeHeight / hoursY / minutesY (design px, scaled).
#define TUBE_HEIGHT_MAX    ((int)(DESIGN_TUBE_HEIGHT_MAX * PX_SCALE_MAX + 0.999f))
#define TUBE_HEIGHT_PX     ((int)(72 * PX_SCALE_MAX))   // ≈ 6 mm at 0.083 mm per design px (the wider tube: test pattern)
#define HOURS_TUBE_Y       0                            // along the top edge
#define MINUTES_TUBE_Y     (PANEL_H - TUBE_HEIGHT_PX)   // along the bottom edge
#define BRIDGE_Y0          TUBE_HEIGHT_PX               // bridge zone between the tubes must stay pure black
#define BRIDGE_Y1          MINUTES_TUBE_Y

// Colors (RGB888 reference; RGB565 derived, verify on AMOLED)
#define LIQUID_RGB888      0x5DCAA5
#define LIQUID_HI_RGB888   0x9FE1CB
#define BG_RGB888          0x000000

// mm per canvas px for the physical meniscus (tube radius vs capillary length) of a tube at px scale k: the AMOLED's
// pitch per design px, so a scaled bore stays the same bore in mm and the meniscus keeps its shape on every board.
#define DESIGN_MM_PER_PX   0.083f
#define MM_PER_PX_AT(k)    (DESIGN_MM_PER_PX / (k))

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
