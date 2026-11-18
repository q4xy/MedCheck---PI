#include <WiFiS3.h>
#include <WiFiUdp.h>
#include <Arduino_GFX_Library.h>

// =====================================================
// 1. WIFI & STATIC IP SETTINGS
// =====================================================

char ssid[] = "Saravanan";
char pass[] = "20102011";

// Fixed Static IP for Mobile Hotspot Subnet (192.168.43.x)
IPAddress staticIP(192, 168, 43, 100);
IPAddress gateway(192, 168, 43, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress dns(8, 8, 8, 8);

// =====================================================
// 2. TFT DISPLAY - 2.4 INCH ILI9341, 320x240
// =====================================================

Arduino_DataBus *bus = new Arduino_UNOPAR8();
Arduino_GFX *gfx = new Arduino_ILI9341(
  bus,
  A4,
  1
);

// =====================================================
// 3. NETWORK
// =====================================================

WiFiServer server(80);
WiFiUDP udp;

const unsigned int UDP_PORT = 4210;
char packetBuffer[64];

// =====================================================
// 4. SCREEN & PLACEMENT STATES
// =====================================================

enum ScreenState {
  SCREEN_HOME,
  SCREEN_PLACEMENT,
  SCREEN_SCANNING,
  SCREEN_RESULT,
  SCREEN_HISTORY,
  SCREEN_EXPORT
};

ScreenState currentScreen = SCREEN_HOME;

enum AlignmentState {
  ALIGN_NONE,
  ALIGN_ADJUST,
  ALIGN_CONFIRMED
};

AlignmentState currentAlignState = ALIGN_NONE;
unsigned long alignConfirmedAtMs = 0;
bool alignTransitionStarted = false;

// =====================================================
// 5. MEDICINE INSPECTION & REALISTIC PROGRESS STATE
// =====================================================

String queuedVerdict = "";
bool verdictReceived = false;
bool fastCompletionMode = false;
bool resultLogged = false;

int scanPercent = 0;
int prevDrawnPercent = -1;
int prevBarFillWidth = 0;

unsigned long lastSlowTickMs = 0;
unsigned long lastFastTickMs = 0;
unsigned long lastStageChangeMs = 0;
unsigned long lastPulseFrameMs = 0;

int stageIndex = 0;
int pulseStep = 0;

const unsigned long SLOW_PROGRESS_INTERVAL_MS = 650;  // Realistic slow climb
const unsigned long FAST_PROGRESS_INTERVAL_MS = 22;   // ~1.2s rapid completion to 100%
const unsigned long STAGE_ROTATE_INTERVAL_MS  = 1600; // Smooth stage transitions
const unsigned long ALIGN_HOLD_BEFORE_SCAN_MS = 900;  // Brief visual confirmation of MEDICINE ALIGNED

const char* INSPECTION_STAGES[7] = {
  "IDENTIFYING MEDICINE",
  "READING MEDICINE DETAILS",
  "IDENTIFYING EXPIRY CODE",
  "INSPECTING EXPIRY DATE",
  "CHECKING PRINT QUALITY",
  "ANALYZING MEDICINE",
  "PROCESSING INSPECTION"
};

// =====================================================
// 6. USB SERIAL COMMAND BUFFER (PYTHON CAMERA LINK)
// =====================================================

String serialLineBuffer = "";

// =====================================================
// 7. HISTORY
// =====================================================

struct ScanRecord {
  int id;
  String sampleId;
  String verdict;
};

ScanRecord historyLog[15];

int historyCount = 0;
int totalScans = 0;

// =====================================================
// 8. JOYSTICK CURSOR & DEBOUNCED CLICK STATE
// =====================================================

int curX = 160;
int curY = 92;

int prevCurX = 160;
int prevCurY = 92;

bool prevClick = false;
unsigned long lastClickHandledMs = 0;
const unsigned long CLICK_LOCKOUT_MS = 280;

// =====================================================
// 9. HIGH-CONTRAST RGB565 PALETTE (TUNED FOR RED ENCLOSURE)
// =====================================================

#define MED_BG            0x0000  // Pure Pitch Black
#define MED_CHARCOAL      0x10A2  // Deep Charcoal Surface
#define MED_PANEL         0x18E3  // Elevated Slate Panel

// Primary UI Accents (High contrast against Red Enclosure)
#define MED_WHITE         0xFFFF
#define MED_GREY          0xBDF7  // Bright Readable Silver-Grey
#define MED_DIM           0x5AEB  // Crisp Neutral Divider

// Button 1: SCAN (Electric Cyan / Blue)
#define MED_CYAN          0x07FF
#define MED_BLUE_FILL     0x0192
#define MED_BLUE_HI       0x035F

// Button 2: HISTORY (Vivid Purple / Violet)
#define MED_PURPLE        0xC99F
#define MED_PURPLE_FILL   0x3010
#define MED_PURPLE_HI     0x601A

// Button 3: EXPORT CSV (Bright Amber / Orange)
#define MED_ORANGE        0xFD20
#define MED_YELLOW        0xFFE0
#define MED_ORANGE_FILL   0x4180
#define MED_ORANGE_HI     0x72A0

// Result Status Colors
#define MED_GREEN         0x07E0
#define MED_GREEN_DARK    0x0260
#define MED_RED           0xF800
#define MED_RED_DARK      0x3000

// =====================================================
// 10. HOME BUTTON GEOMETRY & DECOUPLED SELECTION STATE
// =====================================================

const int BTN_X      = 18;
const int BTN_W      = 284;
const int BTN_H      = 38;
const int BTN_Y[3]   = { 72, 120, 168 };

const int BACK_X     = 90;
const int BACK_Y     = 190;
const int BACK_W     = 140;
const int BACK_H     = 38;

int selectedBtn      = -1;
int prevSelectedBtn  = -1;
bool backHovered     = false;
bool prevBackHovered = false;

// =====================================================
// 11. MOBILE DASHBOARD (PURE BLACK, WHITE TEXT ONLY)
// =====================================================

const char PHONE_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport"
content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>.</title>
<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  -webkit-tap-highlight-color: transparent;
}
html, body {
  width: 100%;
  height: 100%;
  background: #000000;
  overflow: hidden;
  font-family: Arial, sans-serif;
}
body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
button {
  flex: 1;
  width: 100%;
  background: #000000;
  border: none;
  outline: none;
  box-shadow: none;
  color: #ffffff;
  font-family: Arial, sans-serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
}
button:active {
  opacity: 0.35;
}
</style>
</head>
<body>
  <button onclick="send('REAL')">REAL</button>
  <button onclick="send('COUNTERFEIT')">COUNTERFEIT</button>
