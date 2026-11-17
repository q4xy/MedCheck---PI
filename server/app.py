from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit

import config
from camera.webcam import WebcamManager
from server.communication import ESP32Bridge
from server.state_manager import InspectionState

BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "dashboard" / "templates"),
    static_folder=str(BASE_DIR / "dashboard" / "static"),
)
app.config["SECRET_KEY"] = "medcheck-pi-secret-key-2026"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Ensure directories exist
config.IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Hardware & State Singletons
webcam = WebcamManager(
    device_index=config.USB_CAMERA_INDEX,
    width=config.CAMERA_WIDTH,
    height=config.CAMERA_HEIGHT,
    storage_dir=config.IMAGE_STORAGE_DIR,
)
esp32 = ESP32Bridge(config.SERIAL_PORT, config.SERIAL_BAUD_RATE)
state = InspectionState()
state.camera_index = config.USB_CAMERA_INDEX


def ensure_camera_ready() -> bool:
    if webcam.is_open():
        return True
    return webcam.open(state.camera_index)


def refresh_hardware_status() -> None:
    state.camera_connected = ensure_camera_ready()
    state.camera_name = webcam.camera_name if state.camera_connected else f"Camera #{state.camera_index} offline"
    state.camera_index = webcam.device_index
    state.esp32_connected = esp32.connected


def broadcast_state(event_name: str = "inspection_updated") -> None:
    refresh_hardware_status()
    payload = state.to_dict()
    socketio.emit(event_name, payload)


# ==========================================
# HTTP ROUTES
# ==========================================

@app.route("/")
def index():
    lan_ip = config.get_local_ip()
    port = config.FLASK_PORT
    return render_template("main_dashboard.html", lan_ip=lan_ip, port=port)


@app.route("/display")
def display_view():
    lan_ip = config.get_local_ip()
    port = config.FLASK_PORT
    return render_template("main_dashboard.html", lan_ip=lan_ip, port=port)


@app.route("/admin")
def admin_view():
    lan_ip = config.get_local_ip()
    port = config.FLASK_PORT
    return render_template("admin_dashboard.html", lan_ip=lan_ip, port=port)


@app.route("/control")
def control_redirect():
    return redirect("/admin")


@app.route("/captures/<path:filename>")
def serve_capture(filename: str):
    # Only serves current_scan.jpg, no scan history
    return send_from_directory(str(config.IMAGE_STORAGE_DIR), filename)


@app.route("/camera/stream")
def stream_video():
    """MJPEG stream of USB webcam with fallback placeholder."""
    ensure_camera_ready()

    def generate_frames():
        while True:
            frame = webcam.read_frame()
            if frame is None:
                frame = webcam.generate_placeholder_frame("USB CAMERA WAITING FOR SIGNAL")
                _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
                time.sleep(0.1)
                continue

            # Stream valid camera frame
            _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
            time.sleep(0.033)  # ~30 FPS

    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/status")
def api_status():
    refresh_hardware_status()
    data = state.to_dict()
    data["lan_ip"] = config.get_local_ip()
    data["port"] = config.FLASK_PORT
    data["admin_url"] = f"http://{data['lan_ip']}:{config.FLASK_PORT}/admin"
    return jsonify(data)


@app.route("/api/medicines")
def api_medicines():
    return jsonify({
        "current_medicine": state.current_medicine,
        "preset_medicines": state.to_dict()["preset_medicines"],
    })


@app.route("/api/camera/switch", methods=["GET", "POST"])
def api_switch_camera():
    idx = request.args.get("index") or (request.json.get("index") if request.is_json else None)
    if idx is not None:
        try:
            target_idx = int(idx)
            success = webcam.switch_camera(target_idx)
            state.camera_index = webcam.device_index
            state.camera_connected = success
            state.camera_name = webcam.camera_name
            broadcast_state()
            return jsonify({"success": success, "camera_index": webcam.device_index, "camera_name": webcam.camera_name})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": False, "error": "Missing index"}), 400


# ==========================================
# SOCKET.IO REAL-TIME EVENTS
# ==========================================

@socketio.on("connect")
def on_connect():
    refresh_hardware_status()
    emit("inspection_updated", state.to_dict())


@socketio.on("select_medicine")
def handle_select_medicine(data=None):
    if not data or not isinstance(data, dict):
        return
    med_id = data.get("id")
    if med_id:
        state.set_medicine_by_id(str(med_id))
    elif "index" in data:
        state.set_medicine_index(int(data.get("index", 0)))
    broadcast_state("inspection_updated")


@socketio.on("trigger_scan")
@socketio.on("analyze_image")
@socketio.on("start_scan")
def handle_analyze_image():
    """Invoked when user clicks ANALYZE IMAGE on Main Dashboard."""
    # 1. Capture single frame from USB webcam (NO history)
    saved_name = webcam.capture_current_frame(config.CURRENT_SCAN_FILENAME)
    image_url = f"/captures/{saved_name}" if saved_name else "/captures/current_scan.jpg"

    # 2. Update state to SCANNING
    state.start_scanning(image_url)

    # 3. Send STATUS:SCANNING to ESP32
    if esp32.connected:
        esp32.notify_scanning()

    # 4. Broadcast state immediately to both Main and Admin dashboards
    # Animation continues INDEFINITELY until admin decides!
    broadcast_state("inspection_updated")
    socketio.emit("scan_started", {
        "status": "SCANNING",
        "image_url": state.captured_image_url,
        "medicine": state.current_medicine,
    })


@socketio.on("select_result")
@socketio.on("admin_decision")
def handle_admin_decision(data=None):
    """Invoked when admin clicks COUNTERFEIT, REAL, or NO MEDICINE FOUND."""
    if not data or not isinstance(data, dict):
        return

    raw_result = str(data.get("result", "")).strip().upper()
    if raw_result not in {"REAL", "COUNTERFEIT", "NO MEDICINE FOUND"}:
        return

    if "medicine_id" in data:
        state.set_medicine_by_id(str(data["medicine_id"]))
    elif "medicine_index" in data:
        try:
            state.set_medicine_index(int(data["medicine_index"]))
        except Exception:
            pass

    # 1. Update state
    state.set_result(raw_result)

    # 2. Transmit to ESP32
    if raw_result == "REAL":
        esp32.notify_real()
    elif raw_result == "COUNTERFEIT":
        esp32.notify_counterfeit()
    elif raw_result == "NO MEDICINE FOUND":
        esp32.notify_ready()

    # 3. Synchronize both dashboards immediately within <1s
    broadcast_state("inspection_updated")
    socketio.emit("result_selected", {
        "result": raw_result,
        "status": state.current_status,
        "captured_image_url": state.captured_image_url,
        "medicine": state.current_medicine,
    })


@socketio.on("reset_scan")
@socketio.on("new_scan")
def handle_reset_scan():
    """Invoked when START NEW SCAN is clicked on Main Dashboard."""
    state.reset_ready()
    if esp32.connected:
        esp32.notify_ready()
    broadcast_state("inspection_updated")
    socketio.emit("scan_reset", {"status": "SYSTEM READY"})
