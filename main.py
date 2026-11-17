import logging

import config
from server.app import app, socketio, webcam, esp32


def main() -> None:
    config.LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOG_DIRECTORY / "medcheck.log", encoding="utf-8"),
        ],
    )
    lan_ip = config.get_local_ip()
    port = config.FLASK_PORT

    print("[*] Opening only configured external USB webcam...")
    camera_connected = webcam.open(config.USB_CAMERA_INDEX)
    print(f"    Webcam: {webcam.camera_name if camera_connected else webcam.last_error}")
    print(f"[*] Connecting to ESP32 on {config.SERIAL_PORT}...")
    print(f"    ESP32: {'CONNECTED' if esp32.connect() else esp32.last_error}")
    print(f"[*] Presentation dashboard: http://localhost:{port}/display")
    print(f"[*] Operator dashboard:     http://{lan_ip}:{port}/admin")
    print(f"[*] Laptop capture controls: S = capture, R = retake")

    try:
        socketio.run(
            app,
            host=config.FLASK_HOST,
            port=port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    finally:
        webcam.close()
        esp32.close()


if __name__ == "__main__":
    main()