<script>
function send(value) {
  fetch('/set?v=' + value, {
    method: 'GET',
    cache: 'no-store'
  }).catch(() => {});
}
</script>
</body>
</html>
)rawliteral";

// =====================================================
// 12. EXACT TEXT WIDTH & BOUNDARY-SAFE HELPERS (320x240)
// =====================================================

void drawCenteredText(
  const char* text,
  int y,
  uint8_t size,
  uint16_t color
) {
  int16_t x1, y1;
  uint16_t w, h;

  gfx->setTextSize(size);
  gfx->getTextBounds(text, 0, y, &x1, &y1, &w, &h);

  int x = (320 - (int)w) / 2;
  if (x < 4) x = 4;

  gfx->setTextColor(color);
  gfx->setCursor(x, y);
  gfx->print(text);
}

void drawCenteredInBox(
  const char* text,
  int boxX,
  int boxY,
  int boxW,
  int boxH,
  uint8_t size,
  uint16_t color
) {
  int16_t x1, y1;
  uint16_t w, h;

  gfx->setTextSize(size);
  gfx->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);

  int tx = boxX + (boxW - (int)w) / 2 - x1;
  int ty = boxY + (boxH - (int)h) / 2 - y1;

  if (tx < boxX + 2) tx = boxX + 2;

  gfx->setTextColor(color);
  gfx->setCursor(tx, ty);
  gfx->print(text);
}

// =====================================================
// 13. HEADER & BACK BUTTON
// =====================================================

void drawHeader(const char* title, uint16_t accentColor) {
  gfx->fillRect(0, 0, 320, 42, MED_CHARCOAL);
  gfx->drawFastHLine(0, 42, 320, accentColor);
  gfx->drawFastHLine(0, 43, 320, accentColor);
  drawCenteredInBox(title, 0, 0, 320, 42, 2, MED_WHITE);
}

void drawBackButton(bool highlighted) {
  uint16_t fillCol   = highlighted ? MED_BLUE_HI : MED_PANEL;
  uint16_t borderCol = highlighted ? MED_WHITE   : MED_CYAN;

  gfx->fillRoundRect(BACK_X, BACK_Y, BACK_W, BACK_H, 10, fillCol);
  gfx->drawRoundRect(BACK_X,     BACK_Y,     BACK_W,     BACK_H,     10, borderCol);
  gfx->drawRoundRect(BACK_X + 1, BACK_Y + 1, BACK_W - 2, BACK_H - 2, 9,  borderCol);
  gfx->drawRoundRect(BACK_X + 2, BACK_Y + 2, BACK_W - 4, BACK_H - 4, 8,  borderCol);

  drawCenteredInBox("< BACK", BACK_X, BACK_Y, BACK_W, BACK_H, 2, MED_WHITE);
}

// =====================================================
// 14. SINGLE HOME BUTTON RENDERER (ZERO JITTER, ALL 4 BORDERS INTACT)
// =====================================================

void drawSingleHomeButton(int index, bool highlighted) {
  if (index < 0 || index > 2) return;

  const char* labels[3] = {
    "SCAN",
    "HISTORY",
    "EXPORT CSV"
  };

  uint16_t normalFill[3] = { MED_BLUE_FILL, MED_PURPLE_FILL, MED_ORANGE_FILL };
  uint16_t activeFill[3] = { MED_BLUE_HI,   MED_PURPLE_HI,   MED_ORANGE_HI   };
  uint16_t accentCol[3]  = { MED_CYAN,      MED_PURPLE,      MED_ORANGE      };

  int bx = BTN_X;
  int by = BTN_Y[index];
  int bw = BTN_W;
  int bh = BTN_H;

  uint16_t fill   = highlighted ? activeFill[index] : normalFill[index];
  uint16_t border = highlighted ? MED_WHITE         : accentCol[index];
  uint16_t iconC  = highlighted ? MED_YELLOW        : accentCol[index];

  gfx->fillRoundRect(bx, by, bw, bh, 10, fill);

  gfx->drawRoundRect(bx,     by,     bw,     bh,     10, border);
  gfx->drawRoundRect(bx + 1, by + 1, bw - 2, bh - 2, 9,  border);
  gfx->drawRoundRect(bx + 2, by + 2, bw - 4, bh - 4, 8,  border);

  int ix = bx + 28;
  int iy = by + bh / 2;

  if (index == 0) {
    gfx->drawCircle(ix, iy, 9, iconC);
    gfx->drawCircle(ix, iy, 8, iconC);
    gfx->drawFastHLine(ix - 12, iy, 24, iconC);
    gfx->drawFastVLine(ix, iy - 12, 24, iconC);
  } else if (index == 1) {
    gfx->fillRoundRect(ix - 10, iy - 8, 20, 3, 1, iconC);
    gfx->fillRoundRect(ix - 10, iy - 1, 16, 3, 1, iconC);
    gfx->fillRoundRect(ix - 10, iy + 6, 20, 3, 1, iconC);
  } else {
    gfx->fillRect(ix - 1, iy - 9, 3, 13, iconC);
    gfx->drawLine(ix - 6, iy - 1, ix,     iy + 5, iconC);
    gfx->drawLine(ix - 5, iy - 1, ix,     iy + 4, iconC);
    gfx->drawLine(ix + 6, iy - 1, ix + 1, iy + 5, iconC);
    gfx->drawLine(ix + 5, iy - 1, ix + 1, iy + 4, iconC);
    gfx->fillRect(ix - 10, iy + 8, 21, 3, iconC);
  }

  if (highlighted) {
    int rx = bx + bw - 22;
    gfx->fillTriangle(rx - 5, iy - 6, rx - 5, iy + 6, rx + 4, iy, MED_YELLOW);
  }

  drawCenteredInBox(labels[index], bx, by, bw, bh, 2, MED_WHITE);
}

