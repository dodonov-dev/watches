// Tiled tube render (plan step 7): drawTube's base stages (back fill up to the bounds) draw TILE_ROWS strip rows at a
// time into a tile in internal RAM; each finished tile is copied to its strip rows by a sink, while the next tile renders
// into the other slot. The strip lines are then never fetched by the base stages (on the LCD the first touch of every
// PSRAM strip line, write-allocate fill + dirty writeback, was ~5 ms of each render core).
//   LCD (BOARD_LCD316, xtensa): the sink is GDMA mem-to-mem (tile_dma.cpp): no CPU, no cache line fill. -DTILE_OFF:
//   the strip path of step 6.
//   Host (check_render_frames.py --tiles): -DTILE_RENDER=1, the sink is memcpy (render.cpp), to prove the pixels.
#pragma once
#include <stdint.h>
#include "layout.h"
// 4 rows: two slots per tube (both cores render at once) = 4 x 6,560 B internal at 820 px; a 4-row tile of 820 px is
// 205 x 32 B, the GDMA's PSRAM block (rows are 1,640 B, so whole 64-B lines need 8 rows).
#define TILE_ROWS 4
// Canvases whose 4-row tile is not a whole number of 32-B blocks (RENDER_H 240: 615 px, 288: 738 px) keep the strip
// path of step 6.
#ifndef TILE_RENDER
#if defined(BOARD_LCD316) && defined(__XTENSA__) && !defined(TILE_OFF) && (TILE_ROWS * PANEL_W * 2) % 32 == 0
#define TILE_RENDER 1
#else
#define TILE_RENDER 0
#endif
#endif
#if TILE_RENDER
bool tiles_init();                                       // once, at boot (render_init): false = no DMA channel
uint16_t *tile_slot(int idx, int slot);                  // tube idx's slot (0 / 1): TILE_ROWS x PANEL_W, 16-B aligned
// Before the first tile of a frame: strip rows [0, rows) (rounded up to whole tiles) leave the data cache (discarded,
// dirty or not: the tiles rewrite every pixel of them), and nothing reads the strip until tile_end.
void tile_begin(int idx, uint16_t *strip, int rows);
// The slot's first `rows` rows -> dst (the copy before it lands first). The LCD copies the whole tile: strip rows past
// the tube (the strip is allocated in whole tiles) take whatever the slot holds there; nothing reads them.
void tile_put(int idx, int slot, uint16_t *dst, int rows);
void tile_end(int idx);                                  // every put of tube idx has landed
// The push of tube idx's strip (display_lcd316.cpp, PUSH_GATHER) borrows the tube's slots and channel: each tube's push
// runs on its own render core, after (hours) or before (minutes) its render, never during it. tile_scratch: the two
// slots, TILE_SCRATCH_FREE bytes for the caller (the gather's descriptors live past them). A gather copies `rows`
// (<= TILE_GATHER_ROWS) pieces of `bytes` B from src + off[r] + col (PSRAM, written back) packed into dst, on tube
// idx's channel; set (0 / 1) = which of two descriptor sets, so one gather can run while the last one is read.
#define TILE_GATHER_ROWS 32
#define TILE_SCRATCH_FREE (2 * TILE_ROWS * PANEL_W * 2 - 1024)
uint8_t *tile_scratch(int idx);
void tile_gather_start(int idx, int set, uint8_t *dst, const uint16_t *src, const int32_t *off, int rows, int col, int bytes);
void tile_gather_wait(int idx);                          // the last gather of tube idx has landed
const uint32_t *tile_prof(int idx);                      // tube idx since boot, CPU cycles: tile_begin, waits in tile_put,
                                                         // wait in tile_end, put set-up, waits in the gathers
#endif
