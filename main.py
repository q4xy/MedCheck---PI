import sys
import config
from server.app import app, socketio, webcam, esp32


def print_banner(lan_ip: str, port: int) -> None:
    sep = "=" * 66
    print("\n" + sep)
    print("  MEDCHECK-PI -- AI MEDICINE VERIFICATION PLATFORM")
    print("  Real-time Multi-Dashboard & ESP32 Hardware Integration")
    print(sep)
    print(f"  [+] Main Dashboard:    http://localhost:{port}/")
    print(f"  [+] Network Main:      http://{lan_ip}:{port}/")
    print(f"  [+] Admin Dashboard:   http://localhost:{port}/admin")
    print(f"  [+] Network Admin:     http://{lan_ip}:{port}/admin")
    print(f"  [+] Host Binding:      {config.FLASK_HOST}:{port}")
    print(f"  [+] Camera Index:      Device #{config.USB_CAMERA_INDEX}")
    print(f"  [+] ESP32 Serial:      {config.SERIAL_PORT} @ {config.SERIAL_BAUD_RATE} baud")
    print(sep)
    print("  Ready. Open Admin Dashboard on phone/tablet or separate browser.\n")


def main():
    lan_ip = config.get_local_ip()
    port = config.FLASK_PORT

    print("[*] Initializing USB Webcam...")
    cam_ok = webcam.open()
    print(f"    Camera status: {'CONNECTED (' + webcam.camera_name + ')' if cam_ok else 'OFFLINE (Will retry dynamically)'}")

    print(f"[*] Connecting to ESP32 on {config.SERIAL_PORT}...")
    esp_ok = esp32.connect()
    print(f"    ESP32 status:  {'CONNECTED' if esp_ok else 'OFFLINE (' + esp32.last_error + ')'}")

    print_banner(lan_ip, port)

    socketio.run(
        app,
        host=config.FLASK_HOST,
        port=port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