int getHoveredHomeButton(int x, int y) {
  for (int i = 0; i < 3; i++) {
    if (x >= BTN_X && x <= BTN_X + BTN_W &&
        y >= BTN_Y[i] && y <= BTN_Y[i] + BTN_H) {
      return i;
    }
  }
  return -1;
}

bool isBackHovered(int x, int y) {
  return (x >= BACK_X && x <= BACK_X + BACK_W &&
          y >= BACK_Y && y <= BACK_Y + BACK_H);
}

// =====================================================
// 15. HOME SCREEN
// =====================================================

void drawHomeScreen() {
  currentScreen = SCREEN_HOME;

  selectedBtn = getHoveredHomeButton(curX, curY);
  prevSelectedBtn = selectedBtn;

  gfx->fillScreen(MED_BG);

  gfx->fillRect(0, 0, 320, 58, MED_CHARCOAL);
  gfx->drawFastHLine(0, 58, 320, MED_CYAN);
  gfx->drawFastHLine(0, 59, 320, MED_CYAN);

  drawCenteredText("MEDCHECK PI", 10, 3, MED_WHITE);
  drawCenteredText("SMART MEDICINE INSPECTION", 40, 1, MED_CYAN);

  for (int i = 0; i < 3; i++) {
    drawSingleHomeButton(i, (i == selectedBtn));
  }

  gfx->fillRect(0, 216, 320, 24, MED_CHARCOAL);
  gfx->drawFastHLine(0, 216, 320, MED_DIM);

  gfx->fillCircle(14, 228, 4, MED_GREEN);
  gfx->setTextSize(1);
  gfx->setTextColor(MED_WHITE);
  gfx->setCursor(24, 224);
  gfx->print("READY");

  gfx->setTextColor(MED_YELLOW);
  gfx->setCursor(156, 224);
  gfx->print("IP: ");
  gfx->print(WiFi.localIP());
}

// =====================================================
// 16. STEP 1 OF SCAN: MEDICINE PLACEMENT GUIDE SCREEN
// =====================================================

void updatePlacementGuideVisuals(AlignmentState state) {
  const int fx = 34;
  const int fy = 52;
  const int fw = 252;
  const int fh = 110;

  uint16_t frameCol  = MED_CYAN;
  uint16_t cornerCol = MED_YELLOW;
  uint16_t fillCol   = MED_CHARCOAL;
  const char* mainTitle = "PLACE YOUR MEDICINE";
  const char* subLine1  = "Show BACK SIDE to camera";
  const char* subLine2  = "ALIGN MEDICINE INSIDE THE FRAME";

  if (state == ALIGN_ADJUST) {
    frameCol  = MED_ORANGE;
    cornerCol = MED_YELLOW;
    fillCol   = MED_CHARCOAL;
    mainTitle = "ADJUST MEDICINE POSITION";
    subLine1  = "Center BACK SIDE in view";
    subLine2  = "ALIGN MEDICINE INSIDE THE FRAME";
  } else if (state == ALIGN_CONFIRMED) {
    frameCol  = MED_GREEN;
    cornerCol = MED_GREEN;
    fillCol   = MED_GREEN_DARK;
    mainTitle = "MEDICINE ALIGNED";
    subLine1  = "Position verified & stable";
    subLine2  = "STARTING INSPECTION...";
  }

  gfx->fillRoundRect(fx, fy, fw, fh, 10, fillCol);
  gfx->drawRoundRect(fx,     fy,     fw,     fh,     10, frameCol);
  gfx->drawRoundRect(fx + 1, fy + 1, fw - 2, fh - 2, 9,  frameCol);

  int bx1 = fx + 10;
  int by1 = fy + 10;
  int bx2 = fx + fw - 11;
  int by2 = fy + fh - 11;
  int blen = 16;

  gfx->fillRect(bx1, by1, blen, 3, cornerCol);
  gfx->fillRect(bx1, by1, 3, blen, cornerCol);
  gfx->fillRect(bx2 - blen + 1, by1, blen, 3, cornerCol);
  gfx->fillRect(bx2 - 2, by1, 3, blen, cornerCol);
  gfx->fillRect(bx1, by2 - 2, blen, 3, cornerCol);
  gfx->fillRect(bx1, by2 - blen + 1, 3, blen, cornerCol);
  gfx->fillRect(bx2 - blen + 1, by2 - 2, blen, 3, cornerCol);
  gfx->fillRect(bx2 - 2, by2 - blen + 1, 3, blen, cornerCol);

  if (state == ALIGN_ADJUST) {
    drawCenteredInBox("ADJUST MEDICINE", fx + 12, fy + 22, fw - 24, 22, 2, MED_ORANGE);
    drawCenteredInBox("POSITION",        fx + 12, fy + 44, fw - 24, 22, 2, MED_YELLOW);
    drawCenteredInBox(subLine1,          fx + 12, fy + 76, fw - 24, 16, 1, MED_WHITE);
  } else {
    uint16_t titleCol = (state == ALIGN_CONFIRMED) ? MED_GREEN : MED_WHITE;
    drawCenteredInBox(mainTitle, fx + 12, fy + 28, fw - 24, 24, 2, titleCol);
    drawCenteredInBox(subLine1,  fx + 12, fy + 66, fw - 24, 18, 1, MED_GREY);
  }

  gfx->fillRoundRect(20, 172, 280, 34, 8, MED_PANEL);
  gfx->drawRoundRect(20, 172, 280, 34, 8, frameCol);
  drawCenteredInBox(subLine2, 20, 172, 280, 34, 1, (state == ALIGN_CONFIRMED) ? MED_GREEN : MED_CYAN);
}

