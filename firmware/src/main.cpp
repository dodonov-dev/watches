// Liquid Watch firmware — liquid face (port of the sim) + Phase 1 bring-up faces.
// Serial commands (115200, USB CDC; same protocol over BLE Nordic UART Service, name "liquid-watch"):
//   l  liquid face (default)          c  calibration face        h  hello / orientation test
//   f  live fps + frame timing        i  toggle IMU stream (50 Hz CSV)
//   g <along> <across> [gyroAlong gyroAcross]  tilt override in g / dps instead of the IMU (bench poses without
//      touching the board; not persisted)   g  back to the IMU
//   t HH:MM[:SS]  set clock           d<N>  demo time speed ×N (d1 = real time, d0 = freeze; persists in NVS)
//   T <epoch_s> <tz_min>  set clock from the sim (persists in NVS, re-saved each minute; power-on resumes from it,
//      or from the RTC on boards with one: board.h HAS_RTC)
//   w<N>  minutes sweep: the minutes tube runs empty→full→empty every N s, hours keep the clock (w0 = off; persists in NVS)
//   p<name>=<value>  set a param (e.g. p liquid=#39ff14, p fizz=0, p contactAngle=140)
//   p?  dump params as JSON           p!  reset params to the built-in preset (and erase NVS copy)
//   params persist in NVS (autosave 2 s after last p write)
//   b<n> brightness 0..255            H<0|1>  panel HBM experiment (RM67162 B0h; unusable, see KAIZEN)
//   r  reboot
#include <Arduino.h>
#include <Preferences.h>
#include <Adafruit_GFX.h>
#include <Wire.h>
#include <sys/time.h>
#include "esp_heap_caps.h"
#include "layout.h"
#include "board.h"
#include "display.h"
#include "imu.h"
#include "ble.h"
#include "rtc.h"
#include "physics.h"
#include "render.h"
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
static Params params = PRESET_DEFAULT;
static uint32_t paramsGen = 1;   // bumped on every param change; renderer caches key on it
// NVS autosave: namespace lw, blob cur. Written 2 s after the last change; ignored if the schema CRC differs.
static Preferences prefs;
static uint32_t paramsDirtyAt = 0;
static void paramsLoad() {
  prefs.begin("lw", false);
  if (prefs.getUInt("crc") == PARAMS_SCHEMA_CRC && prefs.getBytesLength("cur") == sizeof(Params)) {
    prefs.getBytes("cur", &params, sizeof(Params)); paramsGen++; out.println("params: restored from nvs");
  }
}
static void paramsTouch() { paramsDirtyAt = millis() | 1; }
static void paramsFlush() {
  if (!paramsDirtyAt || millis() - paramsDirtyAt < 2000) return;
  paramsDirtyAt = 0;
  prefs.putBytes("cur", &params, sizeof(Params)); prefs.putUInt("crc", PARAMS_SCHEMA_CRC);
}
static void paramsErase() { paramsDirtyAt = 0; prefs.remove("cur"); prefs.remove("crc"); }
static TubeState tubeH, tubeM;
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
  clockJumped = false;
}
static uint32_t lastPhysUs = 0, frames = 0, fpsT0 = 0;
static float fps = 0;
static uint32_t renderUs = 0, waitUs = 0;          // accumulated over the current fps window
static uint32_t hoursUs = 0, minutesUs = 0;        // per-core render time (hours on core 0, minutes here)
static uint32_t tubeStepUs = 0, fizzStepUs = 0, physSteps = 0, pushUs = 0, restUs = 0;   // physics split, strip hand-over, loop() outside liquid_tick
static uint32_t lastTickEndUs = 0, fizzStepMaxUs = 0;
static float tubeStepMs = 0, fizzStepMs = 0, fizzStepMaxMs = 0, stepsPerFrame = 0, pushMs = 0, restMs = 0;   // tube/fizz: per physics step; the rest per frame
static bool tiltOverride = false;                  // `g`: rawTilt comes from the serial line, not the IMU
static float renderMs = 0, waitMs = 0, hoursMs = 0, minutesMs = 0;   // per-frame averages of the last window
static uint16_t frameIntervalHist[256];             // 1 ms bins; bin 255 includes all slower frames
static uint32_t lastFrameStartUs = 0, frameIntervalSamples = 0;
static uint16_t frameP95Ms = 0;
// Tube strips (owned by display.cpp, internal DMA RAM): the panel DMA reads them directly while the
// next frame renders.
static uint16_t *strip[2] = {nullptr, nullptr};
static char dumpHex[PANEL_W * 4 + 2];

