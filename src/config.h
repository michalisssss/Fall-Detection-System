#ifndef CONFIG_H
#define CONFIG_H

// LED configuration
#define LED_PIN 15
#define LED_BLINK_INTERVAL_MS 500 // Blink interval (0.5 sec ON, 0.5 sec OFF)

// Buzzer configuration
#define BUZZER_PIN 2 // D2
#define BUZZER_STOP_BTN 9              // XIAO ESP32-C6 BOOT button
#define BUZZER_FALL_DURATION_MS 5000   // 5 seconds beep on fall

// WiFi configuration
#define WIFI_SSID "hotspots"          // hotspot/router SSID #####################################################################
#define WIFI_PASSWORD "passwordss"    // hotspot/router pass #####################################################################
#define WIFI_CONNECT_TIMEOUT_MS 30000 // 30 seconds max for initial connection to the WiFi
#define WIFI_RETRY_INTERVAL_MS 60000  // Retry connecting to the WiFi every 60 seconds

// MQTT configuration
#define MQTT_PORT 1883
#define MQTT_BROKER "X.X.X.X" // Raspberry PI IP #####################################################################
#define MQTT_CLIENT_ID "xiao-fall-detector"
#define MQTT_TOPIC_EVENT "home/fall-detection/events"
#define MQTT_TOPIC_HEARTBEAT "home/fall-detection/heartbeat"
#define MQTT_TOPIC_STATUS  "home/fall-detection/status"
#define MQTT_CONNECT_TIMEOUT_MS 10000 // 10 seconds max for MQTT connection
#define MQTT_RETRY_INTERVAL_MS 15000  // Retry MQTT every 15 seconds

// Room name included in event payloads
#define ROOM_NAME "living_room"

// Timing intervals (in milliseconds)
#define HEARTBEAT_INTERVAL 30000 // 30 seconds between heartbeats
#define PRESENCE_INTERVAL 60000  // 60 seconds between presence updates
#define FALL_CONFIRM_MS 3000     // 3 seconds to confirm fall
#define FALL_CLEAR_MS 2000       // 2 seconds to confirm recovery
#define FALL_ESCALATE_MS 180000  // 3 minutes without recovery -> escalate
#define RADAR_TIMEOUT_MS 10000   // 10 seconds without frames -> radar failure
#define WDT_TIMEOUT_SECONDS 30   // 30 seconds hardware watchdog timeout

#endif