void startPlacementScreen() {
  currentScreen = SCREEN_PLACEMENT;
  currentAlignState = ALIGN_NONE;
  alignConfirmedAtMs = 0;
  alignTransitionStarted = false;

  queuedVerdict = "";
  verdictReceived = false;
  fastCompletionMode = false;
  resultLogged = false;

  gfx->fillScreen(MED_BG);
  drawHeader("MEDICINE PLACEMENT", MED_CYAN);

  updatePlacementGuideVisuals(ALIGN_NONE);

  gfx->fillRect(0, 216, 320, 24, MED_CHARCOAL);
  gfx->drawFastHLine(0, 216, 320, MED_DIM);

  gfx->fillCircle(14, 228, 4, MED_CYAN);
  gfx->setTextSize(1);
  gfx->setTextColor(MED_WHITE);
  gfx->setCursor(24, 224);
  gfx->print("CAM 1: OPTICAL GUIDE");

  gfx->setTextColor(MED_YELLOW);
  gfx->setCursor(214, 224);
  gfx->print("CLICK=CANCEL");
}

// =====================================================
// 17. STEP 2 OF SCAN: MEDICINE IDENTIFICATION & INSPECTION SCREEN
// =====================================================

void drawInspectionCapsuleGraphic(int step) {
  int cx = 160;
  int cy = 84;

  gfx->drawCircle(cx, cy, 22, MED_CYAN);
  gfx->drawCircle(cx, cy, 21, MED_BLUE_HI);

  gfx->fillRoundRect(cx - 14, cy - 6, 14, 12, 5, MED_CYAN);
  gfx->fillRoundRect(cx,      cy - 6, 14, 12, 5, MED_PURPLE);
  gfx->drawRoundRect(cx - 14, cy - 6, 28, 12, 5, MED_WHITE);
  gfx->drawFastVLine(cx, cy - 5, 10, MED_WHITE);

  const int dx[4] = {  0,  27,   0, -27 };
  const int dy[4] = { -27,  0,  27,   0 };

  for (int i = 0; i < 4; i++) {
    uint16_t nodeCol = (i == (step % 4)) ? MED_YELLOW : MED_DIM;
    gfx->fillCircle(cx + dx[i], cy + dy[i], 3, nodeCol);
  }
}

void drawInspectionStageBanner(int idx) {
  gfx->fillRoundRect(16, 120, 288, 34, 8, MED_PANEL);
  gfx->drawRoundRect(16, 120, 288, 34, 8, MED_YELLOW);

  int16_t x1, y1;
  uint16_t w, h;
  gfx->setTextSize(2);
  gfx->getTextBounds(INSPECTION_STAGES[idx], 0, 0, &x1, &y1, &w, &h);
  uint8_t chosenSize = (w <= 274) ? 2 : 1;

  drawCenteredInBox(INSPECTION_STAGES[idx], 16, 120, 288, 34, chosenSize, MED_WHITE);
}

void renderProgressBarAndPercent(int pct, bool fastMode) {
  pct = constrain(pct, 0, 100);

  int maxFillW = 256;
  int fillW = (pct * maxFillW) / 100;

  if (fillW > prevBarFillWidth) {
    uint16_t fillCol = fastMode ? MED_GREEN : MED_CYAN;
    gfx->fillRect(32 + prevBarFillWidth, 166, fillW - prevBarFillWidth, 18, fillCol);
    prevBarFillWidth = fillW;
  }

  if (pct != prevDrawnPercent) {
    char pctText[12];
    snprintf(pctText, sizeof(pctText), "%d%%", pct);

    gfx->fillRect(105, 192, 110, 20, MED_BG);
    uint16_t txtCol = fastMode ? MED_GREEN : MED_YELLOW;
    drawCenteredText(pctText, 194, 2, txtCol);
    prevDrawnPercent = pct;
  }
}

void startScanScreen() {
  currentScreen = SCREEN_SCANNING;

  queuedVerdict = "";
  verdictReceived = false;
  fastCompletionMode = false;
  resultLogged = false;

  scanPercent = 0;
  prevDrawnPercent = -1;
  prevBarFillWidth = 0;

  stageIndex = 0;
  pulseStep = 0;

  unsigned long now = millis();
  lastSlowTickMs = now;
  lastFastTickMs = now;
  lastStageChangeMs = now;
  lastPulseFrameMs = now;

  gfx->fillScreen(MED_BG);
  drawHeader("MEDICINE INSPECTION", MED_CYAN);

  drawInspectionCapsuleGraphic(0);
  drawInspectionStageBanner(0);

  gfx->drawRoundRect(28, 162, 264, 26, 8, MED_CYAN);
  gfx->drawRoundRect(29, 163, 262, 24, 7, MED_CYAN);
  gfx->fillRect(32, 166, 256, 18, MED_CHARCOAL);

  renderProgressBarAndPercent(0, false);

  gfx->fillRect(0, 218, 320, 22, MED_CHARCOAL);
  gfx->drawFastHLine(0, 218, 320, MED_DIM);
  drawCenteredText("OPTICAL ANALYSIS IN PROGRESS", 224, 1, MED_GREY);
}

// =====================================================
// 18. SAVE INSPECTION RESULT
// =====================================================

void saveResult() {
  if (resultLogged) return;
  if (!verdictReceived) return;

  totalScans++;
  String sCode = "SMP-" + String(1000 + totalScans);

  if (historyCount < 15) {
    historyLog[historyCount].id = totalScans;
    historyLog[historyCount].sampleId = sCode;
    historyLog[historyCount].verdict = queuedVerdict;
    historyCount++;
  } else {
    for (int i = 0; i < 14; i++) {
      historyLog[i] = historyLog[i + 1];
    }
    historyLog[14].id = totalScans;
    historyLog[14].sampleId = sCode;
    historyLog[14].verdict = queuedVerdict;
  }

  resultLogged = true;
}

// =====================================================
// 19. RESULT SCREEN (REAL / COUNTERFEIT ONLY)
// =====================================================

void drawCheckmarkIcon(int cx, int cy, uint16_t color) {
  gfx->drawCircle(cx, cy, 18, color);
  gfx->drawCircle(cx, cy, 17, color);
  for (int t = -1; t <= 1; t++) {
    gfx->drawLine(cx - 9, cy + t,     cx - 2, cy + 7 + t, color);
    gfx->drawLine(cx - 2, cy + 7 + t, cx + 10, cy - 7 + t, color);
  }
}

