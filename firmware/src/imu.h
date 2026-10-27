#pragma once
#include <stdint.h>
#include <stdbool.h>

struct ImuSample {
  float ax, ay, az;   // g
  float gx, gy, gz;   // deg/s
  float temp;         // °C
};

bool imu_init(void);                // QMI8658 on the board I2C bus (Wire begun by setup, pins: board.h)
bool imu_read(ImuSample &s);        // returns false if no new data ready; axes in the reference frame (board.h)
