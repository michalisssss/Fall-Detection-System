#include "watchdog_manager.h"
#include "config.h"
#include <Arduino.h>
#include <esp_task_wdt.h>

// Initialize the hardware watchdog
void watchdogInit() {
    // Release the default watchdog configuration
    esp_task_wdt_deinit();

    // New watchdog configuration
    esp_task_wdt_config_t wdt_config = {
        .timeout_ms      = WDT_TIMEOUT_SECONDS * 1000,  // 30 seconds
        .idle_core_mask  = 0,      // Do not monitor the idle task
        .trigger_panic   = true    // Trigger a reboot on timeout
    };

    // Apply configuration
    if (esp_task_wdt_init(&wdt_config) != ESP_OK) {
        Serial.println("WARNING: Watchdog initialization failed");
        return;
    }

    // Register the current loopTask for the watchdog to monitor
    if (esp_task_wdt_add(NULL) != ESP_OK) { // NULL refers to the task that calls the watchdog
        Serial.println("WARNING: Watchdog add failed");
        return;
    }

    Serial.println("Hardware watchdog enabled");
}

// Feed the watchdog to prevent a system reset
void watchdogFeed() {
    esp_task_wdt_reset();
}