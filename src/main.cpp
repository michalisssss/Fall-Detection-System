#include <Arduino.h>
#include "config.h"
#include "wifi_manager.h"
#include "mqtt_manager.h"
#include "radar_manager.h"
#include "led_manager.h"
#include "watchdog_manager.h"
#include "buzzer_manager.h"

static unsigned long lastHeartbeat = 0;
static unsigned long lastPresenceUpdate = 0;

void setup() {
    Serial.begin(115200);
    while (!Serial);

    // Initialize hardware
    buzzerInit();
    ledInit();
    radarInit();

    // Connect to network
    connectWiFi();
    connectMQTT();

    // Enable watchdog
    watchdogInit();

    Serial.println("System ready");
}

void loop() {
    // Ensure WiFi connection
    ensureWiFiConnected();

    // Ensure MQTT connection
    ensureMQTTConnected();

    // Process incoming MQTT messages (if any)
    mqttLoop();

    // Process the next radar frame and take action according to fall state
    radarUpdate();

    // Radar watchdog - radar failure check
    radarCheckTimeout();

    // LED update depending human pressence and fall state
    ledUpdate(radarIsHumanPresent(), radarIsFallConfirmed());

    // Buzzer handling either by button press or timeout
    buzzerUpdate();

    // Periodic device heartbeat
    if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
        publishHeartbeat();
        lastHeartbeat = millis();
    }

    // Periodic human presence update
    if (millis() - lastPresenceUpdate > PRESENCE_INTERVAL) {
        publishPresence(radarIsHumanPresent());
        lastPresenceUpdate = millis();
    }

    // Feed watchdog so it doesnt reset the system
    watchdogFeed();

    delay(100); // TODO: test if delay is needed (mmWave.update already has 100ms timeout)
}