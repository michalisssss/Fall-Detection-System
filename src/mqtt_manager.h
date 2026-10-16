#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <Arduino.h>

void connectMQTT();
void ensureMQTTConnected();
void mqttLoop();
bool isMQTTConnected();
void publishFallEvent(bool fall, bool human);
void publishFallEscalated();
void publishPresence(bool human);
void publishHeartbeat();
void publishRadarFailure();

#endif