void drawWarningIcon(int cx, int cy, uint16_t color) {
  gfx->drawTriangle(cx, cy - 16, cx - 17, cy + 14, cx + 17, cy + 14, color);
  gfx->drawTriangle(cx, cy - 14, cx - 15, cy + 13, cx + 15, cy + 13, color);
  gfx->fillRect(cx - 1, cy - 6, 3, 11, color);
  gfx->fillRect(cx - 1, cy + 8, 3, 3, color);
}

void showResultScreen() {
  if (!verdictReceived) return;

  saveResult();
  currentScreen = SCREEN_RESULT;

  bool isFake = (queuedVerdict == "COUNTERFEIT");
  uint16_t accent = isFake ? MED_RED : MED_GREEN;
  uint16_t panel  = isFake ? MED_RED_DARK : MED_GREEN_DARK;

  gfx->fillScreen(MED_BG);
  drawHeader("INSPECTION RESULT", accent);

  if (!isFake) {
    gfx->fillRoundRect(16, 52, 288, 92, 12, panel);
    gfx->drawRoundRect(16, 52, 288, 92, 12, MED_GREEN);
    gfx->drawRoundRect(17, 53, 286, 90, 11, MED_GREEN);
    gfx->drawRoundRect(18, 54, 284, 88, 10, MED_GREEN);

    drawCheckmarkIcon(64, 98, MED_GREEN);

    gfx->setTextSize(3);
    gfx->setTextColor(MED_GREEN);
    gfx->setCursor(108, 86);
    gfx->print("REAL");

    gfx->fillRoundRect(20, 152, 280, 28, 8, MED_PANEL);
    gfx->drawRoundRect(20, 152, 280, 28, 8, MED_DIM);

    gfx->setTextSize(1);
    gfx->setTextColor(MED_GREY);
    gfx->setCursor(34, 162);
    gfx->print("SCAN #");
    gfx->setTextColor(MED_WHITE);
    gfx->print(totalScans);

    gfx->setTextColor(MED_GREY);
    gfx->setCursor(135, 162);
    gfx->print("ID: ");
    gfx->setTextColor(MED_CYAN);
    gfx->print("SMP-");
    gfx->print(1000 + totalScans);
  } else {
    // COUNTERFEIT RESULT SCREEN: Displays ONLY "COUNTERFEIT" with warning styling
    gfx->fillRoundRect(16, 52, 288, 92, 12, panel);
    gfx->drawRoundRect(16, 52, 288, 92, 12, MED_RED);
    gfx->drawRoundRect(17, 53, 286, 90, 11, MED_RED);
    gfx->drawRoundRect(18, 54, 284, 88, 10, MED_RED);

    drawWarningIcon(50, 98, MED_ORANGE);

    gfx->setTextSize(3);
    gfx->setTextColor(MED_RED);
    gfx->setCursor(82, 86);
    gfx->print("COUNTERFEIT");

    gfx->fillRoundRect(20, 152, 280, 28, 8, MED_PANEL);
    gfx->drawRoundRect(20, 152, 280, 28, 8, MED_DIM);

    gfx->setTextSize(1);
    gfx->setTextColor(MED_GREY);
    gfx->setCursor(34, 162);
    gfx->print("SCAN #");
    gfx->setTextColor(MED_WHITE);
    gfx->print(totalScans);

    gfx->setTextColor(MED_GREY);
    gfx->setCursor(135, 162);
    gfx->print("ID: ");
    gfx->setTextColor(MED_CYAN);
    gfx->print("SMP-");
    gfx->print(1000 + totalScans);
  }

  backHovered = isBackHovered(curX, curY);
  prevBackHovered = backHovered;
  drawBackButton(backHovered);
}

// =====================================================
// 20. HISTORY & EXPORT SCREENS (MODULAR ROW REDRAW FOR CURSOR SAFETY)
// =====================================================

void drawHistoryHeaderColumns() {
  gfx->setTextSize(1);
  gfx->setTextColor(MED_PURPLE);
  gfx->setCursor(24, 52);
  gfx->print("NO.");
  gfx->setCursor(74, 52);
  gfx->print("SAMPLE ID");
  gfx->setCursor(184, 52);
  gfx->print("RESULT");
  gfx->drawFastHLine(18, 64, 284, MED_PURPLE);
}

void drawHistoryRow(int slotIndex, int recordIndex) {
  int y = 70 + slotIndex * 23;
  bool isFake = (historyLog[recordIndex].verdict == "COUNTERFEIT");

  gfx->fillRoundRect(18, y - 3, 284, 20, 6, MED_PANEL);
  gfx->drawRoundRect(18, y - 3, 284, 20, 6, MED_DIM);

  gfx->setTextSize(1);
  gfx->setTextColor(MED_WHITE);
  gfx->setCursor(26, y + 3);
  gfx->print("#");
  gfx->print(historyLog[recordIndex].id);

  gfx->setTextColor(MED_CYAN);
  gfx->setCursor(74, y + 3);
  gfx->print(historyLog[recordIndex].sampleId);

  gfx->setTextColor(isFake ? MED_RED : MED_GREEN);
  gfx->setCursor(184, y + 3);
  gfx->print(historyLog[recordIndex].verdict);
}

void drawHistoryEmptyCard() {
  gfx->fillRoundRect(24, 78, 272, 84, 12, MED_PANEL);
  gfx->drawRoundRect(24, 78, 272, 84, 12, MED_PURPLE);
  drawCenteredInBox("NO RECORDS YET", 24, 78, 272, 84, 2, MED_WHITE);
}

void showHistoryScreen() {
  currentScreen = SCREEN_HISTORY;
  gfx->fillScreen(MED_BG);
  drawHeader("INSPECTION HISTORY", MED_PURPLE);

  if (historyCount == 0) {
    drawHistoryEmptyCard();
  } else {
    drawHistoryHeaderColumns();

    int start = max(0, historyCount - 5);
    int slot = 0;

    for (int i = historyCount - 1; i >= start; i--) {
      drawHistoryRow(slot, i);
      slot++;
    }
  }

  backHovered = isBackHovered(curX, curY);
  prevBackHovered = backHovered;
  drawBackButton(backHovered);
}

