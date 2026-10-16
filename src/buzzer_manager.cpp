#include "buzzer_manager.h"
#include "config.h"
#include <Arduino.h>

// Internal state
static unsigned long beepStartTime = 0;
static unsigned long beepDuration = 0;
static unsigned long lastButtonCheck = 0;
static bool lastButtonState = HIGH;
static bool beeping = false;

// Initialize the buzzer pin and the stop button
void buzzerInit() {
    // Buzzer pin
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);

    // Stop button with internal pull-up (pressed = LOW, released = HIGH)
    pinMode(BUZZER_STOP_BTN, INPUT_PULLUP);
}

// Start a non-blocking beep
void buzzerBeep(unsigned long duration_ms) {
    digitalWrite(BUZZER_PIN, HIGH);
    beepStartTime = millis();
    beepDuration = duration_ms;
    beeping = true;
    lastButtonState = digitalRead(BUZZER_STOP_BTN);
}

// Turn the buzzer off
void buzzerOff() {
    digitalWrite(BUZZER_PIN, LOW);
    beeping = false;
}

// Update buzzer
void buzzerUpdate() {
    if (!beeping) return;

    // Buzzer off by timeout
    if (millis() - beepStartTime >= beepDuration) {
        buzzerOff();
        return;
    }

    // Buzzer off by button
    if (digitalRead(BUZZER_STOP_BTN) == LOW) {
        buzzerOff();
        Serial.println("[buzzer] Stopped by user button");
    }
}
