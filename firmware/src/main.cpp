// Liquid Watch firmware — liquid face (port of the sim) + Phase 1 bring-up faces.
// Serial commands (115200, USB CDC; same protocol over BLE Nordic UART Service, name "liquid-watch"):
//   l  liquid face (default)          c  calibration face        h  hello / orientation test
//   m  measuring face: full-panel frame, px rulers (white) and mm rulers at the assumed pitch (green)
//   f  live fps + frame timing        i  toggle IMU stream (50 Hz CSV)
//   g <along> <across> [gyroAlong gyroAcross]  tilt override in g / dps instead of the IMU (bench poses without
//      touching the board; not persisted)   g  back to the IMU
//   t HH:MM[:SS]  set clock           d<N>  demo time speed ×N (d1 = real time, d0 = freeze; persists in NVS)
//   T <epoch_s> <tz_min>  set clock from the sim (persists in NVS, re-saved each minute; power-on resumes from it,
//      or from the RTC on boards with one: board.h HAS_RTC)
//   w<N>  minutes sweep: the minutes tube runs empty→full→empty every N s, hours keep the clock (w0 = off; persists in NVS)
//   p<name>=<value>  set a param (e.g. p liquid=#39ff14, p fizz=0, p contactAngle=140)
//   p~<name>=<value>  volatile: set it for now, never autosaved (tooling pins; a reboot or `p!` drops it)
//   p?  dump params as JSON           p!  reset params to the built-in preset (and erase NVS copy)
//   params are in design px (spec/layout.h DESIGN_H); physics and render run on them scaled to this board's canvas
//   params persist in NVS (autosave 2 s after last p write)
//   b<n> brightness 0..255            H<0|1>  panel HBM experiment (RM67162 B0h; unusable, see KAIZEN)
//   X  deterministic sequence on the current params (seq.h): `SEQ <frame> <hash hours> <hash minutes> [<hash seconds>]
//      fizz ...` per frame, then `SEQ END`; compare two builds with tools/check_board_steps.py (the tubes restart from
//      10:09:30)
//   TUBE_COUNT 3 (layout.h): + the seconds tube (bottom; minutes in the middle), rendered on core 1 after minutes
//   v  board and canvas: `board <name>[@<RENDER_H>] canvas <W>x<H> panel <W>x<H>` (tools pick the sim's layout by it)
//   B0  reboot into fast mode (BLE off) now   B1  reboot into the BLE window   B  the mode (ble.h: every boot is fast mode;
//      the B1 boot runs a BLE window, then reboots into fast mode)
//   r  reboot
#include <Arduino.h>
#include <atomic>
#include <Preferences.h>
#include <Adafruit_GFX.h>
#include <Wire.h>
#include <sys/time.h>
#include "esp_heap_caps.h"
#include "esp_private/sar_periph_ctrl.h"   // temperature_sensor_power_acquire / temp_sensor_get_raw_value (die temperature, `s`)
#include "layout.h"
#include "board.h"
#include "display.h"
#include "imu.h"
#if TUBE_COUNT == 3 && defined(AB_COMPARE)
#error "AB_COMPARE (the A/B resolution face) shows the minutes tube twice: two-tube builds only"
#endif
#include "ble.h"
#include "diag.h"
#include "rtc.h"
#include "physics.h"
#include "render.h"
#include "seq.h"
#include "tiles.h"
#ifdef AB_COMPARE
#include "render_ab.h"
#endif
#include "gen/params_gen.h"

#ifndef BOOT_MODE
#define BOOT_MODE 'l'
#endif

// GFXcanvas16 with the pixel buffer in PSRAM. Pixels are stored byte-swapped (panel is
// big-endian RGB565) so the display push is a straight memcpy; callers use normal RGB565.
class PsramCanvas : public Adafruit_GFX {
 public:
  uint16_t *buf;
  PsramCanvas(int w, int h) : Adafruit_GFX(w, h) {
    buf = (uint16_t *)heap_caps_malloc((size_t)w * h * 2, MALLOC_CAP_SPIRAM);
  }
  void drawPixel(int16_t x, int16_t y, uint16_t c) override {
    if (x < 0 || y < 0 || x >= _width || y >= _height) return;
    buf[(size_t)y * _width + x] = __builtin_bswap16(c);
  }
  void fillScreen(uint16_t c) override {
    c = __builtin_bswap16(c);
    uint32_t cc = (uint32_t)c | ((uint32_t)c << 16);
    uint32_t *p = (uint32_t *)buf;
    for (size_t i = 0; i < (size_t)_width * _height / 2; i++) p[i] = cc;
  }
  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t c) override {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > _width) w = _width - x;
    if (y + h > _height) h = _height - y;
    c = __builtin_bswap16(c);
    for (int yy = y; yy < y + h; yy++) {
      uint16_t *row = buf + (size_t)yy * _width + x;
      for (int xx = 0; xx < w; xx++) row[xx] = c;
    }
  }
};

static PsramCanvas fb(PANEL_W, PANEL_H);
static char mode = BOOT_MODE;
static bool imu_stream = false;
static bool have_imu = false, imu_ok = false;   // have_imu: tilt is fed to the physics (IMU alive, or a `g` override)

