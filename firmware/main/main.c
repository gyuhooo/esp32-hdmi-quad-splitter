#include "lt86104.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "app";

void app_main(void)
{
    ESP_ERROR_CHECK(lt86104_bus_init());
    lt86104_hw_reset();

    uint8_t found[8];
    int n = lt86104_scan(found, 8);
    ESP_LOGI(TAG, "%d I2C device(s) found", n);

    for (int i = 0; i < n; i++) {
        esp_err_t r = lt86104_init(found[i]);
        ESP_LOGI(TAG, "init 0x%02X -> %s", found[i], esp_err_to_name(r));
    }

    while (1) {
        // TODO: INT ピン監視、状態の Wi-Fi 公開
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
