from pathlib import Path
import socket

BASE_DIR = Path(__file__).resolve().parent

# External USB Webcam configuration
# If USB camera is index 1, set to 1; if index 0, set to 0.
USB_CAMERA_INDEX = 1
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# Network Configuration
# Listening on 0.0.0.0 allows access from mobile devices and other laptops on the same Wi-Fi.
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8000

# ESP32 Serial Communication (DevKit with 1.3" SH1106 OLED)
SERIAL_PORT = "COM4"
SERIAL_BAUD_RATE = 115200

# Active scan image path (only single current image, no history)
IMAGE_STORAGE_DIR = BASE_DIR / "captures"
CURRENT_SCAN_FILENAME = "current_scan.jpg"


def get_local_ip() -> str:
    """Detect the local machine's LAN IP address for cross-device access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Does not actually connect but determines routing interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