// ---- liquid face state ----
static Params params = PRESET_DEFAULT;   // design px: what `p` writes, `p?` dumps and NVS keeps
// Params scaled to the canvas (PARAM_FIELDS px), per tube (its px scale, layout.h TUBE_PX_SCALE): what physics and
// render run on. Scale 1 (AMOLED) aliases params; equal tube widths share one struct (no internal RAM on a copy).
#if PX_SCALED
static Params effH = PRESET_DEFAULT;
#else
static Params &effH = params;
#endif
// A tube whose px scale an earlier tube has shares that one's struct: one copy per width (float compares, so constexpr:
// the unused copies are never referenced and dropped).
constexpr bool EFF_M_OWN = PX_SCALE_M != PX_SCALE_H;
static Params effMOwn = PRESET_DEFAULT;
static Params &effM = EFF_M_OWN ? effMOwn : effH;
#if TUBE_COUNT == 3
constexpr bool EFF_S_OWN = PX_SCALE_S != PX_SCALE_H && PX_SCALE_S != PX_SCALE_M;
static Params effSOwn = PRESET_DEFAULT;
static Params &effS = EFF_S_OWN ? effSOwn : PX_SCALE_S == PX_SCALE_M ? effM : effH;
static Params &effOf(int idx) { return idx == 0 ? effH : idx == 1 ? effM : effS; }
#else
static Params &effOf(int idx) { return idx ? effM : effH; }
#endif
static uint32_t paramsGen = 1;   // bumped on every param change; renderer caches key on it
// Every param change goes through here (the render worker is idle outside renderBoth, see below).
static void paramsChanged() {
#if PX_SCALED
  boardParams(params, effH, PX_SCALE_H, PX_SCALE_FIZZ);
#endif
  if constexpr (EFF_M_OWN) boardParams(params, effMOwn, PX_SCALE_M, PX_SCALE_FIZZ);
#if TUBE_COUNT == 3
  if constexpr (EFF_S_OWN) boardParams(params, effSOwn, PX_SCALE_S, PX_SCALE_FIZZ);
#endif
  paramsGen++;
}
// NVS autosave: namespace lw, blob cur. Written 2 s after the last change; ignored if the schema CRC differs.
// What NVS keeps: `p` writes go to params and here, `p~` writes (volatile) to params only, and the autosave writes this
// copy. PSRAM, allocated once at boot (paramsLoad); without it `p~` is refused.
static Preferences prefs;
static uint32_t paramsDirtyAt = 0;
static Params *paramsSaved = nullptr;
static void paramsLoad() {
  paramsSaved = (Params *)heap_caps_malloc(sizeof(Params), MALLOC_CAP_SPIRAM);
  if (!paramsSaved) out.println("error params: no PSRAM for the saved copy (p~ refused)");
  prefs.begin("lw", false);
  if (prefs.getUInt("crc") == PARAMS_SCHEMA_CRC && prefs.getBytesLength("cur") == sizeof(Params)) {
    prefs.getBytes("cur", &params, sizeof(Params)); paramsChanged(); out.println("params: restored from nvs");
  }
  if (paramsSaved) *paramsSaved = params;
}
static void paramsTouch() { paramsDirtyAt = millis() | 1; }
static void paramsFlush() {
  if (!paramsDirtyAt || millis() - paramsDirtyAt < 2000) return;
  paramsDirtyAt = 0;
  prefs.putBytes("cur", paramsSaved ? paramsSaved : &params, sizeof(Params)); prefs.putUInt("crc", PARAMS_SCHEMA_CRC);
}
static void paramsErase() { paramsDirtyAt = 0; prefs.remove("cur"); prefs.remove("crc"); }
static TubeState tubeH, tubeM;
#if TUBE_COUNT == 3
static TubeState tubeS;   // seconds (148 B internal)
static TubeState &tubeOf(int idx) { return idx == 0 ? tubeH : idx == 1 ? tubeM : tubeS; }
#else
static TubeState &tubeOf(int idx) { return idx ? tubeM : tubeH; }
#endif
static GravityNorm gnorm;
static ImuFilter imuFilter;
static TiltInput rawTilt = {0, 0, 0, 0};
static float demoSpeed = 1;          // time multiplier (d<N>); NVS key "demo", so demo mode survives resets and power loss
// Wall clock lives in the RTC-backed system time (settimeofday): survives the USB-CDC DTR/RTS reset
// that every host port open/close triggers. Power-on starts at 0 → last saved sim time from NVS, else 10:09:30.
// demoOffset sits in RTC memory next to it so a running demo clock survives that reset too.
RTC_NOINIT_ATTR static double demoOffset;         // seconds added by demo speed on top of real time
RTC_NOINIT_ATTR static uint32_t demoOffsetMagic;  // demoOffset valid (RTC memory is garbage after power-on)
static const uint32_t DEMO_OFFSET_MAGIC = 0x64656d6f;
static void demoLoad() {
  if (demoOffsetMagic != DEMO_OFFSET_MAGIC || !isfinite(demoOffset)) { demoOffset = 0; demoOffsetMagic = DEMO_OFFSET_MAGIC; }
  float v = prefs.getFloat("demo", 1);
  if (isfinite(v) && v >= 0 && v <= 3600) demoSpeed = v;
  if (demoSpeed != 1) out.printf("demo: x%g restored from nvs\n", demoSpeed);
}
static void demoSave() { if (prefs.getFloat("demo", 1) != demoSpeed) prefs.putFloat("demo", demoSpeed); }
// Minutes sweep (w<N>): the minutes fill ignores the clock and runs a triangle wave, one empty→full→empty
// cycle per sweepPeriod seconds. NVS key "sweep". The phase steps with the physics clock, so d0 does not stop it.
static float sweepPeriod = 0;        // seconds per cycle, 0 = off
static double sweepPhase = 0;        // 0..1 through the cycle
static void sweepLoad() {
  float v = prefs.getFloat("sweep", 0);
  if (isfinite(v) && v >= 0 && v <= 3600) sweepPeriod = v;
  if (sweepPeriod > 0) out.printf("sweep: %gs restored from nvs\n", sweepPeriod);
}
static void sweepSave() { if (prefs.getFloat("sweep", 0) != sweepPeriod) prefs.putFloat("sweep", sweepPeriod); }
static double clockSec = 0;          // local seconds since midnight, refreshed every physics step
static const time_t CLOCK_EPOCH_MIN = 86400L * 365;  // below this = never set since power-on
// Real time from the sim (`T`) persists in NVS key "clk": saved on `T` and then once a minute, so power-on
// resumes where the clock stopped (stale by the time spent off, no RTC battery). A `t` pin (bench scenes)
// stops the minute saves until the next `T`. clockFromSim sits in RTC memory to survive the soft resets.
RTC_NOINIT_ATTR static uint32_t clockFromSim;     // CLOCK_SIM_MAGIC while system time is sim-derived
static const uint32_t CLOCK_SIM_MAGIC = 0x73696d74;
static const uint32_t CLOCK_SAVE_MS = 60000;
static uint32_t clockSavedAt = 0;
static bool clockJumped = false;     // the clock was set: the fills jump there instead of retracting (followClock)
static void setClockLocal(time_t localSec, bool fromSim) {
  timeval tv = { localSec, 0 }; settimeofday(&tv, nullptr); demoOffset = 0;
  clockFromSim = fromSim ? CLOCK_SIM_MAGIC : 0; clockJumped = true;
}
static void clockSave() { if (clockFromSim == CLOCK_SIM_MAGIC) prefs.putLong64("clk", time(nullptr)); clockSavedAt = millis(); }
static void clockSaveTick() { if (millis() - clockSavedAt >= CLOCK_SAVE_MS) clockSave(); }
static void clockRestore() {
  clockSavedAt = millis();
  if (time(nullptr) >= CLOCK_EPOCH_MIN) return;   // system time (and clockFromSim) survived the reset
#if HAS_RTC
  time_t r;   // set by the last `T` and kept running while powered: the actual time, not the stale NVS copy
  if (rtc_read(r) && r >= CLOCK_EPOCH_MIN) { setClockLocal(r, true); out.println("clock: restored from rtc"); return; }
#endif
  int64_t v = prefs.getLong64("clk", 0);
  if (v >= CLOCK_EPOCH_MIN) { setClockLocal((time_t)v, true); out.println("clock: last sim time restored from nvs"); }
  else setClockLocal(CLOCK_EPOCH_MIN + 10 * 3600 + 9 * 60 + 30, false);
}
static double clockNow() {
  timeval tv; gettimeofday(&tv, nullptr);
  double s = fmod((double)(tv.tv_sec % 86400) + tv.tv_usec * 1e-6 + demoOffset, 86400.0);
  return s < 0 ? s + 86400 : s;
}
static void updateTimeTargets(float dt) {
  clockSec = clockNow();
  double minutes = fmod(clockSec / 60.0, 60.0);
  double hours = fmod(clockSec / 3600.0, 12.0);
  followClock(tubeH, (float)(hours / 12.0), dt, clockJumped);
  followClock(tubeM, sweepPeriod > 0 ? (float)(1.0 - fabs(2.0 * sweepPhase - 1.0)) : (float)(minutes / 60.0), dt, clockJumped);
#if TUBE_COUNT == 3
  followClock(tubeS, (float)(fmod(clockSec, 60.0) / 60.0), dt, clockJumped);   // with the fraction of the second (sim fillLevels)
#endif
  clockJumped = false;
}
static uint32_t lastPhysUs = 0, frames = 0, fpsT0 = 0;
static float fps = 0;
static uint32_t renderUs = 0, waitUs = 0;          // accumulated over the current fps window
static uint32_t hoursUs = 0, minutesUs = 0;        // per-core render time (hours on core 0, minutes here; + seconds)
#if TUBE_COUNT == 3
static uint32_t secondsUs = 0; static float secondsMs = 0;   // the seconds tube's render (core 1, after minutes; in minutesUs too)
#define SECONDS_US_RESET secondsUs = 0;
#else
#define SECONDS_US_RESET
#endif
static uint32_t tubeStepUs = 0, fizzStepUs = 0, physSteps = 0, pushUs = 0, restUs = 0;   // physics split, strip hand-over, loop() outside liquid_tick
static uint32_t lastTickEndUs = 0, fizzStepMaxUs = 0;
static float tubeStepMs = 0, fizzStepMs = 0, fizzStepMaxMs = 0, stepsPerFrame = 0, pushMs = 0, restMs = 0;   // tube/fizz: per physics step; the rest per frame
static bool tiltOverride = false;                  // `g`: rawTilt comes from the serial line, not the IMU
static float renderMs = 0, waitMs = 0, hoursMs = 0, minutesMs = 0;   // per-frame averages of the last window
static uint32_t busyCycles0 = 0; static float scanPct = 0;           // display ISR (LCD scan fill): share of one core
static DisplayRefill refill = {0, 0, 0};                             // panel refill health (display.h), per 2 s window
static uint16_t frameIntervalHist[256];             // 1 ms bins; bin 255 includes all slower frames
static uint32_t lastFrameStartUs = 0, frameIntervalSamples = 0;
static uint16_t frameP95Ms = 0;
// Tube strips of the frame being rendered (owned by the display backend, display_next_strips each frame): AMOLED
// the same two internal DMA buffers (its panel DMA reads them while the next frame renders), LCD a free set.
static uint16_t *strip[TUBE_COUNT] = {};   // hours, minutes[, seconds] (AMOLED: seconds' is hours')
// `x` dump line buffer (strip rows, then residue arrays): LCD in PSRAM, allocated in setup (internal RAM went to the
// step-7 tiles); AMOLED static.
#define DUMP_HEX_BYTES (PANEL_W > TUBE_LENGTH_PX ? PANEL_W * 4 + 2 : TUBE_LENGTH_PX * 4 + 2)
#ifdef BOARD_LCD316
static char *dumpHex = nullptr;
#else
static char dumpHex[DUMP_HEX_BYTES];
#endif

#if TUBE_COUNT == 3
static FaceLayout currentLayout() { return faceLayout(effH, effM, effS); }
#else
static FaceLayout currentLayout() { return faceLayout(effH, effM); }
#endif
static const int16_t *lensRows[TUBE_COUNT] = {};   // per tube: the lens row map the push applies (display_row_map)
static FaceLayout frameLayout;   // this frame's (renderBoth): the tubes' top rows for renderTube
#define FRAME_TOP(idx) frameLayout.top(idx)
static void renderOneTube(int idx, uint16_t *dst) {
#ifdef AB_COMPARE   // A/B face: the native minutes tube on core 0 (top slot), the AB_COMPARE-row one here (bottom)
  if (idx == 0) renderTube(1, tubeM, effM, paramsGen, dst, &lensRows[0]);
  else abcmp::render(dst, params, paramsGen, &lensRows[1]);
  return;
#endif
  renderTube(idx, tubeOf(idx), effOf(idx), paramsGen, dst, display_row_map ? &lensRows[idx] : nullptr, FRAME_TOP(idx));
}

static FaceLayout shownLayout = {};

