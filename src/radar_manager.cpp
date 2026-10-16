#include "radar_manager.h"
#include "config.h"
#include "mqtt_manager.h"
#include <Arduino.h>
#include "Seeed_Arduino_mmWave.h"
#include <Preferences.h>
#include "buzzer_manager.h"

// Radar
static HardwareSerial mmWaveSerial(0);
static SEEED_MR60FDA2 mmWave;
static Preferences prefs;

// State machine
enum RadarState {
    STATE_IDLE,             // No fall - nobody down
    STATE_PENDING_FALL,     // Fall candidate - awaiting confirmation
    STATE_FALL,             // Confirmed fall
    STATE_PENDING_RECOVERY  // Fall cleared - awaiting recovery confirmation
};

// Set default state
static RadarState state = STATE_IDLE;

// Timestamps
static unsigned long fallDetectedAt = 0;    // when the fall candidate started
static unsigned long lastRadarFrame = 0;    // last valid frame timestamp
static unsigned long fallConfirmedAt = 0;   // when the fall was confirmed
static unsigned long recoveryStartedAt = 0; // when recovery started

// Flags
static bool lastFallState = false;  // confirmed fall
static bool radarWarningSent = false;  // radar-failure already sent
static bool fallEscalated = false;  // escalation already sent

// Initialization
void radarInit() {
    // Restore last fall state from NVS
    if (!prefs.begin("fall", false)) {
        Serial.println("WARNING: NVS init failed, using defaults");
    }
    lastFallState = prefs.getBool("lastFall", false);

    if (lastFallState) {
        state = STATE_FALL;
        fallConfirmedAt = millis();
        Serial.println("Restored FALL state (escalation timer reset)");
    } else {
        state = STATE_IDLE;
        Serial.println("Restored IDLE state");
    }

    fallEscalated = false;

    // Initialize UART for the radar
    mmWaveSerial.begin(115200);
    mmWave.begin(&mmWaveSerial);
    Serial.println("MR60FDA2 ready");

    // Give the radar a grace period before the watchdog can fire
    lastRadarFrame = millis() - (RADAR_TIMEOUT_MS / 2);
}

// Process the next radar frame and take action according to fall state
void radarUpdate() {
    // Read the next radar frame if ready
    if (!mmWave.update(100)) {
        return;
    }

    // Frame is valid - refresh health timestamp
    lastRadarFrame = millis();
    radarWarningSent = false;

    bool human = mmWave.getHuman();
    bool fall  = mmWave.getFall();

    switch (state) {
        case STATE_IDLE: // no fall - nobody down
            if (fall) {
                state = STATE_PENDING_FALL;
                fallDetectedAt = millis();
                Serial.println("Fall candidate detected, confirming...");
            }
            break;

        case STATE_PENDING_FALL: // fall candidate - awaiting confirmation
            if (!fall) { // Signal lost before fall confirmation - cancel
                state = STATE_IDLE;
                Serial.println("Fall candidate cancelled (signal lost)");
            } else if (millis() - fallDetectedAt >= FALL_CONFIRM_MS) {
                // Fall confirmed -> publish, beep, and move to STATE_FALL
                publishFallEvent(true, human);
                lastFallState = true;
                fallConfirmedAt = millis();
                fallEscalated = false;
                prefs.putBool("lastFall", true);
                buzzerBeep(BUZZER_FALL_DURATION_MS);
                state = STATE_FALL;
                Serial.println("FALL CONFIRMED");
            }
            break;

        case STATE_FALL: // confirmed fall 
            if (!fall) { // Fall cleared -> start recovery confirmation
                state = STATE_PENDING_RECOVERY;
                recoveryStartedAt = millis();
                Serial.println("Fall cleared, confirming recovery...");
            } else if (!fallEscalated && (millis() - fallConfirmedAt >= FALL_ESCALATE_MS)) {
                // Fall persists without recovery -> escalate
                fallEscalated = true;
                Serial.println("FALL ESCALATED (no recovery)");
                publishFallEscalated();
            }
            break;
        
        case STATE_PENDING_RECOVERY: // fall cleared - awaiting confirmation
            if (fall) { // Fall signal returned: cancel recovery - reset escalation timer
                fallConfirmedAt = millis();
                state = STATE_FALL;
                Serial.println("Recovery cancelled (fall signal returned)");
            } else if (millis() - recoveryStartedAt >= FALL_CLEAR_MS) {
                // Recovery confirmed
                publishFallEvent(false, human);
                lastFallState = false;
                fallEscalated = false;
                prefs.putBool("lastFall", false);
                state = STATE_IDLE;
                Serial.println("RECOVERY CONFIRMED");
            }
            break;
    }
}

// Radar watchdog
void radarCheckTimeout() {
    if (!radarWarningSent && (millis() - lastRadarFrame > RADAR_TIMEOUT_MS)) {
        Serial.println("WARNING: no radar frames received");
        publishRadarFailure();
        radarWarningSent = true;
    }
}

// Radar getters
bool radarIsFallConfirmed() {
    return lastFallState;
}

bool radarIsHumanPresent() {
    return mmWave.getHuman();
}