void showExportScreen() {
  currentScreen = SCREEN_EXPORT;
  gfx->fillScreen(MED_BG);
  drawHeader("EXPORT CSV", MED_ORANGE);

  gfx->fillRoundRect(18, 54, 284, 124, 12, MED_PANEL);
  gfx->drawRoundRect(18, 54, 284, 124, 12, MED_ORANGE);
  gfx->drawRoundRect(19, 55, 282, 122, 11, MED_ORANGE);

  char countBuffer[36];
  snprintf(countBuffer, sizeof(countBuffer), "RECORDED SCANS: %d", historyCount);
  drawCenteredText(countBuffer, 68, 2, MED_WHITE);

  drawCenteredText("OPEN ON MOBILE BROWSER:", 100, 1, MED_YELLOW);

  String url = "http://" + WiFi.localIP().toString() + "/export";
  gfx->fillRoundRect(28, 116, 264, 26, 8, MED_CHARCOAL);
  gfx->drawRoundRect(28, 116, 264, 26, 8, MED_CYAN);
  drawCenteredInBox(url.c_str(), 28, 116, 264, 26, 1, MED_CYAN);

  drawCenteredText("FILE: medcheck_history.csv", 152, 1, MED_GREY);

  backHovered = isBackHovered(curX, curY);
  prevBackHovered = backHovered;
  drawBackButton(backHovered);
}

// =====================================================
// 21. FLICKER-FREE CURSOR & BORDER/TEXT-SAFE REDRAW ENGINE
// =====================================================

uint16_t getScreenBaseColorAt(int x, int y) {
  if (currentScreen == SCREEN_HOME) {
    if (y <= 57) return MED_CHARCOAL;
    if (y >= 217) return MED_CHARCOAL;
  } else {
    if (y <= 41) return MED_CHARCOAL;
  }
  return MED_BG;
}

void drawPointer(int x, int y) {
  gfx->fillTriangle(x, y, x, y + 10, x + 7, y + 7, MED_WHITE);
  gfx->drawLine(x, y, x, y + 10, MED_BG);
  gfx->drawLine(x, y, x + 7, y + 7, MED_BG);
  gfx->drawLine(x, y + 10, x + 7, y + 7, MED_BG);
}

void erasePointerRegion(int x, int y) {
  for (int dy = 0; dy <= 10; dy++) {
    for (int dx = 0; dx <= 7; dx++) {
      int px = x + dx;
      int py = y + dy;
      if (px >= 0 && px < 320 && py >= 0 && py < 240) {
        gfx->drawPixel(px, py, getScreenBaseColorAt(px, py));
      }
    }
  }
}

bool rectsOverlap(int ax, int ay, int aw, int ah, int bx, int by, int bw, int bh) {
  return (ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by);
}

void updateCursor(int newX, int newY) {
  if (newX == prevCurX && newY == prevCurY) return;

  if (currentScreen == SCREEN_SCANNING || currentScreen == SCREEN_PLACEMENT) {
    prevCurX = newX;
    prevCurY = newY;
    return;
  }

  erasePointerRegion(prevCurX, prevCurY);

  // Restore top header line if cursor touched y=42..43 on sub-screens
  if (currentScreen != SCREEN_HOME && prevCurY <= 44 && prevCurY + 11 >= 42) {
    uint16_t hdrAcc = MED_CYAN;
    if (currentScreen == SCREEN_HISTORY) hdrAcc = MED_PURPLE;
    else if (currentScreen == SCREEN_EXPORT) hdrAcc = MED_ORANGE;
    else if (currentScreen == SCREEN_RESULT) {
      hdrAcc = (queuedVerdict == "COUNTERFEIT") ? MED_RED : MED_GREEN;
    }
    gfx->drawFastHLine(0, 42, 320, hdrAcc);
    gfx->drawFastHLine(0, 43, 320, hdrAcc);
  }

  if (currentScreen == SCREEN_HOME) {
    selectedBtn = getHoveredHomeButton(newX, newY);

    for (int i = 0; i < 3; i++) {
      bool stateChanged = (selectedBtn != prevSelectedBtn) &&
                          (i == selectedBtn || i == prevSelectedBtn);
      bool touchedOld   = rectsOverlap(prevCurX, prevCurY, 8, 11,
                                       BTN_X - 1, BTN_Y[i] - 1, BTN_W + 2, BTN_H + 2);
      bool touchedNew   = rectsOverlap(newX, newY, 8, 11,
                                       BTN_X - 1, BTN_Y[i] - 1, BTN_W + 2, BTN_H + 2);

      if (stateChanged || touchedOld || touchedNew) {
        drawSingleHomeButton(i, (i == selectedBtn));
      }
    }

    if (prevCurY <= 60 && prevCurY + 11 >= 58) {
      gfx->drawFastHLine(0, 58, 320, MED_CYAN);
      gfx->drawFastHLine(0, 59, 320, MED_CYAN);
    }
    if (prevCurY <= 217 && prevCurY + 11 >= 216) {
      gfx->drawFastHLine(0, 216, 320, MED_DIM);
    }

    prevSelectedBtn = selectedBtn;
  } else if (
    currentScreen == SCREEN_RESULT ||
    currentScreen == SCREEN_HISTORY ||
    currentScreen == SCREEN_EXPORT
  ) {
    // Restore any HISTORY text/rows touched by the cursor
    if (currentScreen == SCREEN_HISTORY) {
      if (historyCount == 0) {
        if (rectsOverlap(prevCurX, prevCurY, 8, 11, 24, 78, 272, 84)) {
          drawHistoryEmptyCard();
        }
      } else {
        if (rectsOverlap(prevCurX, prevCurY, 8, 11, 18, 48, 284, 18)) {
          drawHistoryHeaderColumns();
        }
        int start = max(0, historyCount - 5);
        int slot = 0;
        for (int i = historyCount - 1; i >= start; i--) {
          int rowY = 70 + slot * 23 - 3;
          if (rectsOverlap(prevCurX, prevCurY, 8, 11, 18, rowY, 284, 20)) {
            drawHistoryRow(slot, i);
          }
          slot++;
        }
      }
    }

    // Restore EXPORT card border if touched
    if (currentScreen == SCREEN_EXPORT &&
        rectsOverlap(prevCurX, prevCurY, 8, 11, 18, 54, 284, 124)) {
      gfx->drawRoundRect(18, 54, 284, 124, 12, MED_ORANGE);
      gfx->drawRoundRect(19, 55, 282, 122, 11, MED_ORANGE);
    }

    // Restore RESULT card border if touched
    if (currentScreen == SCREEN_RESULT &&
        rectsOverlap(prevCurX, prevCurY, 8, 11, 16, 52, 288, 92)) {
      uint16_t acc = (queuedVerdict == "COUNTERFEIT") ? MED_RED : MED_GREEN;
      gfx->drawRoundRect(16, 52, 288, 92, 12, acc);
      gfx->drawRoundRect(17, 53, 286, 90, 11, acc);
      gfx->drawRoundRect(18, 54, 284, 88, 10, acc);
    }

    backHovered = isBackHovered(newX, newY);
    bool stateChanged = (backHovered != prevBackHovered);
    bool touchedOld   = rectsOverlap(prevCurX, prevCurY, 8, 11,
                                     BACK_X - 1, BACK_Y - 1, BACK_W + 2, BACK_H + 2);
    bool touchedNew   = rectsOverlap(newX, newY, 8, 11,
                                     BACK_X - 1, BACK_Y - 1, BACK_W + 2, BACK_H + 2);

    if (stateChanged || touchedOld || touchedNew) {
      drawBackButton(backHovered);
    }

    prevBackHovered = backHovered;
  }

  drawPointer(newX, newY);
  prevCurX = newX;
  prevCurY = newY;
}

