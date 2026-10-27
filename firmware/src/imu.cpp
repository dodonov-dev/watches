// Minimal QMI8658 driver (registers per QMI8658 datasheet / Waveshare qmi8658c.h)
#include "imu.h"
#include <Arduino.h>
#include <Wire.h>
#include "board.h"   // IMU_REF

static uint8_t addr = 0x6B;   // SA0 high on the AMOLED-1.91 and the LCD-3.16 per Waveshare; probe both

enum {
  REG_WHO_AM_I = 0x00, REG_REVISION = 0x01,
  REG_CTRL1 = 0x02, REG_CTRL2 = 0x03, REG_CTRL3 = 0x04, REG_CTRL5 = 0x06, REG_CTRL7 = 0x08,
  REG_STATUS0 = 0x2E, REG_TEMP_L = 0x33, REG_AX_L = 0x35, REG_GX_L = 0x3B,
};
static const float ACC_LSB = 1.0f / 4096.0f;   // ±8g  -> 4096 LSB/g
static const float GYR_LSB = 1.0f / 32.0f;     // ±1024 dps -> 32 LSB/dps

static bool wr(uint8_t r, uint8_t v) {
  Wire.beginTransmission(addr); Wire.write(r); Wire.write(v);
  return Wire.endTransmission() == 0;
}
static bool rd(uint8_t r, uint8_t *buf, size_t n) {
  Wire.beginTransmission(addr); Wire.write(r);
  if (Wire.endTransmission(false) != 0) return false;
  return Wire.requestFrom((int)addr, (int)n) == (int)n && Wire.readBytes(buf, n) == n;
}

bool imu_init(void) {
  uint8_t who = 0;
  for (uint8_t a : {0x6B, 0x6A}) {
    addr = a;
    if (rd(REG_WHO_AM_I, &who, 1) && who == 0x05) break;
    who = 0;
  }
  if (who != 0x05) { log_e("QMI8658 not found (who=0x%02X)", who); return false; }
  log_i("QMI8658 at 0x%02X", addr);
  wr(REG_CTRL1, 0x60);            // address auto-increment, big-endian off (LE), INT disabled
  wr(REG_CTRL2, 0x20 | 0x04);     // accel ±8g, 500 Hz
  wr(REG_CTRL3, 0x60 | 0x04);     // gyro ±1024 dps (0b110<<4), 500 Hz
  wr(REG_CTRL5, 0x00);            // no LPF
  wr(REG_CTRL7, 0x03);            // enable accel + gyro
  delay(10);
  return true;
}

bool imu_read(ImuSample &s) {
  uint8_t st;
  if (!rd(REG_STATUS0, &st, 1) || !(st & 0x03)) return false;
  uint8_t b[14];
  if (!rd(REG_TEMP_L, b, sizeof b)) return false;
  int16_t t  = (int16_t)(b[0] | b[1] << 8);
  int16_t ax = (int16_t)(b[2] | b[3] << 8), ay = (int16_t)(b[4] | b[5] << 8), az = (int16_t)(b[6] | b[7] << 8);
  int16_t gx = (int16_t)(b[8] | b[9] << 8), gy = (int16_t)(b[10] | b[11] << 8), gz = (int16_t)(b[12] | b[13] << 8);
  s.temp = t / 256.0f;
  const int16_t a[3] = {ax, ay, az}, g[3] = {gx, gy, gz};   // board frame -> reference frame (board.h)
  s.ax = IMU_REF(a, 0) * ACC_LSB; s.ay = IMU_REF(a, 1) * ACC_LSB; s.az = IMU_REF(a, 2) * ACC_LSB;
  s.gx = IMU_REF(g, 0) * GYR_LSB; s.gy = IMU_REF(g, 1) * GYR_LSB; s.gz = IMU_REF(g, 2) * GYR_LSB;
  return true;
}
