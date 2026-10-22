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
void connectMQTT(bool singleAttempt) {
    unsigned long start = millis();

    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setSocketTimeout(3);   // give up after 3 seconds if the broker is unreachable

    while (!mqttClient.connected()) {
        // Give up after MQTT_CONNECT_TIMEOUT_MS
        if (millis() - start > MQTT_CONNECT_TIMEOUT_MS) {
            Serial.println("MQTT connection timeout");
            return;
        }

        Serial.print("Connecting to MQTT broker...");
        if (mqttClient.connect(MQTT_CLIENT_ID, 
                                    nullptr, // username
                                    nullptr, // pass
                                    MQTT_TOPIC_STATUS, // topic to be published at
                                    1,  // QoS - it will be sent atleast 1 time
                                    true, // retain - message will be kept for new subscribers
                                    "{\"status\":\"offline\"}")) { // disconnection message {status : offline}
            Serial.println("connected");
            // Publish online status
            mqttClient.publish(MQTT_TOPIC_STATUS, "{\"status\":\"online\"}", true);
        } else {
            Serial.print("failed, rc=");
            Serial.print(mqttClient.state());
            if (singleAttempt) return;   // do not block the main loop
            delay(2000);
        }
    }
}

// Ensure MQTT connection is maintained - retries every MQTT_RETRY_INTERVAL_MS to avoid blocking the loop
void ensureMQTTConnected() {
    if (!mqttClient.connected()) {
        if (millis() - lastMQTTAttempt > MQTT_RETRY_INTERVAL_MS) {
            Serial.println("MQTT lost, reconnecting...");
            connectMQTT(true);
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
        if (mqttClient.publish(topic, (const uint8_t*)buffer, n)) {
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
bool publishFallEvent(bool fall, bool human) {
    if (!mqttClient.connected()) return false;

    JsonDocument doc;
    doc["event"] = fall ? "fall" : "state_change";
    doc["fall"] = fall;
    doc["human"] = human;
    doc["room"] = ROOM_NAME;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();  // Uptime in milliseconds

    return publish(MQTT_TOPIC_EVENT, doc, "fall event");
}

// Publish a fall escalation event
bool publishFallEscalated() {
    if (!mqttClient.connected()) return false;

    JsonDocument doc;
    doc["event"] = "fall_escalated";
    doc["room"] = ROOM_NAME;
    doc["reason"] = "no_recovery";
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();

    return publish(MQTT_TOPIC_EVENT, doc, "fall_escalated");
}

// Publish a radar failure event when the radar stops sending frames
bool publishRadarFailure() {
    if (!mqttClient.connected()) return false;

    JsonDocument doc;
    doc["event"] = "radar_failure";
    doc["room"] = ROOM_NAME;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();

    return publish(MQTT_TOPIC_EVENT, doc, "radar_failure");
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
    static bool lastPresence = false;
    static bool initialized = false;

    if (initialized && human == lastPresence) return;  // no change -> skip 

    JsonDocument doc;
    doc["event"] = "presence_changed";
    doc["human"] = human;
    doc["room"] = ROOM_NAME;
    doc["device_id"] = MQTT_CLIENT_ID;
    doc["timestamp"] = millis();

    if (publish(MQTT_TOPIC_EVENT, doc, "presence")) {
        lastPresence = human;
        initialized = true;
    }

}