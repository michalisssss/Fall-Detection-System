#ifndef BUZZER_MANAGER_H
#define BUZZER_MANAGER_H

#include <Arduino.h>

void buzzerInit();
void buzzerBeep(unsigned long duration_ms);
void buzzerOff();
void buzzerUpdate();

#endif