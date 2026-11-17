# MEDCHECK PI

**Smart Medicine Inspection System**

MEDCHECK PI is a local demonstration app for capturing the rear side of medicine packaging, checking an image against a single configured reference, showing visual observations, and synchronizing a presentation dashboard, phone operator dashboard, and optional ESP32 OLED.

> Packaging resemblance or a reference-image match does not establish medicine authenticity, ingredients, safety, batch/expiry validity, or counterfeit status. REAL and COUNTERFEIT are operator-selected demonstration outcomes only. Do not use this prototype for medical or purchasing decisions.

## What is supported

- One medicine profile only: **Iron and Folic Acid Tablets IP**.
- An external USB webcam at the single configured index in `config.py`. No other index is tried as a fallback.
- Optional ESP32 on COM4 at 115200 baud.
- Local Flask + Socket.IO; no cloud service is required.
- Optional reference-image matching and experimental binary model support.
- Persisted history and counts based only on actual captures/analysis/operator decisions.

The existing rear-side package photograph in `captures/current_scan.jpg` is installed as the initial reference at `dataset/reference/iron_folic_acid_reference.jpg`. It visually shows the supported Iron and Folic Acid packaging. No trained model is present. The reference photo itself matches; the prototype did not detect a red mark in that image. Other package-like captures that do not match the reference are returned as **NEEDS MANUAL REVIEW**. The rule-based shape/red-mark checks are a prototype, not a trained classifier.

The red-mark observation is generated only when red pixels are detected in the lower printed area. It is not proof of an expiry correction or counterfeit product. No batch number or expiry date is extracted or invented.

## Project layout

```text
MedCheck-PI/
  main.py
  config.py
  requirements.txt
  camera/
    webcam.py
    camera_test.py
  server/
    app.py
    state_manager.py
    communication.py
  intelligence/
    predict.py
    train.py
    README.md
    model/
  hardware/
    esp32_display.ino
  dashboard/
    templates/
      main_dashboard.html
      admin_dashboard.html
    static/
      css/
      js/
  dataset/
    reference/
    train/
      medicine_back/
      other/
    validation/
      medicine_back/
      other/
  captures/
  logs/
  tests/
```

## Windows install and run

Install Python 3.10 or newer, then from PowerShell in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

The server binds to `0.0.0.0:8000`.

- Presentation/admin display on the laptop: `http://localhost:8000/display`
- Phone operator page on the same Wi-Fi: `http://<laptop-LAN-IP>:8000/admin`
- `ipconfig` shows the laptop's IPv4 address.

For laptop keyboard capture, open the presentation page using `localhost` (or `127.0.0.1`) on the laptop. Press **S** to capture and **R** to retake. The phone operator page has no capture or retake control.

## External USB webcam setup

Run the discovery utility:

```powershell
python camera\camera_test.py
```

It previews detected camera indices. Confirm visually which one is the external USB webcam and press **S** in that preview. Set only `USB_CAMERA_INDEX` in `config.py` to that index, then restart the app. The runtime opens only that index; it may try DirectShow and then OpenCV's default backend for the same index, but never switches to another camera. If it is unavailable, the stream shows a disconnected placeholder and capture is refused.

## ESP32 + OLED

Configuration in `config.py`:

- Serial port: `COM4`
- Baud: `115200`
- OLED I2C address: `0x3C`

Install the Arduino libraries **Adafruit SSD1306** and **Adafruit GFX Library**. Upload `hardware/esp32_display.ino` to the ESP32. The sketch uses a 128x64 SSD1306-compatible display. The app tolerates a disconnected ESP32 and reports its status; physical OLED behavior has not been verified by software tests.

Serial messages are newline terminated:

```text
STATUS:READY
STATUS:SCANNING
STATUS:ACCEPTED
STATUS:REJECTED
STATUS:MANUAL_REVIEW
STATUS:RED_MARK
CAMERA:CONNECTED
CAMERA:DISCONNECTED
RESULT:REAL
RESULT:COUNTERFEIT
```

Close Arduino Serial Monitor before running the app; only one application can own COM4 at a time.

## Reference matching

The initial reference photo is stored at:

```text
dataset\reference\iron_folic_acid_reference.jpg
```

The current matcher is an ORB feature/homography prototype; a match allows operator review but does not authenticate the medicine. Replace that file only with a verified reference you are authorized to use. If no reference exists or the match is uncertain, the application requires manual review.

## Optional model training

Only add genuine, labeled, authorized images. Keep train and validation images separate:

```text
dataset/train/medicine_back/
dataset/train/other/
dataset/validation/medicine_back/
dataset/validation/other/
```

TensorFlow is optional and is not included in the normal app requirements. Install a version compatible with your Python platform, then run:

```powershell
python intelligence\train.py
```

The trainer uses MobileNetV2 initialized without downloaded pretrained weights, saves the model and labels under `intelligence/model`, and requires both classes in both splits. Measure and document independent validation performance before relying on it. The model classifies package-vs-other only; identification as the named medicine still requires a reference-image match.

## Workflow

1. Start `python main.py`.
2. Confirm the configured USB camera is connected on the presentation dashboard.
3. Position the package **back side** and press **S** on the laptop.
4. On the phone, press **ANALYZE IMAGE**.
5. Review the classification and any red-mark observation.
6. REAL/COUNTERFEIT become enabled only for a supported-reference match.
7. An operator may select REAL or COUNTERFEIT; both dashboards, saved history, counts and OLED are updated.
8. Press **R** on the laptop to discard the current decision and capture a new sample. The previous inspection remains in history as a separate record.

`NO MEDICINE FOUND` and `NEEDS MANUAL REVIEW` never enable the decision buttons. New captures invalidate the current acceptance and decision state.

## Stored data and limits

- Captures: unique JPEGs under `captures/`.
- Inspection history: `logs/inspection_history.json`, written atomically.
- Summary counts: computed from saved records; only operator-confirmed decisions count as REAL/COUNTERFEIT, and only the NO MEDICINE FOUND classification contributes to its count.
- Existing model: none included.
- Dataset/reference photo: one existing rear-side package photo is installed as the initial reference.
- Hardware: webcam, COM4, ESP32 and OLED require physical testing on the target machine.
- Prototype image analysis may misclassify. A red region in the lower half is only a visual observation and may be unrelated to package printing.

## Tests

```powershell
python -m compileall main.py config.py server camera intelligence tests
python -m unittest discover -s tests -v
```

These are software tests with mocked/no physical hardware; they do not prove camera, serial, OLED, model, or medicine-authenticity performance.

## Troubleshooting

- **USB webcam disconnected:** run `python camera\camera_test.py`, verify the external camera in the preview, set its index in `config.py`, close other camera apps, and restart. The app intentionally does not switch to the laptop camera.
- **COM4 unavailable:** disconnect Serial Monitor/other serial tools, confirm the ESP32 enumerates as COM4, and restart.
- **Phone cannot connect:** confirm both devices are on the same Wi-Fi, allow Python through Windows Firewall for private networks, and use the laptop IPv4 address with port 8000.
- **Manual review:** low-quality or unmatched images are deliberately not identified; replace the initial reference only with a verified image if needed.
- **OLED blank:** verify I2C wiring/address, board selection, SSD1306 compatibility, and the two required Adafruit libraries.