// =====================================================
// 22. CURSOR CLICK (SINGLE-SHOT DEBOUNCED)
// =====================================================

void handleCursorClick() {
  unsigned long now = millis();
  if (now - lastClickHandledMs < CLICK_LOCKOUT_MS) return;
  lastClickHandledMs = now;

  if (currentScreen == SCREEN_HOME) {
    int clickedBtn = getHoveredHomeButton(curX, curY);
    if (clickedBtn == 0) {
      startPlacementScreen();
      Serial.println("EVENT:ENTER_PLACEMENT");
    } else if (clickedBtn == 1) {
      showHistoryScreen();
      drawPointer(curX, curY);
    } else if (clickedBtn == 2) {
      showExportScreen();
      drawPointer(curX, curY);
    }
  } else if (currentScreen == SCREEN_PLACEMENT) {
    drawHomeScreen();
    drawPointer(curX, curY);
    Serial.println("EVENT:EXIT_PLACEMENT");
  } else if (
    currentScreen == SCREEN_RESULT ||
    currentScreen == SCREEN_HISTORY ||
    currentScreen == SCREEN_EXPORT
  ) {
    if (isBackHovered(curX, curY)) {
      drawHomeScreen();
      drawPointer(curX, curY);
    }
  }
}

// =====================================================
// 23. ALIGNMENT & RESULT STATE TRANSITION HANDLERS
// =====================================================

void handleAlignmentSignal(AlignmentState newState) {
  if (currentScreen != SCREEN_PLACEMENT) return;
  if (alignTransitionStarted) return;

  if (newState != currentAlignState) {
    currentAlignState = newState;
    updatePlacementGuideVisuals(newState);

    if (newState == ALIGN_CONFIRMED) {
      alignConfirmedAtMs = millis();
      alignTransitionStarted = true;
    }
  }
}

void triggerFastCompletion(const String &verdict) {
  if (currentScreen != SCREEN_SCANNING || fastCompletionMode) return;

  queuedVerdict = verdict;
  verdictReceived = true;
  fastCompletionMode = true;
  lastFastTickMs = millis();

  if (prevBarFillWidth > 0) {
    gfx->fillRect(32, 166, prevBarFillWidth, 18, MED_GREEN);
  }
  prevDrawnPercent = -1;
  renderProgressBarAndPercent(scanPercent, true);
}

// =====================================================
// 24. PYTHON USB SERIAL COMMUNICATION HANDLER
// =====================================================

void processSerialCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd == "PING") {
    Serial.println("ACK:PONG");
  } else if (cmd == "GET_STATE") {
    if (currentScreen == SCREEN_PLACEMENT) {
      Serial.println("STATE:PLACEMENT");
    } else if (currentScreen == SCREEN_SCANNING) {
      Serial.println("STATE:SCANNING");
    } else if (currentScreen == SCREEN_RESULT) {
      Serial.println("STATE:RESULT");
    } else {
      Serial.println("STATE:HOME");
    }
  } else if (cmd == "MEDICINE_NOT_ALIGNED") {
    handleAlignmentSignal(ALIGN_NONE);
    Serial.println("ACK:MEDICINE_NOT_ALIGNED");
  } else if (cmd == "MEDICINE_ADJUST") {
    handleAlignmentSignal(ALIGN_ADJUST);
    Serial.println("ACK:MEDICINE_ADJUST");
  } else if (cmd == "MEDICINE_ALIGNED") {
    handleAlignmentSignal(ALIGN_CONFIRMED);
    Serial.println("ACK:MEDICINE_ALIGNED");
  } else if (cmd == "INSPECTION_RESULT_REAL") {
    triggerFastCompletion("REAL");
    Serial.println("ACK:INSPECTION_RESULT_REAL");
  } else if (cmd == "INSPECTION_RESULT_COUNTERFEIT") {
    triggerFastCompletion("COUNTERFEIT");
    Serial.println("ACK:INSPECTION_RESULT_COUNTERFEIT");
  } else {
    Serial.println("ERR:UNKNOWN_CMD");
  }
}

void handleSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLineBuffer.length() > 0) {
        processSerialCommand(serialLineBuffer);
        serialLineBuffer = "";
      }
    } else {
      if (serialLineBuffer.length() < 96) {
        serialLineBuffer += c;
      }
    }
  }
}

