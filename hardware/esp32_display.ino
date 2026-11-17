#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define I2C_ADDRESS 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

enum ScreenState {
  SCREEN_BOOT,
  SCREEN_READY,
  SCREEN_SCANNING,
  SCREEN_ACCEPTED,
  SCREEN_REJECTED,
  SCREEN_MANUAL_REVIEW,
  SCREEN_RED_MARK,
  SCREEN_REAL,
  SCREEN_COUNTERFEIT
};

ScreenState currentScreen = SCREEN_BOOT;
ScreenState screenBeforeAlert = SCREEN_ACCEPTED;
String commandBuffer;
bool displayReady = false;
bool cameraConnected = false;
unsigned long bootStartedAt = 0;
unsigned long lastFrameAt = 0;
unsigned long screenChangedAt = 0;
uint8_t scanProgress = 0;
bool scanForward = true;

void drawHeader(const __FlashStringHelper *label) {
  display.fillRect(0, 0, SCREEN_WIDTH, 13, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setTextSize(1);
  display.setCursor(4, 3);
  display.print(F("MEDCHECK PI"));
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(82, 3);
  display.print(label);
  display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);
}

void drawCross(int16_t x, int16_t y, uint8_t size) {
  display.fillRoundRect(x - size / 2, y - size / 6, size, size / 3, 2, SSD1306_WHITE);
  display.fillRoundRect(x - size / 6, y - size / 2, size / 3, size, 2, SSD1306_WHITE);
}

void drawCheck(int16_t x, int16_t y) {
  display.drawLine(x - 9, y, x - 2, y + 7, SSD1306_WHITE);
  display.drawLine(x - 2, y + 7, x + 12, y - 9, SSD1306_WHITE);
  display.drawLine(x - 9, y + 1, x - 2, y + 8, SSD1306_WHITE);
  display.drawLine(x - 2, y + 8, x + 12, y - 8, SSD1306_WHITE);
}

void drawWarning(int16_t x, int16_t y) {
  display.drawTriangle(x, y - 13, x - 14, y + 12, x + 14, y + 12, SSD1306_WHITE);
  display.drawLine(x, y - 5, x, y + 4, SSD1306_WHITE);
  display.drawPixel(x, y + 8, SSD1306_WHITE);
}

void drawProgressBar(uint8_t progress) {
  display.drawRoundRect(14, 51, 100, 8, 2, SSD1306_WHITE);
  uint8_t fillWidth = (uint16_t)progress * 94 / 100;
  if (fillWidth > 0) display.fillRoundRect(17, 53, fillWidth, 4, 1, SSD1306_WHITE);
}

void drawBootScreen() {
  display.clearDisplay();
  display.drawRoundRect(9, 7, 110, 50, 5, SSD1306_WHITE);
  drawCross(25, 27, 16);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(39, 18);
  display.print(F("MEDCHECK PI"));
  display.setCursor(39, 31);
  display.print(F("INITIALIZING"));
  uint8_t progress = min((unsigned long)100, (millis() - bootStartedAt) / 8);
  drawProgressBar(progress);
  display.display();
}

