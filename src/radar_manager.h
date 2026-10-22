#ifndef RADAR_MANAGER_H
#define RADAR_MANAGER_H

#include <Arduino.h>

void radarInit();
void radarUpdate();
bool radarIsFallConfirmed();
bool radarIsHumanPresent();
void radarCheckTimeout();
void radarResetTimeout();

#endif