#pragma once
#include <stdint.h>
#include "esp_err.h"

// ピン割り当て(ボードに合わせて変更)
#define LT86104_I2C_PORT   0
#define LT86104_PIN_SDA    21
#define LT86104_PIN_SCL    22
#define LT86104_PIN_RESET  4
#define LT86104_PIN_INT    5
#define LT86104_I2C_HZ     100000

esp_err_t lt86104_bus_init(void);
void      lt86104_hw_reset(void);
int       lt86104_scan(uint8_t *found, int max);
esp_err_t lt86104_write_reg(uint8_t addr, uint8_t reg, uint8_t val);
esp_err_t lt86104_read_reg(uint8_t addr, uint8_t reg, uint8_t *val);
esp_err_t lt86104_init(uint8_t addr);