// ---- hours-tube worker on core 0 (the Arduino loop runs on core 1) ----
// The two tubes are independent, so each frame renders them at the same time: the worker draws hours
// into strip[0] while loop() draws minutes into strip[1]. Hand-shake by task notification: loop()
// gives the worker one notification per frame and blocks on its own until the worker is done, so at
// any point outside renderBoth() the worker is idle and blocked (serial commands, param writes, the
// physics step and `x` all run in that window — nothing they touch is being read on core 0).
// Push, backends with display_push_any_core (LCD): staggered so that a push always runs next to the other core's
// render, never next to the other push (two pushes at once are slower than one after the other: PSRAM-bound) —
// core 0 renders hours, then pushes it; core 1 first pushes the previous frame's minutes strip (the strips are
// reused, so it still holds that frame), then renders minutes. The minutes tube shows one frame later than the
// hours tube. 2026-10-28, user preset: 16.0 → 17.7 fps over the serial push after both renders (core 1, 18.8 ms).
// Otherwise (AMOLED, one SPI DMA queue): the loop pushes both strips after both renders.
// Three tubes: core 1 renders seconds after minutes (lane 1, render.cpp TUBE_LANE). Staggered: the pushes swap cores
// (pend, below): core 1 pushes last frame's hours next to the hours render, core 0 last frame's minutes and seconds
// next to core 1's renders. AMOLED: after the hours and minutes pushes are queued, the seconds tube renders into the
// hours strip once its push has left it, then is pushed.
// Priority 1 = same as loop(); far below the BT controller (23) and NimBLE host on the same core, and
// the worker blocks every frame so core 0's idle task (task-WDT) keeps running.
#define WORKER_PRIO 1
#ifndef WORKER_STACK
#define WORKER_STACK 4096   // measured use ~3 KB (`v` stack-free worker ~1068)
#endif
#ifdef AB_COMPARE
#define STAGGER_PUSH false  // the A/B face pushes its second strip from another canvas, after both renders
#define AB_FACE 1
#else
#define STAGGER_PUSH display_push_any_core
#define AB_FACE 0
#endif
static TaskHandle_t workerTask = nullptr, loopTask = nullptr;
static uint32_t workerUs = 0, workerPushUs = 0;   // last hours render / push time, written by the worker
// The frame's fizz steps (liquid_tick records each step's inputs): each tube's run on the core that renders it, right
// before its render, so the two tubes step at once instead of one after the other on core 1 while core 0 waits. A tube
// steps only its own state (stepFizzTube), and its steps follow every stepTube of the frame as before (they read
// nothing stepTube writes but the agitation, recorded per step). The A/B face renders the minutes tube twice: it keeps
// stepFizz in the step loop. The X sequence (seq.h) keeps stepFizz too.
#ifndef AB_COMPARE
#define FIZZ_SPLIT 1
#else
#define FIZZ_SPLIT 0
#endif
struct FizzStepIn { float along, across, agitation; };
static FizzStepIn fizzIn[5]; static int fizzInN = 0;   // this frame's steps (<= 5)
static uint32_t workerFizzUs[5];                        // the hours tube's fizz steps, each, written by the worker
static void runFizzSteps(int idx, uint32_t *us) {
  for (int s = 0; s < fizzInN; s++) {
    const uint32_t t0 = micros();
    stepFizzTube(idx, effOf(idx), PHYS_DT, fizzIn[s].along, fizzIn[s].across, fizzIn[s].agitation);
    us[s] = micros() - t0;
  }
}
static uint32_t workerStackFree = 0;       // high-water mark (bytes on ESP-IDF), for `s`
static int hoursY0 = 0, hoursRows = 0;     // where this frame's hours strip goes (set by loop() before the worker starts)
// Staggered push: strip[1] holds a rendered minutes frame not pushed yet, for rows [minutesY0, +minutesRows) through
// lensRows[1]. Dropped whenever something else drew the face or the strip (layout change, other faces, `x`).
static bool minutesPending = false; static int minutesY0 = 0, minutesRows = 0;
#if TUBE_COUNT == 3
// Staggered, three tubes (LCD): the pushes swap cores against the renders, one frame late for every tube. Core 1 pushes
// last frame's hours strip, then renders minutes and seconds; core 0 renders hours, then pushes last frame's minutes and
// seconds (after core 1's push: one push at a time, PSRAM-bound). The strips come in two sets (display_next_strips),
// so a pushed strip is never the one its tube renders into. pend: last frame's strips, rows and lens row maps (copied:
// the tube's own map may be rebuilt by its next render while the other core pushes). Dropped like minutesPending.
// Loads (2026-11-05, 10-8-6): core 0 21.9 + 13.7 vs core 1 9.8 + 24.1 ms, was 31.7 / 37.8.
struct PendingPush { const uint16_t *buf; int y0, rows; const int16_t *map; };
static PendingPush pend[3]; static bool pendOn = false;
static int16_t *pendMap = nullptr;               // 3 x TUBE_HEIGHT_MAX, PSRAM (setup)
static std::atomic<bool> hoursPushDone{true};    // core 1 pushed last frame's hours strip (core 0's pushes wait for it)
static bool workerPushMS = false;                // this frame the worker pushes pend[1], pend[2] after the hours render
#endif
static void dropPending() {   // something else drew the face or the strips
  minutesPending = false;
#if TUBE_COUNT == 3
  pendOn = false;
#endif
}
// One 50 Hz physics step (k = its index in the frame): clock targets, IMU filter, every tube's stepTube; records the
// step's fizz inputs (FIZZ_SPLIT) for the per-core fizz runs.
static void physStep(int k) {
  demoOffset += PHYS_DT * (demoSpeed - 1);
  if (sweepPeriod > 0) sweepPhase = fmod(sweepPhase + PHYS_DT / sweepPeriod, 1.0);
  updateTimeTargets(PHYS_DT);
  TiltInput in = have_imu ? imuFilter.step(rawTilt, effH) : TiltInput{0, 0, 0, 0};   // no px params
  const uint32_t p0 = micros();
  stepTube(tubeH, in, effH, PHYS_DT, TUBE_PX_SCALE(0));
  stepTube(tubeM, in, effM, PHYS_DT, TUBE_PX_SCALE(1));
#if TUBE_COUNT == 3
  stepTube(tubeS, in, effS, PHYS_DT, TUBE_PX_SCALE(2));
#endif
  const uint32_t p1 = micros();
  if (FIZZ_SPLIT) fizzIn[k] = {in.along, in.across, tubeH.agitation};
  else stepFizz(effH, effM, PHYS_DT, in.along, in.across, tubeH.agitation);   // AB_COMPARE only: two tubes
#ifdef AB_COMPARE
  abcmp::step(in.along, in.across, in.gyroAlong, in.gyroAcross, tubeM.fillTarget, params, paramsGen, PHYS_DT);
#endif
  const uint32_t fz = micros() - p1;
  tubeStepUs += p1 - p0; fizzStepUs += fz; physSteps++;
  if (fz > fizzStepMaxUs) fizzStepMaxUs = fz;
}
#if TUBE_COUNT == 3
// Three tubes, staggered (LCD): the frame's physics steps run on core 0 at the start of the worker's job, next to core
// 1's push of last frame's hours strip (which reads no tube state); core 1 waits for physDone before its fizz and renders.
// Swinging the tilt the steps cost ~2.5 ms a frame (3 tubes, ~2 steps), which no longer sit in front of both renders.
static int physPending = 0;                  // steps for the worker to run this frame (0: liquid_tick ran them)
static std::atomic<bool> physDone{true};
#endif
static void renderWorker(void *) {
  for (;;) {
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
#if TUBE_COUNT == 3
    if (physPending) { for (int k = 0; k < physPending; k++) physStep(k); physPending = 0; physDone.store(true, std::memory_order_release); }
#endif
    if (FIZZ_SPLIT) runFizzSteps(0, workerFizzUs);
    uint32_t t0 = micros();
    renderOneTube(0, strip[0]);
    uint32_t t1 = micros();
    workerUs = t1 - t0;
    if (STAGGER_PUSH) {
#if TUBE_COUNT == 3
      uint32_t tp = micros();
      if (workerPushMS) {   // last frame's minutes and seconds, next to core 1's renders, once its hours push is done
        while (!hoursPushDone.load(std::memory_order_acquire)) {}
        tp = micros();
        for (int t = 1; t < 3; t++) display_push_strip_async(pend[t].buf, pend[t].y0, pend[t].rows, pend[t].map);
      }
      workerPushUs = micros() - tp;
#else
      const uint32_t tp = micros();
      display_push_strip_async(strip[0], hoursY0, hoursRows, lensRows[0]);
      workerPushUs = micros() - tp;
#endif
    }
    workerStackFree = uxTaskGetStackHighWaterMark(nullptr);
    xTaskNotifyGive(loopTask);
  }
}
#ifdef STACK_GUARD
// -DSTACK_GUARD=N (diagnostic builds, docs/hang-investigation-plan.md aid 6): render0's stack is static with N bytes of
// 0xA5 below it, outside the stack FreeRTOS sees; loop() checks them each frame. Partial detection only: a frame that
// jumps further than N, or a loop() blocked on render0, is not caught (read the guard over JTAG then: `v` prints it).
// Moves the stack from the heap to .bss (+N bytes internal RAM): what an overflow hits differs from production.
static StackType_t workerStackMem[(STACK_GUARD + WORKER_STACK) / sizeof(StackType_t)] __attribute__((aligned(16)));
static StaticTask_t workerTcb;
static int guardDamaged() {   // bytes of the guard no longer 0xA5
  int n = 0; const uint8_t *g = (const uint8_t *)workerStackMem;
  for (int i = 0; i < STACK_GUARD; i++) n += g[i] != 0xA5;
  return n;
}
#endif
static void workerStart() {
  loopTask = xTaskGetCurrentTaskHandle();
#ifdef STACK_GUARD
  memset(workerStackMem, 0xA5, STACK_GUARD);
  workerTask = xTaskCreateStaticPinnedToCore(renderWorker, "render0", WORKER_STACK, nullptr, WORKER_PRIO,
                                             workerStackMem + STACK_GUARD / sizeof(StackType_t), &workerTcb, 0);
#else
  xTaskCreatePinnedToCore(renderWorker, "render0", WORKER_STACK, nullptr, WORKER_PRIO, &workerTask, 0);
#endif
}

