#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define I2C_ADDRESS 0x3C

Adafruit_SH1107 display = Adafruit_SH1107(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire);
String commandBuffer = "";

void showSplash() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.println(F("MEDCHECK - PI"));
  display.drawFastHLine(0, 12, 128, SH110X_WHITE);
  display.setCursor(4, 20);
  display.println(F("SYSTEM ONLINE"));
  display.setCursor(4, 34);
  display.println(F("WAITING FOR SCAN"));
  display.display();
}

void showStatus(const __FlashStringHelper *line1, const __FlashStringHelper *line2) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.println(F("MEDCHECK - PI"));
  display.drawFastHLine(0, 12, 128, SH110X_WHITE);
  display.setCursor(4, 18);
  display.println(line1);
  display.setCursor(4, 34);
  display.println(line2);
  display.display();
}

void showResult(String result) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.println(F("MEDCHECK - PI"));
  display.drawFastHLine(0, 12, 128, SH110X_WHITE);
  display.setCursor(4, 18);
  display.print(F("RESULT: "));
  display.println(result);
  display.setCursor(4, 34);
  display.println(F("STATUS: SELECTED"));
  display.display();
}

void handleCommand(String command) {
  command.trim();
  if (command.startsWith("RESULT:")) {
    String result = command.substring(7);
    result.trim();
    if (result == "REAL") {
      showResult("REAL");
    } else if (result == "COUNTERFEIT") {
      showResult("COUNTERFEIT");
    }
    return;
  }

  if (command.startsWith("STATUS:")) {
    String status = command.substring(7);
    status.trim();
    if (status == "SCANNING") {
      showStatus(F("SCANNING..."), F("PLEASE WAIT"));
    } else if (status == "READY") {
      showStatus(F("SYSTEM ONLINE"), F("WAITING FOR SCAN"));
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(250);

  if (!display.begin(I2C_ADDRESS, true)) {
    Serial.println(F("SH110X allocation failed"));
    for (;;) { }
  }

  display.clearDisplay();
  display.display();
  showSplash();
  Serial.println(F("ESP32 READY"));
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = Serial.read();
    if (incoming == '\n' || incoming == '\r') {
      if (commandBuffer.length() > 0) {
        handleCommand(commandBuffer);
        commandBuffer = "";
      }
    } else {
      commandBuffer += incoming;
    }
  }
}
