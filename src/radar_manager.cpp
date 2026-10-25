#include "radar_manager.h"
#include "config.h"
#include "mqtt_manager.h"
#include <Arduino.h>
#include "Seeed_Arduino_mmWave.h"
#include <Preferences.h>
#include "buzzer_manager.h"

// Radar
static HardwareSerial mmWaveSerial(0); // UART0 port
static SEEED_MR60FDA2 mmWave;
static Preferences prefs;

// State machine
enum RadarState {
    STATE_IDLE,             // No fall
    STATE_PENDING_FALL,     // Fall candidate - awaiting confirmation
    STATE_FALL,             // Confirmed fall
    STATE_PENDING_RECOVERY  // Fall cleared - awaiting recovery confirmation
};

// default state
static RadarState state = STATE_IDLE;

// Timestamps
static unsigned long fallDetectedAt = 0;     // when the fall candidate was detected 
static unsigned long lastRadarFrameTime = 0; // last valid frame timestamp
static unsigned long fallConfirmedAt = 0;    // when the fall was confirmed
static unsigned long recoveryStartedAt = 0;  // when recovery started
static unsigned long lastRepeatBeep = 0;     // last buzzer alarm

// Flags
static bool lastFallState = false;     // confirmed fall
static bool radarWarningSent = false;  // radar failure sent
static bool fallEscalated = false;     // escalation sent
static bool fallAlarmStarted = false;  // alarm started for this fall
static bool lastHuman = false;         // last known human presence

// Initialization
void radarInit() {
    // Open namespace fall
    if (!prefs.begin("fall", false)) { // false -> not read-only (read and write allowed)
        Serial.println("WARNING: NVS init failed, using defaults");
    }

    // Restore last fall state from NVS 
    lastFallState = prefs.getBool("lastFall", false); // false -> default value for key lastFall
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

    // Reset frame timer - give the radar time to boot before the watchdog fires
    lastRadarFrameTime = millis();
}

// Process the next radar frame and take action according to fall state
void radarUpdate() {
    // Read the next radar frame if ready
    if (!mmWave.update(100)) {
        return;
    }

    // Frame is valid - refresh health timestamp
    lastRadarFrameTime = millis();
    radarWarningSent = false;

    bool human = mmWave.getHuman();
    bool fall  = mmWave.getFall();
    lastHuman = human;  // remember last known presence
    
    switch (state) {
        case STATE_IDLE: // no fall - nobody down
            if (fall) {
                state = STATE_PENDING_FALL;
                fallDetectedAt = millis();
                Serial.println("Fall candidate detected, confirming...");
            }
            break;

        case STATE_PENDING_FALL: // fall candidate - awaiting confirmation
            if (!fall && !fallAlarmStarted) { // Signal lost before fall confirmation - cancel
                state = STATE_IDLE;
                Serial.println("Fall candidate cancelled (signal lost)");
            } else if (millis() - fallDetectedAt >= FALL_CONFIRM_MS) {
                // Local alarm first - works even if WiFi & MQTT are down
                if (!fallAlarmStarted) {
                    fallAlarmStarted = true;
                    fallConfirmedAt = millis();
                    lastRepeatBeep = millis();
                    buzzerBeep();
                    Serial.println("FALL CONFIRMED (local alarm)");
                } else {
                    if (millis() - lastRepeatBeep > BUZZER_REPEAT_MS) {
                        lastRepeatBeep = millis();
                        buzzerBeep();
                    }
                }
                // Inform Pi - if it fails, retry on the next frame
                if (publishFallEvent(true, human)) {
                    lastFallState = true;
                    fallEscalated = false;
                    prefs.putBool("lastFall", true);
                    fallAlarmStarted = false;
                    state = STATE_FALL;
                    Serial.println("Fall event delivered");
                } else {
                    Serial.println("WARNING: fall event not delivered (MQTT down?), will retry");
                }
            }
            break;

        case STATE_FALL: // confirmed fall 
            if (!fall) { // Fall cleared -> start recovery confirmation
                state = STATE_PENDING_RECOVERY;
                recoveryStartedAt = millis();
                Serial.println("Fall cleared, confirming recovery...");
            } else if (!fallEscalated && (millis() - fallConfirmedAt >= FALL_ESCALATE_MS)) {
                 // Mark as escalated only if the message was really sent
                if (publishFallEscalated()) {
                    fallEscalated = true;
                    Serial.println("FALL ESCALATED (no recovery)");
                }
            }
            break;
        
        case STATE_PENDING_RECOVERY: // fall cleared - awaiting confirmation
            if (fall) { // Fall signal returned -> cancel recovery and reset escalation timer
                fallConfirmedAt = millis();
                state = STATE_FALL;
                Serial.println("Recovery cancelled - Fall signal returned");
            } else if (millis() - recoveryStartedAt >= FALL_CLEAR_MS) {
                // Transition to IDLE if the recovery event was delivered to the Pi
                if (publishFallEvent(false, human)) {
                    lastFallState = false;
                    fallEscalated = false;
                    prefs.putBool("lastFall", false);
                    state = STATE_IDLE;
                    Serial.println("RECOVERY CONFIRMED");
                }
            }
            break;
    }
}

// Radar watchdog
void radarCheckTimeout() {
    if (!radarWarningSent && (millis() - lastRadarFrameTime > RADAR_TIMEOUT_MS)) {
        // Retry on the next loop iteration if publish fails
        if (publishRadarFailure()) {
            Serial.println("WARNING: no radar frames received");
            radarWarningSent = true;
        }
    }
}

// Radar getters
bool radarIsFallConfirmed() { // LED turns on at local confirmation - not only after delivery
    return lastFallState || fallAlarmStarted;
}

bool radarIsHumanPresent() {
    return lastHuman;
}