static void renderBoth() {
  const FaceLayout lay = currentLayout();
  if (lay != shownLayout) {                 // tubes moved: wipe the rows they used to cover
    display_wait_all();
    fb.fillScreen(0); display_push_frame(fb.buf);
    shownLayout = lay; dropPending();
  }
  frameLayout = lay;
  uint32_t t0 = micros();
#if TUBE_COUNT == 3
  if (!STAGGER_PUSH) display_wait_all();        // previous frame: seconds pushed last, from the hours strip
  else
#endif
  display_wait_pending(display_bands(lay.Hm));  // previous frame: hours strip pushed first → free once only minutes' bands remain
  uint32_t t1 = micros();
  display_next_strips(strip);
  hoursY0 = lay.yH; hoursRows = AB_FACE ? lay.Hm : lay.Hh;   // the A/B face shows the minutes tube in the hours slot
  render_fizz_prepare(effH);                    // the fizz masks, here on core 1: neither tube builds them while the other draws
#if TUBE_COUNT == 3
  workerPushMS = STAGGER_PUSH && pendOn;
  hoursPushDone.store(!workerPushMS, std::memory_order_release);
  physDone.store(physPending == 0, std::memory_order_release);
#endif
  xTaskNotifyGive(workerTask);                  // hours → core 0
  display_wait_all();                           // minutes strip free (overlaps the hours render)
  uint32_t t2 = micros();
  if (STAGGER_PUSH) {
#if TUBE_COUNT == 3
    if (pendOn) {                               // last frame's hours, next to the hours render
      display_push_strip_async(pend[0].buf, pend[0].y0, pend[0].rows, pend[0].map);
      hoursPushDone.store(true, std::memory_order_release);
      const uint32_t t = micros(); pushUs += t - t2; t2 = t;
    }
#else
    if (minutesPending) {                       // last frame's minutes, next to the hours render
      display_push_strip_async(strip[1], minutesY0, minutesRows, lensRows[1]);
      const uint32_t t = micros(); pushUs += t - t2; t2 = t;
    }
#endif
  }
  uint32_t fz1[5];
#if TUBE_COUNT == 3
  while (!physDone.load(std::memory_order_acquire)) {}   // core 0 steps the tubes first (physPending)
#endif
  if (FIZZ_SPLIT) runFizzSteps(1, fz1);   // the minutes tube's fizz steps, next to the hours tube's on core 0
  t2 = micros();
  renderOneTube(1, strip[1]);
  uint32_t t3 = micros();
#if TUBE_COUNT == 3
  uint32_t fz2[5] = {};
  if (STAGGER_PUSH) {                           // seconds after minutes, on this core (lane 1)
    if (FIZZ_SPLIT) runFizzSteps(2, fz2);
    const uint32_t ts = micros();
    renderOneTube(2, strip[2]);
    secondsUs += micros() - ts; t3 = micros();
  }
#endif
  ulTaskNotifyTake(pdTRUE, portMAX_DELAY);      // hours done (STAGGER_PUSH: and pushed)
  uint32_t t4 = micros();
  if (STAGGER_PUSH) {
    pushUs += workerPushUs;
#if TUBE_COUNT == 3
    for (int t = 0; t < 3; t++) {   // this frame's strips: pushed next frame (rows and lens map as rendered now)
      const int rows = lay.rows(t);
      int16_t *const m = lensRows[t] ? pendMap + t * TUBE_HEIGHT_MAX : nullptr;
      if (m) memcpy(m, lensRows[t], rows * sizeof(int16_t));
      pend[t] = {strip[t], lay.top(t), rows, m};
    }
    pendOn = true;
#else
    minutesPending = true; minutesY0 = lay.yM; minutesRows = lay.Hm;
#endif
  } else {
#ifdef AB_COMPARE
    { int aH, aY; abcmp::layout(params, paramsGen, aH, aY);
      display_push_strip_async(strip[0], lay.yH, lay.Hm, lensRows[0]);   // the native minutes tube, in the hours slot
      display_push_strip_ab(strip[1], aY, aH, lensRows[1]); }
#else
    display_push_strip_async(strip[0], lay.yH, lay.Hh, lensRows[0]);
    display_push_strip_async(strip[1], lay.yM, lay.Hm, lensRows[1]);
#if TUBE_COUNT == 3
    // seconds into the hours strip once its push has left it (transfers complete in queue order)
    display_wait_pending(display_bands(lay.Hm));
    if (FIZZ_SPLIT) runFizzSteps(2, fz2);
    const uint32_t ts = micros();
    renderOneTube(2, strip[2]);
    secondsUs += micros() - ts; t3 += micros() - ts;
    display_push_strip_async(strip[2], lay.yS, lay.Hs, lensRows[2]);
#endif
#endif
    pushUs += micros() - t4;                    // each band's window command waits for the band before it
  }
  if (FIZZ_SPLIT)   // the `f` fizz step: all tubes' cost a step, as when one core stepped them
    for (int s = 0; s < fizzInN; s++) {
      uint32_t fz = workerFizzUs[s] + fz1[s];
#if TUBE_COUNT == 3
      fz += fz2[s];
#endif
      fizzStepUs += fz; if (fz > fizzStepMaxUs) fizzStepMaxUs = fz;
    }
  renderUs += t4 - t1; waitUs += t1 - t0;       // render = wall time of the concurrent section (staggered: with the pushes)
  hoursUs += workerUs; minutesUs += t3 - t2;
  diag_feed();   // -DLOOP_WDT: the waits above completed
}

// Laid out on the AMOLED's 536x240, stretched to this canvas (SX / SY: identity there).
#define SX(v) ((v) * PANEL_W / 536)
#define SY(v) ((v) * PANEL_H / 240)
static void face_hello() {
  fb.fillScreen(0);
  fb.drawRect(0, 0, PANEL_W, PANEL_H, 0xFFFF);
  fb.setTextColor(0xFFFF); fb.setTextSize(SY(4));
  fb.setCursor(SX(120), SY(90)); fb.print("hello liquid");
  fb.setTextSize(SY(2));
  fb.setCursor(8, 8);   fb.print("<- LEFT (USB-C here?)");
  fb.setCursor(8, PANEL_H - 24); fb.print("bottom-left");
  fb.setCursor(PANEL_W - 136, PANEL_H - 24); fb.print("bottom-right");
  fb.fillRect(SX(20), SY(150), SX(60), SY(40), 0xF800);
  fb.fillRect(SX(90), SY(150), SX(60), SY(40), 0x07E0);
  fb.fillRect(SX(160), SY(150), SX(60), SY(40), 0x001F);
  fb.fillRect(SX(230), SY(150), SX(60), SY(40), LIQUID_RGB565);
  fb.fillRect(SX(300), SY(150), SX(60), SY(40), LIQUID_HI_RGB565);
  fb.setTextSize(1); fb.setCursor(SX(380), SY(160)); fb.print(BOARD_TAG);
  display_push_frame(fb.buf);
}

static void face_calibration() {
  fb.fillScreen(0);
#if TUBE_COUNT == 3   // hours at the top edge, seconds at the bottom, minutes centred between (render.h faceLayout)
  const int ys[3] = {HOURS_TUBE_Y, HOURS_TUBE_Y + TUBE_HEIGHT_PX + (MINUTES_TUBE_Y - HOURS_TUBE_Y - 2 * TUBE_HEIGHT_PX + 1) / 2, MINUTES_TUBE_Y};
#else
  const int ys[2] = {HOURS_TUBE_Y, MINUTES_TUBE_Y};
#endif
  for (int y : ys) {
    fb.fillRect(0, y, TUBE_LENGTH_PX, TUBE_HEIGHT_PX, LIQUID_RGB565);
    fb.drawFastHLine(0, y + TUBE_HEIGHT_PX / 2, PANEL_W, 0xFFFF);
    fb.drawFastVLine(PANEL_W / 2, y, TUBE_HEIGHT_PX, 0xFFFF);
  }
  display_push_frame(fb.buf);
}

// Measuring face: a 1-px frame on the canvas's outermost pixels (= the panel's at full res), a px ruler along the top and
// left edges (white: 10 / 50 / 100 px), an mm ruler at the assumed pitch (PX_PER_MM) along the bottom and right edges
// (green: 1 / 5 / 10 mm), and a centre cross. Lay a steel ruler on the glass: if the green mm don't match, the pitch
// is off (spec/layout.h LCD_MM_PER_PX).
static void face_ruler() {
  const uint16_t W = 0xFFFF, G = 0x07E0, D = 0x4208;
  fb.fillScreen(0);
  fb.drawFastHLine(0, PANEL_H / 2, PANEL_W, D); fb.drawFastVLine(PANEL_W / 2, 0, PANEL_H, D);
  fb.drawRect(0, 0, PANEL_W, PANEL_H, W);
  fb.setTextSize(2); fb.setTextColor(W);
  for (int x = 10; x < PANEL_W; x += 10) {
    const int len = x % 100 == 0 ? 24 : x % 50 == 0 ? 14 : 7;
    fb.drawFastVLine(x, 0, len, W);
    if (x % 100 == 0) { fb.setCursor(x + 3, 14); fb.print(x); }
  }
  for (int y = 10; y < PANEL_H; y += 10) {
    const int len = y % 100 == 0 ? 24 : y % 50 == 0 ? 14 : 7;
    fb.drawFastHLine(0, y, len, W);
    if (y % 100 == 0) { fb.setCursor(14, y + 3); fb.print(y); }
  }
  fb.setTextColor(G);
  for (int mm = 1; mm * PX_PER_MM < PANEL_W; mm++) {
    const int x = (int)lroundf(mm * PX_PER_MM), len = mm % 10 == 0 ? 24 : mm % 5 == 0 ? 14 : 7;
    fb.drawFastVLine(x, PANEL_H - len, len, G);
    if (mm % 10 == 0) { fb.setCursor(x + 3, PANEL_H - 30); fb.print(mm); }
  }
  for (int mm = 1; mm * PX_PER_MM < PANEL_H; mm++) {
    const int y = (int)lroundf(mm * PX_PER_MM), len = mm % 10 == 0 ? 24 : mm % 5 == 0 ? 14 : 7;
    fb.drawFastHLine(PANEL_W - len, y, len, G);
    if (mm % 10 == 0) { fb.setCursor(PANEL_W - 52, y + 3); fb.print(mm); }
  }
  fb.setTextColor(W); fb.setCursor(PANEL_W / 2 - 230, PANEL_H / 2 - 40);
  fb.printf("%dx%d px  %.4f mm/px", PANEL_W, PANEL_H, 1.0f / PX_PER_MM);
  fb.setCursor(PANEL_W / 2 - 230, PANEL_H / 2 + 20);
  fb.printf("expect %.2f x %.2f mm", PANEL_W / PX_PER_MM, PANEL_H / PX_PER_MM);
  fb.setTextSize(1); fb.setCursor(PANEL_W / 2 - 230, PANEL_H / 2 + 60); fb.print(BOARD_TAG);
  display_push_frame(fb.buf);
}

