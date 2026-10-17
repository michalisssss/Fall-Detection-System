#include "mqtt_manager.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

static WiFiClient espClient;
static PubSubClient mqttClient(espClient);

// Track the last connection attempt to avoid blocking the loop
static unsigned long lastMQTTAttempt = 0;

// Initialize MQTT connection to the broker - Blocks until connected OR timeout (MQTT_CONNECT_TIMEOUT_MS)
void connectMQTT() {
    unsigned long start = millis();

    while (!mqttClient.connected()) {
        // Give up after MQTT_CONNECT_TIMEOUT_MS
        if (millis() - start > MQTT_CONNECT_TIMEOUT_MS) {
            Serial.println("MQTT connection timeout");
            return;
        }

        Serial.print("Connecting to MQTT broker...");
        if (mqttClient.connect(MQTT_CLIENT_ID)) {
            Serial.println("connected");
        } else {
            Serial.print("failed, rc=");
            Serial.print(mqttClient.state());
            Serial.println(" - retrying in 2s");
            delay(2000);
        }
    }
}

// Ensure MQTT connection is maintained - retries every MQTT_RETRY_INTERVAL_MS to avoid blocking the loop
void ensureMQTTConnected() {
    if (!mqttClient.connected()) {
        if (millis() - lastMQTTAttempt > MQTT_RETRY_INTERVAL_MS) {
            Serial.println("MQTT lost, reconnecting...");
            connectMQTT();
            lastMQTTAttempt = millis();
        }
    }
}

// Process incoming MQTT messages and keep the connection alive
void mqttLoop() {
    mqttClient.loop();
}

// Check if MQTT is connected
bool isMQTTConnected() {
    return mqttClient.connected();
}

// Publish a JSON document to the given topic with retry
static bool publish(const char* topic, JsonDocument& doc, const char* label) {
    // Serialize
    char buffer[256];
    size_t n = serializeJson(doc, buffer);

    // Check for truncation
    if (n >= sizeof(buffer)) {
        Serial.print("WARNING: JSON truncated (");
        Serial.print(label);
        Serial.println(")");
        return false;
    }

    // Try to publish up to 3 times
    for (int attempt = 1; attempt <= 3; attempt++) {
        if (mqttClient.publish(topic, buffer, n)) {
            Serial.print("Published ");
            Serial.println(label);
            return true;
        }
        delay(100); // retry every 0.1 sec
    }

    Serial.print("WARNING: Failed to publish ");
    Serial.println(label);
    return false;
}

// Publish fall event (fall detected or recovery)
void publishFallEvent(bool fall, bool human) {
    if (!mqttClient.connected()) return;

    JsonDocument doc;
    doc["event"] = fall ? "fall" : "state_change";
    doc["fall"] = fall;
    doc["human"] = human;
    doc["room"] = ROOM_NAME;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();  // Uptime in milliseconds

    publish(MQTT_TOPIC_EVENT, doc, "fall event");
}

// Publish a fall escalation event
void publishFallEscalated() {
    if (!mqttClient.connected()) return;

    JsonDocument doc;
    doc["event"] = "fall_escalated";
    doc["room"] = ROOM_NAME;
    doc["reason"] = "no_recovery";
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();

    publish(MQTT_TOPIC_EVENT, doc, "fall_escalated");
}

// Publish a radar failure event when the radar stops sending frames
void publishRadarFailure() {
    if (!mqttClient.connected()) return;

    JsonDocument doc;
    doc["event"] = "radar_failure";
    doc["room"] = ROOM_NAME;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();

    publish(MQTT_TOPIC_EVENT, doc, "radar_failure");
}

// Publish a heartbeat message periodically to indicate the device is alive
void publishHeartbeat() {
    if (!mqttClient.connected()) return;

    JsonDocument doc;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["uptime_ms"] = millis();
    doc["wifi_rssi"] = WiFi.RSSI();
    doc["ip"] = WiFi.localIP().toString();
    doc["mqtt_state"] = mqttClient.state();
    doc["status"] = "alive";

    publish(MQTT_TOPIC_HEARTBEAT, doc, "heartbeat");
}

// Publish a presence update periodically to indicate whether a person is in the room
void publishPresence(bool human) {
    if (!mqttClient.connected()) return;

    JsonDocument doc;
    doc["event"] = "presence_changed";
    doc["human"] = human;
    doc["room"] = ROOM_NAME;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();

    publish(MQTT_TOPIC_EVENT, doc, "presence");
}