struct DisplayLayout {
  int H, yH, yM;
  bool operator!=(const DisplayLayout &o) const { return H != o.H || yH != o.yH || yM != o.yM; }
};
static DisplayLayout currentLayout() {
  TubeLayout l = tubeLayout(params);
  return {l.H, l.yH, l.yM};
}
static void renderOneTube(int idx, uint16_t *dst) {
  renderTube(idx, idx == 0 ? tubeH : tubeM, params, paramsGen, dst);
}

static DisplayLayout shownLayout = {0, 0, 0};

// ---- hours-tube worker on core 0 (the Arduino loop runs on core 1) ----
// The two tubes are independent, so each frame renders them at the same time: the worker draws hours
// into strip[0] while loop() draws minutes into strip[1]. Hand-shake by task notification: loop()
// gives the worker one notification per frame and blocks on its own until the worker is done, so at
// any point outside renderBoth() the worker is idle and blocked (serial commands, param writes, the
// physics step and `x` all run in that window — nothing they touch is being read on core 0).
// Priority 1 = same as loop(); far below the BT controller (23) and NimBLE host on the same core, and
// the worker blocks every frame so core 0's idle task (task-WDT) keeps running.
#define WORKER_PRIO 1
#define WORKER_STACK 4096   // measured use ~1.5 KB
static TaskHandle_t workerTask = nullptr, loopTask = nullptr;
static uint32_t workerUs = 0;              // last hours render time, written by the worker
static uint32_t workerStackFree = 0;       // high-water mark (bytes on ESP-IDF), for `s`
static void renderWorker(void *) {
  for (;;) {
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    uint32_t t0 = micros();
    renderOneTube(0, strip[0]);
    workerUs = micros() - t0;
    workerStackFree = uxTaskGetStackHighWaterMark(nullptr);
    xTaskNotifyGive(loopTask);
  }
}
static void workerStart() {
  loopTask = xTaskGetCurrentTaskHandle();
  xTaskCreatePinnedToCore(renderWorker, "render0", WORKER_STACK, nullptr, WORKER_PRIO, &workerTask, 0);
}

static void renderBoth() {
  DisplayLayout lay = currentLayout();
  if (lay != shownLayout) {                 // tubes moved: wipe the rows they used to cover
    display_wait_all();
    fb.fillScreen(0); display_push_frame(fb.buf);
    shownLayout = lay;
  }
  uint32_t t0 = micros();
  display_wait_pending(display_bands(lay.H));   // previous frame: hours strip pushed first → free once only minutes' bands remain
  uint32_t t1 = micros();
  xTaskNotifyGive(workerTask);                  // hours → core 0
  display_wait_all();                           // minutes strip free (overlaps the hours render)
  uint32_t t2 = micros();
  renderOneTube(1, strip[1]);
  uint32_t t3 = micros();
  ulTaskNotifyTake(pdTRUE, portMAX_DELAY);      // hours done
  uint32_t t4 = micros();
  display_push_strip_async(strip[0], lay.yH, lay.H);
  display_push_strip_async(strip[1], lay.yM, lay.H);
  pushUs += micros() - t4;                      // each band's window command waits for the band before it
  renderUs += t4 - t1; waitUs += t1 - t0;       // render = wall time of the concurrent section
  hoursUs += workerUs; minutesUs += t3 - t2;
}