// Live figures of whatever the loop is rendering (2 s rolling window, see liquid_tick).
static void report_fps() {
  int foamH = 0, foamM = 0, slotsH = 0, slotsM = 0; const int fizzH = fizzCounts(0, foamH, slotsH), fizzM = fizzCounts(1, foamM, slotsM);
#if TUBE_COUNT == 3
  char secs[96]; { int foamS = 0, slotsS = 0; const int fizzS = fizzCounts(2, foamS, slotsS);
    snprintf(secs, sizeof secs, " s %d (foam %d, slots %d)  seconds %.2f ms", fizzS, foamS, slotsS, secondsMs); }
#else
  const char *const secs = "";
#endif
  out.printf("fps %.1f  render %.2f ms  push-wait %.2f ms  cores h %.2f / m %.2f ms  (mode %c, transp %.2f)  frame-p95 %u ms"
             "  phys %.2f steps x (tube %.2f + fizz %.2f ms, max %.2f)  push %.2f ms  rest %.2f ms  fizz h %d (foam %d, slots %d) m %d (foam %d, slots %d)%s  scan-isr %.1f%%"
             "  refill late %u restarts %u worst %u%%",
             fps, renderMs, waitMs, hoursMs, minutesMs, mode, params.liquidTransparency,
             (unsigned)frameP95Ms, stepsPerFrame, tubeStepMs, fizzStepMs, fizzStepMaxMs, pushMs, restMs, fizzH, foamH, slotsH, fizzM, foamM, slotsM, secs, scanPct,
             (unsigned)refill.late, (unsigned)refill.restarts, (unsigned)refill.worstPct);
#ifdef DIGIT_VERIFY
  { uint32_t px = 0, bad = 0; render_digit_verify(px, bad); out.printf("  digit-verify bad %u of %u px", (unsigned)bad, (unsigned)px); }
#endif
#ifdef TUBE_VERIFY
  { const char *nm[] = {"zone px", "palette", "band rows", "trace memo", "ramp rows px"}; out.printf("  tube-verify");
    for (int k = 0; k < 5; k++) { uint32_t n = 0, bad = 0; render_tube_verify(k, n, bad); out.printf(" %s bad %u of %u", nm[k], (unsigned)bad, (unsigned)n); } }
#endif
#ifdef TILE_VERIFY
  { uint32_t n = 0, bad = 0; render_tile_verify(n, bad); out.printf("  tile-verify bad %u of %u px", (unsigned)bad, (unsigned)n); }
#endif
#if defined(PUSH_VERIFY) && defined(BOARD_LCD316)
  { const PushVerify v = display_push_verify();
    out.printf("  push-verify bad %u of %u px  stored %u of %u words  skipped %u of %u segments", (unsigned)v.bad, (unsigned)v.checked,
               (unsigned)v.stored, (unsigned)v.words, (unsigned)v.skipped, (unsigned)v.segs); }
#endif
  out.printf("\n");
#if defined(PUSH_PROF) && defined(BOARD_LCD316)
  { uint32_t k[TUBE_COUNT][PUSH_PROF_N]; display_push_prof(k, true);
    for (int i = 0; i < TUBE_COUNT; i++) { const float n = k[i][0] ? (float)k[i][0] : 1;
      out.printf("push-prof %d pushes %u (by record %u)  us hash %.0f store %.0f gather-wait %.0f  changed segs %.0f  units %.1f\n", i, (unsigned)k[i][0],
                 (unsigned)k[i][6], k[i][1] / 240.0f / n, k[i][2] / 240.0f / n, k[i][4] / 240.0f / n, k[i][3] / n, k[i][5] / n); } }
#endif
#ifdef TUBE_PROF
  const uint32_t k0frames = render_tube_profile(0)[0];
  for (int i = 0; i < TUBE_COUNT; i++) {   // per-frame averages over the frames since the last `f` (cycles / 240 = us), TU_* order
    const uint32_t *k = render_tube_profile(i); const float n = k[0] ? (float)k[0] : 1, us = 240 * n;
    out.printf("tube-prof %c frames %u  us all %.0f pal %.0f back %.0f trprep %.0f trrows %.0f (fill %.0f shear %.0f zone %.0f) backing %.0f"
               " body %.0f front %.0f glow %.0f film %.0f inset %.0f band %.0f bounds %.0f labels %.0f ticks %.0f digits %.0f fizz %.0f top %.0f ramp %.0f bandk %.0f palp %.0f palb %.0f tile %.0f hash %.0f\n",
               "hms"[i], (unsigned)k[0], k[1] / us, k[2] / us, k[3] / us, k[4] / us, k[5] / us, k[19] / us, k[20] / us, k[21] / us,
               k[6] / us, k[7] / us, k[8] / us, k[9] / us, k[10] / us, k[11] / us, k[12] / us, k[13] / us, k[14] / us, k[15] / us,
               k[16] / us, k[17] / us, k[18] / us, k[22] / us, k[23] / us, k[25] / us, k[24] / us, k[26] / us, k[27] / us);
  }
  render_tube_profile_reset();
#if TILE_RENDER
  { static uint32_t last[2][5]; const float n = k0frames ? (float)k0frames : 1;
    for (int i = 0; i < 2; i++) { const uint32_t *t = tile_prof(i); uint32_t d[5]; for (int j = 0; j < 5; j++) { d[j] = t[j] - last[i][j]; last[i][j] = t[j]; }
      out.printf("tile-prof %c  us begin %.0f put-wait %.0f end-wait %.0f put %.0f gather-wait %.0f\n", i ? 'm' : 'h', d[0] / 240.0f / n, d[1] / 240.0f / n,
                 d[2] / 240.0f / n, d[3] / 240.0f / n, d[4] / 240.0f / n); } }
#endif
#endif
#ifdef TICK_PROF
  for (int i = 0; i < 2; i++) {   // per-frame averages over the frames since the last `f` (cycles / 240 = us)
    const uint32_t *k = render_tick_profile(i); const float n = k[0] ? (float)k[0] : 1, us = 240 * n;
    out.printf("tick-prof %c frames %u  us all %.1f facts %.1f ranges %.1f rows %.1f (fills %.1f, per-pixel %.1f)  rows %.0f (dry %.0f wet %.0f mixed %.0f)"
               "  fills %.0f  per-pixel px %.0f  segs %.0f ticks %.0f\n",
               i ? 'm' : 'h', (unsigned)k[0], k[1] / us, k[2] / us, k[3] / us, k[4] / us, k[14] / us, k[5] / us, k[6] / n, k[7] / n, k[8] / n,
               k[9] / n, k[10] / n, k[11] / n, k[12] / n, k[13] / n);
  }
  render_tick_profile_reset();
#endif
#ifdef FIZZ_PROF
  for (int i = 0; i < 2; i++) {   // per-frame averages over the frames since the last `f` (cycles / 240 = us)
    const uint32_t *k = render_fizz_profile(i); const float n = k[FZ_FRAMES] ? (float)k[FZ_FRAMES] : 1, us = 240 * n;
    out.printf("fizz-prof %c frames %u  us all %.1f setup %.1f rowprep %.1f disc %.1f redraw %.1f  bubbles %.1f rows %.1f"
               "  px visit %.0f skip %.0f out %.0f cov0 %.0f aa %.0f veil %.0f core %.0f corew %.0f sqrt %.0f blick %.0f ring %.0f solid %.0f off %.0f\n",
               i ? 'm' : 'h', (unsigned)k[FZ_FRAMES], k[FZ_CYC] / us, k[FZ_CYC_SETUP] / us, k[FZ_CYC_ROWPREP] / us, k[FZ_CYC_DISC] / us,
               k[FZ_CYC_REDRAW] / us, k[FZ_BUBBLES] / n, k[FZ_ROWS] / n, k[FZ_PX_VISIT] / n, k[FZ_PX_SKIP] / n, k[FZ_PX_OUT] / n,
               k[FZ_PX_COV0] / n, k[FZ_PX_AA] / n, k[FZ_PX_VEIL] / n, k[FZ_PX_CORE] / n, k[FZ_PX_COREW] / n, k[FZ_PX_SQRT] / n,
               k[FZ_PX_BLICK] / n, k[FZ_PX_RING] / n, k[FZ_PX_SOLID] / n, k[FZ_PX_OFF] / n);
  }
  {   // per stepFizz call (both tubes)
    const uint32_t *k = render_fizz_step_profile(); const float n = k[FS_STEPS] ? (float)k[FS_STEPS] : 1, us = 240 * n;
    out.printf("fizz-step steps %u  us all %.1f rand %.1f (%.2f calls) springpt %.1f loop %.1f fit %.1f (%.1f calls, %.1f rows) touch %.1f (%.1f calls, %.0f slots)"
               "  merge %.1f cadence %.1f settle %.1f  live %.1f held %.1f slots %.1f\n",
               (unsigned)k[FS_STEPS], k[FS_CYC] / us, k[FS_CYC_RAND] / us, k[FS_RANDS] / n, k[FS_CYC_SPRINGPT] / us, k[FS_CYC_LOOP] / us,
               k[FS_CYC_FIT] / us, k[FS_FITS] / n, k[FS_FIT_ROWS] / n, k[FS_CYC_TOUCH] / us, k[FS_TOUCHES] / n, k[FS_TOUCH_SCAN] / n,
               k[FS_CYC_MERGE] / us, k[FS_CYC_CADENCE] / us, k[FS_CYC_SETTLE] / us, k[FS_LIVE] / n, k[FS_HELD] / n, k[FS_SLOTS] / n);
  }
  render_fizz_profile_reset();
#endif
#ifdef DIGIT_PROF
  for (int i = 0; i < 2; i++) {
    const uint32_t *c = render_profile(i);
    out.printf("digit-prof %c glyphs %u rows %u int-plain %u int-liq %u frac-plain %u frac-liq %u slow %u runs %u  us layout %u rear-ticks %u rear-digits %u\n",
               i ? 'm' : 'h', (unsigned)c[0], (unsigned)c[1], (unsigned)c[2], (unsigned)c[3], (unsigned)c[4], (unsigned)c[5], (unsigned)c[6], (unsigned)c[7],
               (unsigned)c[8], (unsigned)c[9], (unsigned)c[10]);
    const uint32_t *k = render_profile_cycles(i);
    out.printf("digit-cycles %c plain %u us  band %u us  ramp %u us\n", i ? 'm' : 'h', (unsigned)(k[0] / 240), (unsigned)(k[1] / 240), (unsigned)(k[2] / 240));
  }
#endif
}

