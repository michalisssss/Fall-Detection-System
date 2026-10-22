#include "led_manager.h"
#include "config.h"
#include <Arduino.h>

static unsigned long lastBlinkTime = 0;
static bool blinkState = false;

// Initialize the LED pin as an output and set it to HIGH (OFF)
void ledInit() {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);
    blinkState = false;
}

// Update the LED status based on human presence and fall detection
void ledUpdate(bool human, bool fall) {
    if (fall) { // Fall detected = ON (LOW)
        digitalWrite(LED_PIN, LOW);
        lastBlinkTime = millis();
        return;
    }

    if (human) { // Human present = blink
        unsigned long now = millis();
        if (now - lastBlinkTime >= LED_BLINK_INTERVAL_MS) {
            lastBlinkTime = now;
            blinkState = !blinkState;
            digitalWrite(LED_PIN, blinkState ? LOW : HIGH);
        }
        return;
    }

    // No presence = LED off (HIGH)
    digitalWrite(LED_PIN, HIGH);
    blinkState = false;
}