static void face_hello() {
  fb.fillScreen(0);
  fb.drawRect(0, 0, PANEL_W, PANEL_H, 0xFFFF);
  fb.setTextColor(0xFFFF); fb.setTextSize(4);
  fb.setCursor(120, 90); fb.print("hello liquid");
  fb.setTextSize(2);
  fb.setCursor(8, 8);   fb.print("<- LEFT (USB-C here?)");
  fb.setCursor(8, 216); fb.print("bottom-left");
  fb.setCursor(400, 216); fb.print("bottom-right");
  fb.fillRect(20, 150, 60, 40, 0xF800);
  fb.fillRect(90, 150, 60, 40, 0x07E0);
  fb.fillRect(160, 150, 60, 40, 0x001F);
  fb.fillRect(230, 150, 60, 40, LIQUID_RGB565);
  fb.fillRect(300, 150, 60, 40, LIQUID_HI_RGB565);
  display_push_frame(fb.buf);
}

static void face_calibration() {
  fb.fillScreen(0);
  fb.fillRect(0, HOURS_TUBE_Y,   TUBE_LENGTH_PX, TUBE_HEIGHT_PX, LIQUID_RGB565);
  fb.fillRect(0, MINUTES_TUBE_Y, TUBE_LENGTH_PX, TUBE_HEIGHT_PX, LIQUID_RGB565);
  fb.drawFastHLine(0, HOURS_TUBE_Y + TUBE_HEIGHT_PX / 2,   PANEL_W, 0xFFFF);
  fb.drawFastHLine(0, MINUTES_TUBE_Y + TUBE_HEIGHT_PX / 2, PANEL_W, 0xFFFF);
  fb.drawFastVLine(PANEL_W / 2, HOURS_TUBE_Y, TUBE_HEIGHT_PX, 0xFFFF);
  fb.drawFastVLine(PANEL_W / 2, MINUTES_TUBE_Y, TUBE_HEIGHT_PX, 0xFFFF);
  display_push_frame(fb.buf);
}

// Live figures of whatever the loop is rendering (2 s rolling window, see liquid_tick).
static void report_fps() {
  int foamH = 0, foamM = 0, slotsH = 0, slotsM = 0; const int fizzH = fizzCounts(0, foamH, slotsH), fizzM = fizzCounts(1, foamM, slotsM);
  out.printf("fps %.1f  render %.2f ms  push-wait %.2f ms  cores h %.2f / m %.2f ms  (mode %c, transp %.2f)  frame-p95 %u ms"
             "  phys %.2f steps x (tube %.2f + fizz %.2f ms, max %.2f)  push %.2f ms  rest %.2f ms  fizz h %d (foam %d, slots %d) m %d (foam %d, slots %d)\n",
             fps, renderMs, waitMs, hoursMs, minutesMs, mode, params.liquidTransparency,
             (unsigned)frameP95Ms, stepsPerFrame, tubeStepMs, fizzStepMs, fizzStepMaxMs, pushMs, restMs, fizzH, foamH, slotsH, fizzM, foamM, slotsM);
#ifdef DIGIT_PROF
  for (int i = 0; i < 2; i++) {
    const uint32_t *c = render_profile(i);
    out.printf("digit-prof %c glyphs %u rows %u int-plain %u int-liq %u frac-plain %u frac-liq %u slow %u runs %u\n",
               i ? 'm' : 'h', (unsigned)c[0], (unsigned)c[1], (unsigned)c[2], (unsigned)c[3], (unsigned)c[4], (unsigned)c[5], (unsigned)c[6], (unsigned)c[7]);
  }
#endif
}

