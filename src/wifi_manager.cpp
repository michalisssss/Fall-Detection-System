#include "wifi_manager.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>

static unsigned long lastWiFiAttempt = 0;

// Connect to the WiFi network (blocking, with timeout)
void connectWiFi() {
    Serial.println("Connecting to WiFi...");

    // Set WiFi mode to client mode (station)
    WiFi.mode(WIFI_STA);

    // Attempt to connect
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    // Wait until connected OR timeout
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - start > WIFI_CONNECT_TIMEOUT_MS) {
            Serial.println("WiFi connection timeout");
            return;
        }
        delay(500);
        Serial.print(".");
    }

    Serial.print("\nWiFi connected. IP: ");
    Serial.println(WiFi.localIP());
}

// Ensure WiFi connection is maintained (non-blocking)
void ensureWiFiConnected() {
    if (WiFi.status() != WL_CONNECTED) {
        if (millis() - lastWiFiAttempt > WIFI_RETRY_INTERVAL_MS) {
            Serial.println("WiFi lost, reconnecting...");
            WiFi.mode(WIFI_STA);
            WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
            lastWiFiAttempt = millis();
        }
    }
}