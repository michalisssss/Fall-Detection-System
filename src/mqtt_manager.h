#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <Arduino.h>

void connectMQTT();
void ensureMQTTConnected();
void mqttLoop();
bool isMQTTConnected();
bool publishFallEvent(bool fall, bool human);
bool publishFallEscalated();
bool publishRadarFailure();
void publishPresence(bool human);
void publishHeartbeat();

#endif