// ---- liquid face ----
static void liquid_start() {
  fb.fillScreen(0);
  display_push_frame(fb.buf);
  dropPending();   // another face drew the strips / the face
  display_set_brightness(255);   // params.brightness is applied in the render LUTs
  updateTimeTargets(0);
  memset(frameIntervalHist, 0, sizeof(frameIntervalHist));
  lastFrameStartUs = 0; frameIntervalSamples = 0; frameP95Ms = 0;
  lastPhysUs = micros(); frames = 0; fpsT0 = millis();
  tubeStepUs = fizzStepUs = physSteps = pushUs = restUs = fizzStepMaxUs = 0; lastTickEndUs = 0;   // no time spent on another face in the first window
  renderUs = waitUs = hoursUs = minutesUs = 0; SECONDS_US_RESET
}

static void liquid_tick() {
  uint32_t frameStartUs = micros();
  if (lastTickEndUs) restUs += frameStartUs - lastTickEndUs;
  if (lastFrameStartUs) {
    uint32_t intervalMs = (frameStartUs - lastFrameStartUs + 999) / 1000;
    if (intervalMs > 255) intervalMs = 255;
    frameIntervalHist[intervalMs]++;
    frameIntervalSamples++;
  }
  lastFrameStartUs = frameStartUs;
  // physics at 50 Hz, catch up if a render took longer than one step
  uint32_t now = micros();
  int steps = 0;
  while ((int32_t)(now - lastPhysUs) >= (int32_t)(1000000 / PHYS_HZ) && steps < 5) { lastPhysUs += 1000000 / PHYS_HZ; steps++; }
#if TUBE_COUNT == 3
  if (STAGGER_PUSH) physPending = steps;   // the worker runs them (renderWorker)
  else
#endif
  for (int k = 0; k < steps; k++) physStep(k);
  fizzInN = steps;   // renderBoth steps the fizz (FIZZ_SPLIT)
  renderBoth();
  fizzInN = 0;
  frames++;
  {   // hang diagnostics: the frame into the RTC boot record; the loop task's high-water mark every 64 frames (a scan)
    static uint32_t loopFree = 0;
    if ((frames & 63) == 1 && loopTask) loopFree = uxTaskGetStackHighWaterMark(loopTask);
    diag_frame(workerStackFree, loopFree);
#ifdef STACK_GUARD
    const int bad = guardDamaged();
    if (bad) { diag_stage(DIAG_GUARD); diag_printf(out, "STACK GUARD render0: %d of %d B below the stack overwritten\n", bad, STACK_GUARD); abort(); }
#endif
  }
  {   // fizz asked past its fixed pool (params pushed past the sliders): say so once per new peak
    static int reported = 0; const int over = fizzOverflow();
    if (over > reported) { reported = over; out.printf("error fizz pool: %d bubbles requested, fixed pool holds fewer (capped)\n", over); }
  }
  {   // fizz size params past the sliders: the masks do not fit their pool, bubbles draw analytically (slower)
    static int reported = 0; const int over = fizzMaskOverflow();
    if (over > reported) { reported = over;
      if (over == INT_MAX) out.println("error fizz masks: bubble sizes past what a mask holds (analytic)");
      else out.printf("error fizz masks: %d bytes asked, the pool holds fewer (analytic)\n", over); }
  }
  if (millis() - fpsT0 >= 2000) {
    fps = frames * 1000.0f / (millis() - fpsT0);
    { const uint32_t c = display_busy_cycles(); scanPct = (c - busyCycles0) * 100.0f / (getCpuFrequencyMhz() * 1e6f * (millis() - fpsT0) / 1000.0f); busyCycles0 = c; }
    refill = display_refill_health();
    renderMs = renderUs / 1000.0f / frames; waitMs = waitUs / 1000.0f / frames;
    hoursMs = hoursUs / 1000.0f / frames; minutesMs = minutesUs / 1000.0f / frames;
#if TUBE_COUNT == 3
    secondsMs = secondsUs / 1000.0f / frames;
#endif
    stepsPerFrame = (float)physSteps / frames; pushMs = pushUs / 1000.0f / frames; restMs = restUs / 1000.0f / frames;
    tubeStepMs = physSteps ? tubeStepUs / 1000.0f / physSteps : 0; fizzStepMs = physSteps ? fizzStepUs / 1000.0f / physSteps : 0;
    fizzStepMaxMs = fizzStepMaxUs / 1000.0f;
    tubeStepUs = fizzStepUs = physSteps = pushUs = restUs = fizzStepMaxUs = 0;
    if (frameIntervalSamples) {
      uint32_t target = (frameIntervalSamples * 95 + 99) / 100, cumulative = 0;
      for (int ms = 0; ms < 256; ms++) {
        cumulative += frameIntervalHist[ms];
        if (cumulative >= target) { frameP95Ms = (uint16_t)ms; break; }
      }
    }
    memset(frameIntervalHist, 0, sizeof(frameIntervalHist)); frameIntervalSamples = 0;
    frames = 0; renderUs = waitUs = hoursUs = minutesUs = 0; SECONDS_US_RESET fpsT0 = millis();
  }
  lastTickEndUs = micros();
}

static void imu_poll() {
  if (!have_imu || tiltOverride) return;
  ImuSample s;
  if (!imu_read(s)) return;
  float a[3] = {s.ax, s.ay, s.az}, g[3] = {s.gx, s.gy, s.gz};
  float n = gnorm.update(sqrtf(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]));
  rawTilt.along = IMU_ALONG_TUBE_SIGN * a[IMU_AXIS_ALONG_TUBE] / n;
  rawTilt.across = IMU_ACROSS_TUBE_SIGN * a[IMU_AXIS_ACROSS_TUBE] / n;
  rawTilt.gyroAlong = g[IMU_AXIS_ALONG_TUBE];
  rawTilt.gyroAcross = g[IMU_AXIS_ACROSS_TUBE];
  static uint32_t next = 0;
  if (imu_stream && millis() >= next) {
    next = millis() + 20;
    out.printf("%lu,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f\n", millis(), s.ax, s.ay, s.az, s.gx, s.gy, s.gz);
  }
}

// ---- param access by name (serial now; GATT / Wi-Fi later reuse this) ----
static const ParamField *findField(const char *name) {
  for (int i = 0; i < PARAMS_NUM_FIELDS; i++) if (!strcmp(PARAM_FIELDS[i].name, name)) return &PARAM_FIELDS[i];
  return nullptr;
}
static bool setParam(Params &dst, const char *name, const char *val) {
  const ParamField *f = findField(name); if (!f) return false;
  uint8_t *p = (uint8_t *)&dst + f->off;
  switch (f->type) {
    case 'f': *(float *)p = atof(val); break;
    case 'i': *(int *)p = atoi(val); break;
    case 'b': *(bool *)p = !(val[0] == '0' || val[0] == 'f' || val[0] == 'F' || val[0] == 'n'); break;
    case 'c': *(uint32_t *)p = strtoul(val[0] == '#' ? val + 1 : val, nullptr, 16); break;
  }
  return true;
}
// Long serial output in bounded chunks: under host backpressure a USB CDC write can take ~200 ms per 256 B, so the
// -DLOOP_WDT feed goes between chunks of at most 512 B (~0.4 s), not between whole strips. Same bytes either way.
static void writeChunked(const char *s, size_t n) {
  while (n) { const size_t k = n < 512 ? n : 512; out.write((const uint8_t *)s, k); s += k; n -= k; diag_feed(); }
}
static void dumpParams() {
  out.print("{");
  for (int i = 0; i < PARAMS_NUM_FIELDS; i++) {
    const ParamField &f = PARAM_FIELDS[i]; const uint8_t *p = (const uint8_t *)&params + f.off;
    diag_feed();   // -DLOOP_WDT: one short write per field
    out.printf("%s\"%s\":", i ? "," : "", f.name);
    switch (f.type) {
      case 'f': out.printf("%g", *(const float *)p); break;
      case 'i': out.printf("%d", *(const int *)p); break;
      case 'b': out.print(*(const bool *)p ? "true" : "false"); break;
      case 'c': out.printf("\"#%06lx\"", (unsigned long)*(const uint32_t *)p); break;
    }
  }
  out.println("}");
}