// =====================================================
// 25. HTTP RESPONSE, DASHBOARD & GENUINE CSV DOWNLOAD
// =====================================================

void sendResponse(
  WiFiClient &client,
  const char* contentType,
  const char* body
) {
  client.println("HTTP/1.1 200 OK");
  client.print("Content-Type: ");
  client.println(contentType);
  client.print("Content-Length: ");
  client.println(strlen(body));
  client.println("Cache-Control: no-store");
  client.println("Connection: close");
  client.println();
  client.print(body);
}

void sendCsvDownload(WiFiClient &client) {
  String csv = "Scan Number,Sample ID,Result\r\n";
  for (int i = 0; i < historyCount; i++) {
    csv += String(historyLog[i].id) + ",";
    csv += historyLog[i].sampleId + ",";
    csv += historyLog[i].verdict + "\r\n";
  }

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: text/csv; charset=utf-8");
  client.println("Content-Disposition: attachment; filename=\"medcheck_history.csv\"");
  client.println("X-Content-Type-Options: nosniff");
  client.print("Content-Length: ");
  client.println(csv.length());
  client.println("Cache-Control: no-store");
  client.println("Connection: close");
  client.println();
  client.print(csv);
}

void handleWebClients() {
  WiFiClient client = server.available();
  if (!client) return;

  String request = "";
  unsigned long timeout = millis() + 400;

  while (client.connected() && millis() < timeout) {
    while (client.available()) {
      char c = client.read();
      request += c;
      if (request.endsWith("\r\n\r\n")) break;
    }
    if (request.endsWith("\r\n\r\n")) break;
  }

  if (request.indexOf("GET /set?v=COUNTERFEIT") >= 0) {
    sendResponse(client, "text/plain", "OK");
    client.stop();
    triggerFastCompletion("COUNTERFEIT");
    return;
  }

  if (request.indexOf("GET /set?v=REAL") >= 0) {
    sendResponse(client, "text/plain", "OK");
    client.stop();
    triggerFastCompletion("REAL");
    return;
  }

  if (request.indexOf("GET /export") >= 0) {
    sendCsvDownload(client);
    delay(10);
    client.stop();
    return;
  }

  if (request.indexOf("GET /ping") >= 0) {
    sendResponse(client, "text/plain", "UNOR4_PHARMA");
    client.stop();
    return;
  }

  sendResponse(client, "text/html; charset=utf-8", PHONE_HTML);
  client.stop();
}

// =====================================================
// 26. NON-BLOCKING PLACEMENT TRANSITION & INSPECTION ENGINE
// =====================================================

void updateWorkflowTimers() {
  unsigned long now = millis();

  if (currentScreen == SCREEN_PLACEMENT && alignTransitionStarted) {
    if (now - alignConfirmedAtMs >= ALIGN_HOLD_BEFORE_SCAN_MS) {
      alignTransitionStarted = false;
      startScanScreen();
      Serial.println("EVENT:INSPECTION_STARTED");
    }
    return;
  }

  if (currentScreen != SCREEN_SCANNING) return;

  if (now - lastPulseFrameMs >= 280) {
    lastPulseFrameMs = now;
    pulseStep = (pulseStep + 1) % 4;
    drawInspectionCapsuleGraphic(pulseStep);
  }

  if (!fastCompletionMode && (now - lastStageChangeMs >= STAGE_ROTATE_INTERVAL_MS)) {
    lastStageChangeMs = now;
    stageIndex = (stageIndex + 1) % 7;
    drawInspectionStageBanner(stageIndex);
  }

  if (fastCompletionMode) {
    if (now - lastFastTickMs >= FAST_PROGRESS_INTERVAL_MS) {
      lastFastTickMs = now;

      if (scanPercent < 100) {
        int step = max(2, (100 - scanPercent) / 14);
        scanPercent = min(100, scanPercent + step);
        renderProgressBarAndPercent(scanPercent, true);
      } else {
        fastCompletionMode = false;
        showResultScreen();
        drawPointer(curX, curY);
        Serial.println("EVENT:INSPECTION_COMPLETE");
      }
    }
    return;
  }

  if (now - lastSlowTickMs >= SLOW_PROGRESS_INTERVAL_MS) {
    lastSlowTickMs = now;

    if (scanPercent < 92) {
      scanPercent++;
      renderProgressBarAndPercent(scanPercent, false);
    }
  }
}

// =====================================================
// 27. SETUP
// =====================================================

void setup() {
  Serial.begin(115200);

  gfx->begin();
  gfx->fillScreen(MED_BG);

  drawCenteredText("MEDCHECK PI", 85, 3, MED_WHITE);
  drawCenteredText("CONNECTING WIFI", 125, 1, MED_CYAN);

  WiFi.config(staticIP, dns, gateway, subnet);
  WiFi.begin(ssid, pass);

  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
  }

  while (WiFi.localIP() == IPAddress(0, 0, 0, 0)) {
    delay(200);
  }

  Serial.println();
  Serial.println("=================================");
  Serial.print("UNO R4 STATIC IP : ");
  Serial.println(WiFi.localIP());
  Serial.print("MOBILE DASHBOARD : http://");
  Serial.print(WiFi.localIP());
  Serial.println("/");
  Serial.print("CSV DOWNLOAD URL : http://");
  Serial.print(WiFi.localIP());
  Serial.println("/export");
  Serial.println("=================================");

  server.begin();
  udp.begin(UDP_PORT);

  drawHomeScreen();
  drawPointer(curX, curY);
}

// =====================================================
// 28. MAIN LOOP
// =====================================================

void loop() {
  handleSerialCommands();
  handleWebClients();

  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    if (len > 0) {
      packetBuffer[len] = '\0';

      int dx = 0, dy = 0, click = 0;
      if (sscanf(packetBuffer, "%d,%d,%d", &dx, &dy, &click) == 3) {
        curX = constrain(curX + dx, 6, 310);
        curY = constrain(curY + dy, 6, 228);
        updateCursor(curX, curY);

        if (click == 1 && !prevClick) {
          handleCursorClick();
        }
        prevClick = (click == 1);
      }
    }
  }

  updateWorkflowTimers();
}