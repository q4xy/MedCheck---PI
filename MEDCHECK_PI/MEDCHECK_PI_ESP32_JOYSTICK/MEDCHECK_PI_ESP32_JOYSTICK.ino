#include <WiFi.h>
#include <WiFiUdp.h>
#include <math.h>

// =====================================================
// 1. WIFI CREDENTIALS
// =====================================================
const char* ssid = "Saravanan";
const char* password = "20102011";

// =====================================================
// 2. JOYSTICK PINS
// =====================================================
const int PIN_VRX = 32;
const int PIN_VRY = 33;
const int PIN_SW  = 25;

// =====================================================
// 3. ZERO-JITTER CURSOR TUNING
// =====================================================
const float RADIAL_DEADZONE = 550.0;  // Wide deadzone prevents ghost drift
const float MAX_SPEED       = 4.5;    // Smooth, controllable pointer speed
const float SMOOTHING       = 0.25;   // Strong low-pass filter against ADC noise

float centerX = 2048.0;
float centerY = 2048.0;

float smoothX = 0.0;
float smoothY = 0.0;
float accumX  = 0.0;
float accumY  = 0.0;

// =====================================================
// 4. UDP NETWORK
// =====================================================
WiFiUDP udp;
IPAddress broadcastIP;
const unsigned int UDP_PORT = 4210;

// =====================================================
// 5. TIMING & BUTTON DEBOUNCE
// =====================================================
const unsigned long SEND_INTERVAL = 25; // 40 Hz smooth update rate
unsigned long lastSendTime = 0;

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long DEBOUNCE_DELAY = 50;

// =====================================================
// 6. CALIBRATION
// =====================================================
void calibrateCenter() {
  long sumX = 0, sumY = 0;
  for (int i = 0; i < 80; i++) {
    sumX += analogRead(PIN_VRX);
    sumY += analogRead(PIN_VRY);
    delay(6);
  }
  centerX = sumX / 80.0;
  centerY = sumY / 80.0;
}

// =====================================================
// 7. WIFI CONNECTION
// =====================================================
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
  }

  IPAddress myIP = WiFi.localIP();
  broadcastIP = IPAddress(myIP[0], myIP[1], myIP[2], 255);
  udp.begin(UDP_PORT);
}

// =====================================================
// 8. SINGLE-SHOT BUTTON DEBOUNCE
// =====================================================
bool readJoystickClick() {
  bool reading = digitalRead(PIN_SW);
  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
    lastButtonReading = reading;
  }
  if (millis() - lastDebounceTime > DEBOUNCE_DELAY) {
    if (reading != stableButtonState) {
      stableButtonState = reading;
      if (stableButtonState == LOW) return true;
    }
  }
  return false;
}

// =====================================================
// 9. SEND PACKET (dx,dy,click)
// =====================================================
void sendJoystickPacket(int moveX, int dy, int click) {
  char packet[24];
  snprintf(packet, sizeof(packet), "%d,%d,%d", moveX, dy, click);
  udp.beginPacket(broadcastIP, UDP_PORT);
  udp.write((const uint8_t*)packet, strlen(packet));
  udp.endPacket();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SW, INPUT_PULLUP);
  analogReadResolution(12);

  connectWiFi();
  delay(300);
  calibrateCenter();
  Serial.println("ESP32 ZERO-JITTER JOYSTICK READY!");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    return;
  }

  unsigned long now = millis();
  if (now - lastSendTime < SEND_INTERVAL) return;
  lastSendTime = now;

  // 16-sample oversampling to eliminate ESP32 ADC spikes
  long rawX = 0, rawY = 0;
  for (int i = 0; i < 16; i++) {
    rawX += analogRead(PIN_VRX);
    rawY += analogRead(PIN_VRY);
  }
  float avgX = rawX / 16.0;
  float avgY = rawY / 16.0;

  float dxRaw = avgX - centerX;
  float dyRaw = avgY - centerY;
  float dist  = sqrtf(dxRaw * dxRaw + dyRaw * dyRaw);

  float targetVX = 0.0;
  float targetVY = 0.0;

  if (dist <= RADIAL_DEADZONE) {
    // Stick is at rest: gently track minor spring drift & zero accumulators
    if (dist < 180.0) {
      centerX = centerX * 0.98 + avgX * 0.02;
      centerY = centerY * 0.98 + avgY * 0.02;
    }
    smoothX *= 0.5;
    smoothY *= 0.5;
    if (fabsf(smoothX) < 0.05) { smoothX = 0.0; accumX = 0.0; }
    if (fabsf(smoothY) < 0.05) { smoothY = 0.0; accumY = 0.0; }
  } else {
    // Smooth scaled radial deflection outside deadzone
    float maxTravel = 2048.0 - RADIAL_DEADZONE;
    float normMag   = constrain((dist - RADIAL_DEADZONE) / maxTravel, 0.0f, 1.0f);
    float curvedMag = normMag * normMag; // Quadratic curve for fine slow aim + fast sweep

    float dirX = dxRaw / dist;
    float dirY = dyRaw / dist;

    targetVX = dirX * curvedMag * MAX_SPEED;
    targetVY = dirY * curvedMag * MAX_SPEED;

    smoothX = smoothX + SMOOTHING * (targetVX - smoothX);
    smoothY = smoothY + SMOOTHING * (targetVY - smoothY);
  }

  accumX += smoothX;
  accumY += smoothY;

  int moveX = (int)accumX;
  int moveY = (int)accumY;
  accumX -= moveX;
  accumY -= moveY;

  int click = readJoystickClick() ? 1 : 0;

  if (moveX != 0 || moveY != 0 || click == 1) {
    sendJoystickPacket(moveX, moveY, click);
  }
}