#if TUBE_COUNT == 3
static bool liquidOk = true;   // every boot allocation of the face succeeded (setup); else the face never runs
#endif
static void show(char m) {
  display_wait_all();
#if TUBE_COUNT == 3
  if (m == 'l' && !liquidOk) { out.println("error liquid face: a boot allocation failed (see the boot log), hello face instead"); m = 'h'; }
#endif
  mode = m;
  switch (m) {
    case 'h': face_hello(); break;
    case 'c': face_calibration(); break;
    case 'm': face_ruler(); break;
    case 'l': liquid_start(); break;
  }
}

static void handleLine(char *line) {
  while (*line == ' ') line++;
  char c = line[0]; char *arg = line + 1; while (*arg == ' ') arg++;
  diag_cmd(c);
  switch (c) {
    case 'h': case 'c': case 'm': case 'l': show(c); break;
    case 'f': report_fps(); break;   // query only: does not change the face
    case 'i': imu_stream = !imu_stream; out.printf("imu stream %s\n", imu_stream ? "on (t_ms,ax,ay,az,gx,gy,gz)" : "off"); break;
    case 'g': {
      float v[4] = {0, 0, 0, 0}; const int n = sscanf(arg, "%f %f %f %f", &v[0], &v[1], &v[2], &v[3]);
      if (n >= 2 && !(isfinite(v[0]) && isfinite(v[1]) && isfinite(v[2]) && isfinite(v[3]))) { out.println("usage: g <along> <across> [gyroAlong gyroAcross] | g"); break; }   // sscanf takes nan / inf: they would stick in the filters
      tiltOverride = n >= 2;
      if (tiltOverride) { rawTilt = {v[0], v[1], v[2], v[3]}; have_imu = true; }   // a dead IMU still takes the override
      else have_imu = imu_ok;
      out.printf(tiltOverride ? "tilt override %.3f %.3f gyro %.1f %.1f\n" : "tilt from imu\n", v[0], v[1], v[2], v[3]);
      break; }
    case 'b': { int v = atoi(arg); display_set_brightness(constrain(v, 0, 255)); out.printf("brightness %d\n", v); break; }
    case 'H': { bool on = atoi(arg) != 0; display_set_hbm(on); out.printf("hbm %s\n", on ? "on" : "off"); break; }   // experiment only: tints cyan, browns out the board
    case 't': { int hh = 0, mm = 0, ss = 0; if (sscanf(arg, "%d:%d:%d", &hh, &mm, &ss) >= 2) { setClockLocal(CLOCK_EPOCH_MIN + hh * 3600 + mm * 60 + ss, false); out.printf("time %02d:%02d:%02d\n", hh, mm, ss); } else out.println("usage: t HH:MM[:SS]"); break; }
    case 'T': {  // T <epoch_s> <tz_offset_min>: local time = epoch + tz
      long long ep = 0; int tz = 0;
      if (sscanf(arg, "%lld %d", &ep, &tz) >= 1) { setClockLocal((time_t)(ep + tz * 60L), true); clockSave(); clockSec = clockNow();
        if (HAS_RTC && !rtc_write((time_t)(ep + tz * 60L))) out.println("error rtc write");
        out.printf("time %02d:%02d:%02d\n", (int)clockSec / 3600, ((int)clockSec / 60) % 60, (int)clockSec % 60); }
      else out.println("usage: T <epoch_s> <tz_min>");
      break; }
    case 'd': demoSpeed = atof(arg); demoSave(); out.printf("demo speed x%g\n", demoSpeed); break;
    case 'w': {
      float v = atof(arg);
      if (!(isfinite(v) && v >= 0 && v <= 3600) || (v > 0 && v < 1)) { out.println("usage: w<seconds 1..3600> | w0"); break; }
      sweepPeriod = v; sweepPhase = 0; sweepSave();
      if (v > 0) out.printf("sweep %gs\n", v); else out.println("sweep off");
      break; }
    case 'p': {
      if (arg[0] == '?') dumpParams();
      else if (arg[0] == '!') { params = PRESET_DEFAULT; if (paramsSaved) *paramsSaved = params; paramsChanged(); paramsErase(); out.println("params reset"); }
      else { const bool vol = arg[0] == '~'; if (vol) arg++;
        char *eq = strchr(arg, '='); if (!eq) { out.println("usage: p<name>=<value> | p~<name>=<value> | p? | p!"); break; }
        if (vol && !paramsSaved) { out.println("error p~: no saved copy"); break; }
        *eq = 0; bool ok = setParam(params, arg, eq + 1);
        if (ok) { if (!vol) { if (paramsSaved) setParam(*paramsSaved, arg, eq + 1); paramsTouch(); } paramsChanged(); }
        out.printf(ok ? "ok %s\n" : "unknown param %s\n", arg); }
      break; }
    case 'x': {  // dump state + every strip (hex) for offline comparison with the sim
      display_wait_all(); display_next_strips(strip); dropPending();   // strips re-rendered without the lens map
      const FaceLayout l = currentLayout();   // canvas W H, hours rows, tops, minutes rows (tube widths may differ)
#if TUBE_COUNT == 3
      for (int t = 0; t < 3; t++) renderTube(t, tubeOf(t), effOf(t), paramsGen, strip[t], nullptr, l.top(t));
      out.printf("LAYOUT %d %d %d %d %d %d %d %d\n", PANEL_W, PANEL_H, l.Hh, l.yH, l.yM, l.Hm, l.yS, l.Hs);
#else
      renderTube(0, tubeH, effH, paramsGen, strip[0], nullptr, l.yH); renderTube(1, tubeM, effM, paramsGen, strip[1], nullptr, l.yM);
      out.printf("LAYOUT %d %d %d %d %d %d\n", PANEL_W, PANEL_H, l.Hh, l.yH, l.yM, l.Hm);
#endif
      auto dumpState = [&](const TubeState &t) {
        out.printf(" %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %d %d %d %d",
                   t.fillTarget, t.fillPos, t.angle, t.light, t.edgeLight, t.agitation,
                   t.acrossTilt, t.cap, t.filmFree, t.filmHome, t.slugPos, t.reading, t.pinFree, t.pinHome,
                   t.lineVFree, t.lineVHome, t.rearX16, t.rearY16, t.rearX16w, t.rearY16w);   // the rear parallax as rendered (1/16 px)
      };
      out.print("STATE"); for (int t = 0; t < TUBE_COUNT; t++) dumpState(tubeOf(t)); out.println();
      char *const thex = dumpHex;   // dried-trace residue and its wet part, hex per tube (see compare-device.py)
      auto dumpTrace = [&](const uint16_t *v) {
        if (v) for (int x = 0; x < TUBE_LENGTH_PX; x++) sprintf(thex + x * 4, "%04x", v[x]);
        else thex[0] = 0;
        writeChunked(thex, strlen(thex)); out.print(' ');
      };
      out.print("TRACE "); for (int t = 0; t < TUBE_COUNT; t++) dumpTrace(tubeOf(t).trace); out.println();
      out.print("WET "); for (int t = 0; t < TUBE_COUNT; t++) dumpTrace(tubeOf(t).traceWet); out.println();
      for (int t = 0; t < TUBE_COUNT; t++) {
#if TUBE_COUNT == 3
        // AMOLED: seconds shares the hours strip; whichever of the two is dumped renders again first (the same state)
        if (strip[2] == strip[0] && t != 1) renderTube(t, tubeOf(t), effOf(t), paramsGen, strip[t], nullptr, l.top(t));
#endif
        for (int y = 0; y < l.rows(t); y++) {
          const uint16_t *row = strip[t] + y * PANEL_W; char *o = dumpHex;
          for (int x = 0; x < PANEL_W; x++) { uint16_t c = __builtin_bswap16(row[x]); o += sprintf(o, "%04x", c); }
          *o++ = '\n'; *o = 0; writeChunked(dumpHex, (size_t)(o - dumpHex));
        }
      }
      out.println("END");
      break; }
    case 'X': {  // deterministic sequence (seq.h) on the current params, frame hashes (tools/check_board_steps.py)
      display_wait_all(); display_next_strips(strip); dropPending();   // strips rendered without the lens map, as `x`
      const bool seeded = render_seq_reset(0x5eedu);
      const FaceLayout l = currentLayout();
      const uint32_t t0 = millis();
      TubeState *const tubes[TUBE_COUNT] = {&tubeH, &tubeM,
#if TUBE_COUNT == 3
                                            &tubeS
#endif
      };
      const Params *const ps[TUBE_COUNT] = {&effH, &effM,
#if TUBE_COUNT == 3
                                            &effS
#endif
      };
      int top[TUBE_COUNT]; for (int t = 0; t < TUBE_COUNT; t++) top[t] = l.top(t);
      uint32_t hash[TUBE_COUNT];
      seqRun(tubes, ps, paramsGen, strip, top, [&](int frame, int t, const uint16_t *s) {
        hash[t] = seqHash(s, l.rows(t) * PANEL_W);
        if (t < TUBE_COUNT - 1) return;
        out.printf("SEQ %d", frame);
        for (int i = 0; i < TUBE_COUNT; i++) out.printf(" %08lx", (unsigned long)hash[i]);
        out.print(" fizz");
        for (int i = 0; i < TUBE_COUNT; i++) { int f, sl; const int live = fizzCounts(i, f, sl); out.printf(" %d/%d", live, f); }
        out.println();
        delay(1);   // the idle task (task watchdog)
        diag_feed();
      });
      out.printf("SEQ END %d frames %lu ms%s\n", SEQ_FRAMES, (unsigned long)(millis() - t0), seeded ? "" : " (fizz unseeded: esp_random)");
      clockJumped = true;   // the fills jump back to the clock
      break; }
    case 's': out.printf("mode %c fps %.1f clock %02d:%02d:%02d along %.3f across %.3f gyro %.1f fillH %.3f fillM %.3f heap %u worker-stack-free %u loop-stack-free %u",
                 mode, fps, (int)clockSec / 3600, ((int)clockSec / 60) % 60, (int)clockSec % 60,
                 rawTilt.along, rawTilt.across, rawTilt.gyroAcross, tubeH.fillTarget, tubeM.fillTarget,
                 ESP.getFreeHeap(), (unsigned)workerStackFree, loopTask ? (unsigned)uxTaskGetStackHighWaterMark(loopTask) : 0u);
#if TUBE_COUNT == 3
      out.printf(" fillS %.3f", tubeS.fillTarget);
#endif
#ifdef PIN_BAT_ADC
      out.printf(" bat %.2f V", analogReadMilliVolts(PIN_BAT_ADC) * 2 / 1000.0f);   // 200k / 200k divider
#endif
      out.printf(" temp %d C ble %s", (int)temp_sensor_get_raw_value(nullptr), ble_on() ? "on" : "off");
      out.println(); break;
    case 'v': diag_printf(out, "board %s canvas %dx%d panel %dx%d stack-free worker %u loop %u", BOARD_TAG, PANEL_W, PANEL_H, BOARD_PANEL_W, BOARD_PANEL_H,
                         (unsigned)workerStackFree, loopTask ? (unsigned)uxTaskGetStackHighWaterMark(loopTask) : 0u);   // both render tasks' high-water marks, bytes
      diag_print_v(out);   // one line: device.py reads `v` as one
#ifdef STACK_GUARD
      diag_printf(out, " guard 0x%08lx %d/%d", (unsigned long)(uintptr_t)workerStackMem, guardDamaged(), STACK_GUARD);
#endif
      out.println(); break;
    case 'C': diag_print_core(out); break;   // the last coredump's summary, read at boot
    case 'B':
      if (arg[0] == '0') { out.println("rebooting into fast mode (BLE off)"); ble_request_fast(); }
      else if (arg[0] == '1') { out.println("rebooting into the BLE window"); ble_request_window(); }
      else if (!ble_on()) out.println("mode fast (BLE off)");
      else { const int left = ble_window_left_s(); if (left < 0) out.println("mode ble (connected)"); else out.printf("mode ble (window: fast mode in %d s)\n", left); }
      break;
    case 'r': diag_stage(DIAG_RESTART_REQ); ESP.restart(); break;
    case '?': out.println("cmds: l c h f i g [along across] s b<0-255> t HH:MM T <epoch> <tz> d<N> w<N> p<name>=<v> p~<name>=<v> p? p! x X v C B[0|1] r"); break;
    default: out.println("error unknown command"); break;
  }
  diag_feed();   // -DLOOP_WDT: a completed command
}

