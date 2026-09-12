#include "lt86104.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

static const char *TAG = "lt86104";

// Lontium 提供の初期化テーブルをここに置く({reg, val} の並び)。
// データシート/リファレンスコードは NDA 下で配布されるため、リポジトリには含めない。
static const uint8_t INIT_TABLE[][2] = {
    // {0xFF, 0x80}, // 例: ページ切替
};

esp_err_t lt86104_bus_init(void)
{
    i2c_config_t cfg = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = LT86104_PIN_SDA,
        .scl_io_num = LT86104_PIN_SCL,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = LT86104_I2C_HZ,
    };
    ESP_ERROR_CHECK(i2c_param_config(LT86104_I2C_PORT, &cfg));
    ESP_ERROR_CHECK(i2c_driver_install(LT86104_I2C_PORT, cfg.mode, 0, 0, 0));

    gpio_config_t rst = {
        .pin_bit_mask = 1ULL << LT86104_PIN_RESET,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&rst));
    gpio_config_t irq = {
        .pin_bit_mask = 1ULL << LT86104_PIN_INT,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&irq));
    return ESP_OK;
}

void lt86104_hw_reset(void)
{
    gpio_set_level(LT86104_PIN_RESET, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(LT86104_PIN_RESET, 1);
    vTaskDelay(pdMS_TO_TICKS(50));
}

int lt86104_scan(uint8_t *found, int max)
{
    int n = 0;
    for (uint8_t a = 0x08; a < 0x78 && n < max; a++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (a << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t r = i2c_master_cmd_begin(LT86104_I2C_PORT, cmd, pdMS_TO_TICKS(20));
        i2c_cmd_link_delete(cmd);
        if (r == ESP_OK) {
            ESP_LOGI(TAG, "found device at 0x%02X", a);
            found[n++] = a;
        }
    }
    return n;
}

esp_err_t lt86104_write_reg(uint8_t addr, uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = {reg, val};
    return i2c_master_write_to_device(LT86104_I2C_PORT, addr, buf, 2, pdMS_TO_TICKS(50));
}

esp_err_t lt86104_read_reg(uint8_t addr, uint8_t reg, uint8_t *val)
{
    return i2c_master_write_read_device(LT86104_I2C_PORT, addr, &reg, 1, val, 1, pdMS_TO_TICKS(50));
}

esp_err_t lt86104_init(uint8_t addr)
{
    size_t n = sizeof(INIT_TABLE) / sizeof(INIT_TABLE[0]);
    if (n == 0) {
        ESP_LOGW(TAG, "INIT_TABLE is empty; fill it from the Lontium reference code");
        return ESP_ERR_NOT_SUPPORTED;
    }
    for (size_t i = 0; i < n; i++) {
        esp_err_t r = lt86104_write_reg(addr, INIT_TABLE[i][0], INIT_TABLE[i][1]);
        if (r != ESP_OK) {
            ESP_LOGE(TAG, "write reg 0x%02X failed: %s", INIT_TABLE[i][0], esp_err_to_name(r));
            return r;
        }
    }
    return ESP_OK;
}