// ---- liquid face ----
static void liquid_start() {
  fb.fillScreen(0);
  display_push_frame(fb.buf);
  display_set_brightness(255);   // params.brightness is applied in the render LUTs
  updateTimeTargets(0);
  memset(frameIntervalHist, 0, sizeof(frameIntervalHist));
  lastFrameStartUs = 0; frameIntervalSamples = 0; frameP95Ms = 0;
  lastPhysUs = micros(); frames = 0; fpsT0 = millis();
  tubeStepUs = fizzStepUs = physSteps = pushUs = restUs = fizzStepMaxUs = 0; lastTickEndUs = 0;   // no time spent on another face in the first window
  renderUs = waitUs = hoursUs = minutesUs = 0;
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
  while ((int32_t)(now - lastPhysUs) >= (int32_t)(1000000 / PHYS_HZ) && steps < 5) {
    lastPhysUs += 1000000 / PHYS_HZ; steps++;
    demoOffset += PHYS_DT * (demoSpeed - 1);
    if (sweepPeriod > 0) sweepPhase = fmod(sweepPhase + PHYS_DT / sweepPeriod, 1.0);
    updateTimeTargets(PHYS_DT);
    TiltInput in = have_imu ? imuFilter.step(rawTilt, params) : TiltInput{0, 0, 0, 0};
    const uint32_t p0 = micros();
    stepTube(tubeH, in, params);
    stepTube(tubeM, in, params);
    const uint32_t p1 = micros();
    stepFizz(params, PHYS_DT, in.along, in.across, tubeH.agitation);
    const uint32_t fz = micros() - p1;
    tubeStepUs += p1 - p0; fizzStepUs += fz; physSteps++;
    if (fz > fizzStepMaxUs) fizzStepMaxUs = fz;
  }
  renderBoth();
  frames++;
  {   // fizz asked past its fixed pool (params pushed past the sliders): say so once per new peak
    static int reported = 0; const int over = fizzOverflow();
    if (over > reported) { reported = over; out.printf("error fizz pool: %d bubbles requested, fixed pool holds fewer (capped)\n", over); }
  }
  if (millis() - fpsT0 >= 2000) {
    fps = frames * 1000.0f / (millis() - fpsT0);
    renderMs = renderUs / 1000.0f / frames; waitMs = waitUs / 1000.0f / frames;
    hoursMs = hoursUs / 1000.0f / frames; minutesMs = minutesUs / 1000.0f / frames;
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
    frames = 0; renderUs = waitUs = hoursUs = minutesUs = 0; fpsT0 = millis();
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
static bool setParam(const char *name, const char *val) {
  const ParamField *f = findField(name); if (!f) return false;
  uint8_t *p = (uint8_t *)&params + f->off;
  switch (f->type) {
    case 'f': *(float *)p = atof(val); break;
    case 'i': *(int *)p = atoi(val); break;
    case 'b': *(bool *)p = !(val[0] == '0' || val[0] == 'f' || val[0] == 'F' || val[0] == 'n'); break;
    case 'c': *(uint32_t *)p = strtoul(val[0] == '#' ? val + 1 : val, nullptr, 16); break;
  }
  return true;
}
static void dumpParams() {
  out.print("{");
  for (int i = 0; i < PARAMS_NUM_FIELDS; i++) {
    const ParamField &f = PARAM_FIELDS[i]; const uint8_t *p = (const uint8_t *)&params + f.off;
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

static void show(char m) {
  display_wait_all();
  mode = m;
  switch (m) {
    case 'h': face_hello(); break;
    case 'c': face_calibration(); break;
    case 'l': liquid_start(); break;
  }
}

static void handleLine(char *line) {
  while (*line == ' ') line++;
  char c = line[0]; char *arg = line + 1; while (*arg == ' ') arg++;
  switch (c) {
    case 'h': case 'c': case 'l': show(c); break;
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
      else if (arg[0] == '!') { params = PRESET_DEFAULT; paramsGen++; paramsErase(); out.println("params reset"); }
      else { char *eq = strchr(arg, '='); if (!eq) { out.println("usage: p<name>=<value> | p? | p!"); break; }
        *eq = 0; bool ok = setParam(arg, eq + 1); if (ok) { paramsGen++; paramsTouch(); }
        out.printf(ok ? "ok %s\n" : "unknown param %s\n", arg); }
      break; }
    case 'x': {  // dump state + both strips (hex) for offline comparison with the sim
      display_wait_all();
      renderTube(0, tubeH, params, paramsGen, strip[0]); renderTube(1, tubeM, params, paramsGen, strip[1]);
      auto dumpState = [&](const TubeState &t) {
        out.printf(" %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f",
                   t.fillTarget, t.fillPos, t.angle, t.light, t.edgeLight, t.agitation,
                   t.acrossTilt, t.cap, t.filmFree, t.filmHome, t.slugPos, t.reading, t.pinFree, t.pinHome,
                   t.lineVFree, t.lineVHome);
      };
      out.print("STATE"); dumpState(tubeH); dumpState(tubeM); out.println();
      static char thex[TUBE_LENGTH_PX * 4 + 1];   // dried-trace residue and its wet part, hex per tube (see compare-device.py)
      auto dumpTrace = [&](const uint16_t *v) {
        if (v) for (int x = 0; x < TUBE_LENGTH_PX; x++) sprintf(thex + x * 4, "%04x", v[x]);
        else thex[0] = 0;
        out.print(thex); out.print(' ');
      };
      out.print("TRACE "); dumpTrace(tubeH.trace); dumpTrace(tubeM.trace); out.println();
      out.print("WET "); dumpTrace(tubeH.traceWet); dumpTrace(tubeM.traceWet); out.println();
      for (int t = 0; t < 2; t++) for (int y = 0; y < tubeLayout(params).H; y++) {
        const uint16_t *row = strip[t] + y * PANEL_W; char *o = dumpHex;
        for (int x = 0; x < PANEL_W; x++) { uint16_t c = __builtin_bswap16(row[x]); o += sprintf(o, "%04x", c); }
        *o++ = '\n'; *o = 0; out.write(dumpHex);
      }
      out.println("END");
      break; }
    case 's': out.printf("mode %c fps %.1f clock %02d:%02d:%02d along %.3f across %.3f gyro %.1f fillH %.3f fillM %.3f heap %u worker-stack-free %u",
                 mode, fps, (int)clockSec / 3600, ((int)clockSec / 60) % 60, (int)clockSec % 60,
                 rawTilt.along, rawTilt.across, rawTilt.gyroAcross, tubeH.fillTarget, tubeM.fillTarget,
                 ESP.getFreeHeap(), (unsigned)workerStackFree);
#ifdef PIN_BAT_ADC
      out.printf(" bat %.2f V", analogReadMilliVolts(PIN_BAT_ADC) * 2 / 1000.0f);   // 200k / 200k divider
#endif
      out.println(); break;
    case 'r': ESP.restart(); break;
    case '?': out.println("cmds: l c h f i g [along across] s b<0-255> t HH:MM T <epoch> <tz> d<N> w<N> p<name>=<v> p? p! x r"); break;
    default: out.println("error unknown command"); break;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(10);  // bulk CDC writes never wedge loop() (see DualOut::write in ble.cpp)
  uint32_t t = millis();
  while (!Serial && millis() - t < 2500) delay(10);
  static const char *const RST[] = {"unknown", "poweron", "ext", "sw", "panic", "int-wdt", "task-wdt", "wdt",
                                    "deepsleep", "brownout", "sdio", "usb", "jtag", "efuse", "pwr-glitch", "cpu-lockup"};
  int rr = esp_reset_reason();
  out.printf("\nliquid-watch | %s | cpu %lu MHz | psram %u KB | heap %u KB | reset %s\n", BOARD_NAME,
                getCpuFrequencyMhz(), ESP.getPsramSize() / 1024, ESP.getFreeHeap() / 1024,
                rr >= 0 && rr < 16 ? RST[rr] : "?");
  if (!fb.buf) { out.println("FATAL: framebuffer alloc failed"); }
  if (!display_init()) out.println("display init FAILED");
  if (!render_init()) out.println("render init FAILED (glyph pools / mark tables / film tables, PSRAM)");
  if (!physics_init()) out.println("physics init FAILED (wet-film buffers, PSRAM): no residue");
  tubeH.trace = traceBuf(0); tubeM.trace = traceBuf(1);   // static dried-trace buffers (see physics.h)
  tubeH.traceWet = traceWetBuf(0); tubeM.traceWet = traceWetBuf(1);   // their wet parts (PSRAM, physics_init)
  strip[0] = display_strip(0); strip[1] = display_strip(1);
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
  ble_init("liquid-watch");
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
  while (Serial.available()) feedByte(Serial.read());
  for (int c; (c = ble_read()) >= 0;) feedByte((char)c);
  imu_poll();
  paramsFlush();
  clockSaveTick();
  if (mode == 'l') liquid_tick(); else delay(1);
}
