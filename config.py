from __future__ import annotations

import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_NAME = "MEDCHECK PI"
PROJECT_SUBTITLE = "SMART MEDICINE INSPECTION SYSTEM"

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8000
SECRET_KEY = "medcheck-pi-local-demo"

# Only this configured external USB camera index is opened. No fallback is used.
USB_CAMERA_INDEX = 1
CAMERA_BACKEND = "DSHOW"
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
ALLOW_INTERNAL_CAMERA_FALLBACK = False

SERIAL_PORT = "COM4"
SERIAL_BAUD_RATE = 115200
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_I2C_ADDRESS = 0x3C

IMAGE_STORAGE_DIR = BASE_DIR / "captures"
DATASET_DIR = BASE_DIR / "dataset"
TRAIN_DATASET_DIR = DATASET_DIR / "train"
VALIDATION_DATASET_DIR = DATASET_DIR / "validation"
MEDICINE_REFERENCE_MANIFEST = DATASET_DIR / "reference" / "medicines.json"
MEDICINE_REFERENCE_IMAGE = DATASET_DIR / "reference" / "iron_folic_acid_reference.jpg"
MODEL_PATH = BASE_DIR / "intelligence" / "model" / "trained_model.keras"
HISTORY_PATH = BASE_DIR / "logs" / "inspection_history.json"
LOG_DIRECTORY = BASE_DIR / "logs"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
ANALYSIS_CONFIDENCE_THRESHOLD = 0.85
REFERENCE_MATCH_THRESHOLD = 0.32
LOG_LEVEL = "INFO"


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