void drawReadyScreen() {
  display.clearDisplay();
  drawHeader(F("READY"));
  display.drawRoundRect(7, 20, 114, 30, 4, SSD1306_WHITE);
  display.drawCircle(20, 35, 7, SSD1306_WHITE);
  display.drawLine(25, 40, 30, 45, SSD1306_WHITE);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(35, 25);
  display.print(cameraConnected ? F("USB CAM CONNECTED") : F("USB CAM OFFLINE"));
  display.setCursor(35, 38);
  display.print(F("SYSTEM READY"));
  display.fillRect(0, 54, SCREEN_WIDTH, 10, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setCursor(19, 56);
  display.print(F("READY TO INSPECT"));
  display.display();
}

void drawScanningScreen() {
  display.clearDisplay();
  drawHeader(F("SCAN"));
  display.drawCircle(22, 34, 9, SSD1306_WHITE);
  display.drawLine(29, 41, 36, 48, SSD1306_WHITE);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(43, 23);
  display.print(F("SCANNING IMAGE"));
  display.drawRoundRect(42, 39, 72, 9, 2, SSD1306_WHITE);
  display.fillRect(45 + scanProgress / 2, 41, 18, 5, SSD1306_WHITE);
  if (scanForward) {
    if (scanProgress >= 45) scanForward = false;
    else scanProgress += 3;
  } else {
    if (scanProgress == 0) scanForward = true;
    else scanProgress -= 3;
  }
  display.display();
}

void drawAcceptedScreen() {
  display.clearDisplay();
  drawHeader(F("OK"));
  display.drawRoundRect(5, 20, 118, 31, 4, SSD1306_WHITE);
  drawCheck(19, 35);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(39, 24);
  display.print(F("IMAGE ACCEPTED"));
  display.setCursor(39, 36);
  display.print(F("IRON + FOLIC ACID"));
  display.fillRect(0, 54, SCREEN_WIDTH, 10, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setCursor(23, 56);
  display.print(F("READY FOR DECISION"));
  display.display();
}

void drawRejectedScreen() {
  display.clearDisplay();
  drawHeader(F("REJECT"));
  drawWarning(22, 36);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(43, 25);
  display.print(F("IMAGE REJECTED"));
  display.setCursor(43, 38);
  display.print(F("NO MEDICINE FOUND"));
  display.setCursor(38, 55);
  display.print(F("PLEASE RESCAN"));
  display.display();
}

void drawManualReviewScreen() {
  display.clearDisplay();
  drawHeader(F("REVIEW"));
  display.drawCircle(23, 35, 12, SSD1306_WHITE);
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(20, 27);
  display.print(F("?"));
  display.setTextSize(1);
  display.setCursor(44, 25);
  display.print(F("MANUAL REVIEW"));
  display.setCursor(44, 37);
  display.print(F("IMAGE UNCLEAR"));
  display.setCursor(40, 55);
  display.print(F("PLEASE RESCAN"));
  display.display();
}

void drawRedMarkScreen() {
  display.clearDisplay();
  drawHeader(F("ALERT"));
  drawWarning(20, 35);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(39, 21);
  display.print(F("VISUAL ALERT"));
  display.setCursor(39, 32);
  display.print(F("RED MARK DETECTED"));
  display.setCursor(24, 42);
  display.print(F("LOWER PRINTED AREA"));
  display.setCursor(9, 56);
  display.print(F("MANUAL REVIEW ONLY"));
  display.display();
}

void drawRealScreen() {
  display.clearDisplay();
  drawHeader(F("RESULT"));
  display.drawRoundRect(6, 19, 116, 35, 5, SSD1306_WHITE);
  drawCheck(23, 36);
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(43, 23);
  display.print(F("REAL"));
  display.setTextSize(1);
  display.setCursor(13, 43);
  display.print(F("OPERATOR SELECTED"));
  display.setCursor(16, 57);
  display.print(F("MEDCHECK PI DEMO"));
  display.display();
}

void drawCounterfeitScreen() {
  display.clearDisplay();
  drawHeader(F("RESULT"));
  display.drawRoundRect(5, 19, 118, 35, 5, SSD1306_WHITE);
  drawWarning(18, 36);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(39, 27);
  display.print(F("COUNTERFEIT"));
  display.setCursor(13, 42);
  display.print(F("OPERATOR SELECTED"));
  display.setCursor(16, 57);
  display.print(F("MEDCHECK PI DEMO"));
  display.display();
}

void setScreen(ScreenState next) {
  currentScreen = next;
  screenChangedAt = millis();
  lastFrameAt = 0;
  if (displayReady && next != SCREEN_SCANNING) {
    switch (next) {
      case SCREEN_READY: drawReadyScreen(); break;
      case SCREEN_ACCEPTED: drawAcceptedScreen(); break;
      case SCREEN_REJECTED: drawRejectedScreen(); break;
      case SCREEN_MANUAL_REVIEW: drawManualReviewScreen(); break;
      case SCREEN_RED_MARK: drawRedMarkScreen(); break;
      case SCREEN_REAL: drawRealScreen(); break;
      case SCREEN_COUNTERFEIT: drawCounterfeitScreen(); break;
      default: break;
    }
  }
}

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();
  if (command == F("STATUS:READY")) {
    setScreen(SCREEN_READY);
  } else if (command == F("STATUS:SCANNING")) {
    scanProgress = 0;
    scanForward = true;
    setScreen(SCREEN_SCANNING);
  } else if (command == F("STATUS:ACCEPTED")) {
    setScreen(SCREEN_ACCEPTED);
  } else if (command == F("STATUS:REJECTED")) {
    setScreen(SCREEN_REJECTED);
  } else if (command == F("STATUS:MANUAL_REVIEW")) {
    setScreen(SCREEN_MANUAL_REVIEW);
  } else if (command == F("STATUS:RED_MARK")) {
    screenBeforeAlert = currentScreen == SCREEN_ACCEPTED ? SCREEN_ACCEPTED : SCREEN_MANUAL_REVIEW;
    setScreen(SCREEN_RED_MARK);
  } else if (command == F("CAMERA:CONNECTED")) {
    cameraConnected = true;
    if (currentScreen == SCREEN_READY) drawReadyScreen();
  } else if (command == F("CAMERA:DISCONNECTED")) {
    cameraConnected = false;
    if (currentScreen == SCREEN_READY) drawReadyScreen();
  } else if (command == F("RESULT:REAL")) {
    setScreen(SCREEN_REAL);
  } else if (command == F("RESULT:COUNTERFEIT")) {
    setScreen(SCREEN_COUNTERFEIT);
  }
}

void setup() {
  Serial.begin(115200);
  commandBuffer.reserve(64);
  bootStartedAt = millis();
  displayReady = display.begin(SSD1306_SWITCHCAPVCC, I2C_ADDRESS);
  if (displayReady) {
    display.clearDisplay();
    drawBootScreen();
  } else {
    Serial.println(F("OLED INIT FAILED"));
  }
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = (char)Serial.read();
    if (incoming == '\n') {
      if (commandBuffer.length() > 0) handleCommand(commandBuffer);
      commandBuffer = "";
    } else if (incoming != '\r') {
      if (commandBuffer.length() < 63) {
        commandBuffer += incoming;
      } else {
        commandBuffer = "";
        Serial.println(F("ERR:COMMAND_TOO_LONG"));
      }
    }
  }

  unsigned long now = millis();
  if (currentScreen == SCREEN_BOOT) {
    if (displayReady && now - lastFrameAt >= 60) {
      drawBootScreen();
      lastFrameAt = now;
    }
    if (now - bootStartedAt >= 900) setScreen(SCREEN_READY);
  } else if (currentScreen == SCREEN_SCANNING && displayReady && now - lastFrameAt >= 90) {
    drawScanningScreen();
    lastFrameAt = now;
  } else if (currentScreen == SCREEN_RED_MARK && now - screenChangedAt >= 3500) {
    setScreen(screenBeforeAlert);
  }
}