void setup() {
  diag_usb_reenum();   // LCD: after a CPU-only reset, make the host re-enumerate before the CDC starts (diag.cpp)
  Serial.begin(115200);
  Serial.setTxTimeoutMs(10);  // bulk CDC writes never wedge loop() (see DualOut::write in ble.cpp)
  uint32_t t = millis();
  while (!Serial && millis() - t < 2500) delay(10);
  static const char *const RST[] = {"unknown", "poweron", "ext", "sw", "panic", "int-wdt", "task-wdt", "wdt",
                                    "deepsleep", "brownout", "sdio", "usb", "jtag", "efuse", "pwr-glitch", "cpu-lockup"};
  int rr = esp_reset_reason();
  out.printf("\nliquid-watch | %s %dx%d | cpu %lu MHz | psram %u KB | heap %u KB | reset %s\n", BOARD_TAG, PANEL_W, PANEL_H,
                getCpuFrequencyMhz(), ESP.getPsramSize() / 1024, ESP.getFreeHeap() / 1024,
                rr >= 0 && rr < 16 ? RST[rr] : "?");
  diag_boot(out);   // previous boot's RTC record, the cached coredump summary (hang diagnostics, diag.h)
  if (!fb.buf) { out.println("FATAL: framebuffer alloc failed"); }
#ifdef BOARD_LCD316
  dumpHex = (char *)heap_caps_malloc(DUMP_HEX_BYTES, MALLOC_CAP_SPIRAM);
  if (!dumpHex) out.println("FATAL: dump buffer alloc failed");
#endif
  // Fast mode (BLE off this boot): the RAM Arduino released from the BT controller takes the face's hottest tables
  // (render_init); the BLE window keeps them in PSRAM so BLE (and the PSRAM timing task) fit.
  const bool dispOk = display_init(); diag_stage(DIAG_DISPLAY);
  const bool renderOk = render_init(!ble_on()), physOk = physics_init(); diag_stage(DIAG_RENDER);
  if (!dispOk) out.println("display init FAILED");
  if (!renderOk) out.println("render init FAILED (glyph pools / mark tables / film tables / lane table, PSRAM)");
  if (!physOk) out.println("physics init FAILED (wet-film buffers, PSRAM): no residue");
#if TUBE_COUNT == 3
  pendMap = (int16_t *)heap_caps_malloc(3 * TUBE_HEIGHT_MAX * sizeof(int16_t), MALLOC_CAP_SPIRAM);
  if (!pendMap) out.println("FATAL: pending lens map alloc failed");
  liquidOk = dispOk && renderOk && physOk && pendMap;   // the seconds tube's state lives in these allocations: no face without them
#endif
#ifdef AB_COMPARE
  out.printf("ab face: native top, %dx%d bottom%s\n", abcmp::width(), abcmp::height(), abcmp::init() ? "" : " - init FAILED");
#endif
  for (int t = 0; t < TUBE_COUNT; t++) {
    tubeOf(t).trace = traceBuf(t);         // dried-trace buffers (see physics.h; seconds' in PSRAM)
    tubeOf(t).traceWet = traceWetBuf(t);   // their wet parts (PSRAM, physics_init)
  }
  display_next_strips(strip);
  workerStart();
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000);   // IMU and RTC share the board bus
#ifdef PIN_BAT_ADC
  analogReadMilliVolts(PIN_BAT_ADC);   // the ADC driver allocates on its first read: at boot, not on the first `s`
#endif
#ifdef NO_IMU   // perf-baseline build (tools/e2e.sh --bare): no I2C polling, tilt stays 0
  have_imu = false;
#else
  have_imu = imu_init();
#endif
  imu_ok = have_imu;
  paramsChanged();   // effH / effM from the built-in preset; paramsLoad replaces it with the NVS copy
  paramsLoad();
  demoLoad();
  sweepLoad();
  out.printf("imu: %s\n", have_imu ? "ok" : "NOT FOUND");
#if HAS_RTC
  out.printf("rtc: %s\n", rtc_init() ? "ok" : "NOT FOUND");   // before clockRestore, which may skip the RTC
#endif
  show(BOOT_MODE);
  clockRestore();
  clockSec = clockNow();
  temperature_sensor_power_acquire();   // `s` reads the die temperature (shared with the PSRAM timing task)
  if (ble_on()) { diag_stage(DIAG_BLE); ble_init("liquid-watch"); }
  out.printf("mode: %s\n", ble_on() ? "ble window (B0 = fast mode now)" : "fast (BLE off; B1 = BLE window)");
  diag_loop_wdt_init(out);   // -DLOOP_WDT: loopTask on the task watchdog, registered once
  diag_setup_done();
  out.println("ready. ? for commands");
}

// Echo only for a human terminal: while the IMU stream is on (the sim's mode) it would interleave with CSV lines.
static void feedByte(char c) {
  static char line[96]; static int n = 0;
  if (c == '\n' || c == '\r') { if (!imu_stream) Serial.println(); if (n) { line[n] = 0; handleLine(line); n = 0; } }
  else if (c == 8 || c == 127) { if (n) { n--; if (!imu_stream) Serial.print("\b \b"); } }   // backspace
  else if (c >= 32 && n < (int)sizeof(line) - 1) { line[n++] = c; if (!imu_stream) Serial.write(c); }
}

void loop() {
  while (Serial.available()) { feedByte(Serial.read()); diag_feed(); }   // -DLOOP_WDT: draining input is progress
  for (int c; (c = ble_read()) >= 0;) { feedByte((char)c); diag_feed(); }
  imu_poll();
  ble_tick();
  paramsFlush();
  clockSaveTick();
  if (mode == 'l') liquid_tick(); else delay(1);
  diag_feed();   // -DLOOP_WDT: one ordinary loop() iteration completed (every mode)
}
