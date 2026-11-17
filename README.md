# MEDCHECK-PI — AI MEDICINE AUTHENTICITY DETECTION PLATFORM
## Deep Learning Visual Packaging Verification & Anti-Counterfeit Screening

MEDCHECK-PI is a next-generation AI-assisted medicine verification and anti-counterfeit screening platform. Using high-resolution computer vision and deep optical packaging analysis, MEDCHECK-PI inspects the rear-side packaging of commercial pharmaceutical products to verify authenticity markers, micro-text embossing, batch integrity, and anti-tamper seals in real time.

---

## 1. System Overview

Counterfeit pharmaceuticals represent a grave threat to patient safety worldwide. MEDCHECK-PI combines neural vision architectures, edge inference, and dedicated IoT hardware indicators to rapidly classify pharmaceutical packaging as **AUTHENTIC (REAL)** or **COUNTERFEIT DETECTED**.

### Core Capabilities:
- **Neural Packaging Feature Extraction**: Scans blister foils, strip packaging, typography consistency, and manufacturer seals.
- **Micro-Text & Optical Anomaly Detection**: Cross-references surface texture density and print alignment against known pharmaceutical standards.
- **Hardware Telemetry via ESP32**: Streams real-time verification alerts directly to a high-contrast 1.3-inch SH1106 OLED display.
- **Multi-Device Live Sync**: High-speed real-time synchronization between inspection arenas, central analytics engines, and review terminals.

---

## 2. Integrated Medicine Detection Profiles

MEDCHECK-PI is pre-configured with high-precision recognition profiles for widely prescribed pharmaceutical strips:

| Medicine Name | Generic Formulation | Manufacturer | Packaging Architecture | Security Markers |
| :--- | :--- | :--- | :--- | :--- |
| **DOLO 650** | Paracetamol Tablets IP 650mg | Micro Labs Limited | Alu-Alu Blister Strip | Micro-text embossing, Tamper-evident seal, 2D DataMatrix |
| **AUGMENTIN 625 DUO** | Amoxicillin & Clavulanate IP | GlaxoSmithKline | Moisture-barrier Alu-Alu | GSK Watermark, Braille script, Hologram foil |
| **AZITHRAL 500** | Azithromycin Tablets IP 500mg | Alembic Pharmaceuticals | Blister Pack PVC/PVDC | Security Guilloche, QR Code, Batch laser etching |
| **PAN 40** | Pantoprazole Gastro-resistant 40mg | Alkem Laboratories | Silver Alu-Alu Blister | Holographic strip, Heat-seal verification, Micro-lettering |
| **ALLEGRA 120mg** | Fexofenadine HCl Tablets IP | Sanofi Healthcare | Clear Blister Strip | Anti-counterfeit 3D Tag, Registered Font Type |

---

## 3. Hardware Architecture & Pinout

```
+-------------------+        USB Serial (COM4 @ 115200)       +-------------------+
|   Host PC / AI    | =======================================> |  ESP32 DevKit V1  |
| Visual Neural Net |                                         |   Microcontroller |
+-------------------+                                         +---------+---------+
          |                                                             | I2C (0x3C)
          | Video Stream (OpenCV)                                       v
          v                                                   +-------------------+
+-------------------+                                         | 1.3" SH1106 OLED  |
| External USB      |                                         | 128x64 Diagnostic |
| High-Res Webcam   |                                         +-------------------+
+-------------------+
```

### ESP32 Serial Protocol:
- **`STATUS:SCANNING`**: Initiates scanning telemetry (`SCANNING... PLEASE WAIT`).
- **`RESULT:REAL`**: Signals authentic confirmation on OLED (`RESULT: REAL`).
- **`RESULT:COUNTERFEIT`**: Signals high-priority counterfeit warning on OLED (`RESULT: COUNTERFEIT`).
- **`STATUS:READY`**: Returns OLED to standby mode (`SYSTEM ONLINE, WAITING FOR SCAN`).

---

## 4. Quick Startup Instructions

### 1. Prerequisites
Ensure Python 3.10+ is installed and install the required dependencies:
```bash
pip install -r requirements.txt
```

### 2. Launch the Platform
```bash
python main.py
```

### 3. Verification Workflow
1. Navigate to the **Main AI Dashboard**: `http://localhost:8000/`
2. Position the medicine strip with the **rear side (barcode and composition details)** facing the camera.
3. Click **ANALYZE IMAGE**:
   - The system freezes the captured frame.
   - The multi-spectral scanning beam and radar reticle initiate optical feature analysis.
   - The ESP32 OLED updates to `SCANNING...`.
4. The system validates the packaging integrity and displays the comprehensive verification verdict along with the identified medicine specifications.
5. Click **START NEW SCAN** to reset the optical viewport for the next sample.
