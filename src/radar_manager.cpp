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
static unsigned long lastRepeatBeep = 0;

// Flags
static bool lastFallState = false;  // confirmed fall
static bool radarWarningSent = false;  // radar-failure already sent
static bool fallEscalated = false;  // escalation already sent
static bool fallAlarmStarted = false;  // local alarm already started for this fall
static bool lastHuman = false;  // last known human presence

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
    lastRadarFrame = millis();
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
                // Local alarm first - works even if WiFi/MQTT is down
                if (!fallAlarmStarted) {
                    fallAlarmStarted = true;
                    fallConfirmedAt = millis();
                    lastRepeatBeep = millis();
                    buzzerBeep(BUZZER_FALL_DURATION_MS);
                    Serial.println("FALL CONFIRMED (local alarm)");
                } else {
                    if (millis() - lastRepeatBeep > 30000) {
                        lastRepeatBeep = millis();
                        buzzerBeep(BUZZER_FALL_DURATION_MS);
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
            if (fall) { // Fall signal returned: cancel recovery - reset escalation timer
                fallConfirmedAt = millis();
                state = STATE_FALL;
                Serial.println("Recovery cancelled (fall signal returned)");
            } else if (millis() - recoveryStartedAt >= FALL_CLEAR_MS) {
                // Recovery counts only after the Pi has been told
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
    if (!radarWarningSent && (millis() - lastRadarFrame > RADAR_TIMEOUT_MS)) {
        // Retry every loop until the failure message is delivered
        if (publishRadarFailure()) {
            Serial.println("WARNING: no radar frames received");
            radarWarningSent = true;
        }
    }
}

void radarResetTimeout() { 
    lastRadarFrame = millis(); 
}

// Radar getters
bool radarIsFallConfirmed() { // LED turns on at local confirmation - not only after delivery
    return lastFallState || fallAlarmStarted;
}

bool radarIsHumanPresent() {
    return lastHuman;
}