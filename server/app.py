from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit

import config
from camera.webcam import WebcamManager
from intelligence.predict import analyze_image
from server.communication import ESP32Bridge
from server.state_manager import InspectionState

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "dashboard" / "templates"),
    static_folder=str(BASE_DIR / "dashboard" / "static"),
)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    MAX_CONTENT_LENGTH=config.MAX_IMAGE_BYTES,
)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

for directory in (config.IMAGE_STORAGE_DIR, config.LOG_DIRECTORY, config.DATASET_DIR / "reference"):
    directory.mkdir(parents=True, exist_ok=True)

webcam = WebcamManager(
    device_index=config.USB_CAMERA_INDEX,
    width=config.CAMERA_WIDTH,
    height=config.CAMERA_HEIGHT,
    storage_dir=config.IMAGE_STORAGE_DIR,
)
esp32 = ESP32Bridge(config.SERIAL_PORT, config.SERIAL_BAUD_RATE)
state = InspectionState(config.HISTORY_PATH)
state.camera_index = config.USB_CAMERA_INDEX
_capture_lock = threading.Lock()
_last_camera_serial_state: Optional[bool] = None


def refresh_hardware_status(attempt_camera_open: bool = False) -> None:
    global _last_camera_serial_state
    if attempt_camera_open and not webcam.is_open():
        webcam.open(config.USB_CAMERA_INDEX)
    camera_connected = webcam.is_open()
    camera_name = (
        webcam.camera_name
        if camera_connected
        else f"USB WEBCAM DISCONNECTED (index {config.USB_CAMERA_INDEX})"
    )
    state.set_hardware_status(
        camera_connected,
        camera_name,
        config.USB_CAMERA_INDEX,
        esp32.connected,
    )
    if _last_camera_serial_state is None or _last_camera_serial_state != camera_connected:
        esp32.notify_camera(camera_connected)
        _last_camera_serial_state = camera_connected


def broadcast_state(event_name: str = "inspection_updated") -> None:
    refresh_hardware_status()
    socketio.emit(event_name, state.to_dict())


def _capture_current_image() -> bool:
    if not _capture_lock.acquire(blocking=False):
        state.last_error = "Capture is already in progress."
        broadcast_state()
        return False
    try:
        state.reset_current()
        if not webcam.is_open() and not webcam.open(config.USB_CAMERA_INDEX):
            state.current_status = "USB WEBCAM DISCONNECTED"
            state.last_error = webcam.last_error or "Configured external USB webcam is unavailable."
            broadcast_state()
            return False

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"scan_{stamp}.jpg"
        saved_name = webcam.capture_current_frame(filename)
        if saved_name is None:
            state.current_status = "IMAGE CAPTURE FAILED"
            state.last_error = webcam.last_error or "The configured USB webcam did not return a frame."
            broadcast_state()
            return False

        image_url = f"/captures/{saved_name}"
        state.start_capture(saved_name, image_url)
        state.last_error = ""
        if esp32.connected:
            esp32.notify_ready()
        socketio.emit("capture_completed", state.to_dict())
        broadcast_state()
        return True
    except Exception:
        logger.exception("Unexpected error capturing from configured USB webcam")
        try:
            state.reset_current()
        except OSError:
            logger.exception("Could not save invalidated inspection history")
        state.current_status = "IMAGE CAPTURE FAILED"
        state.last_error = "Capture failed. Check the configured USB webcam and application log."
        broadcast_state()
        return False
    finally:
        _capture_lock.release()


def _run_analysis(image_name: str, inspection_id: str) -> None:
    image_path = config.IMAGE_STORAGE_DIR / image_name
    try:
        result = analyze_image(image_path)
        completed_id = state.finish_analysis(result, expected_inspection_id=inspection_id)
        if completed_id is None:
            return
        classification = result.get("classification")
        if classification == "SUPPORTED MEDICINE FOUND":
            esp32.notify_accepted()
            if result.get("red_mark_detected"):
                esp32.notify_red_mark()
                socketio.emit("red_mark_detected", state.to_dict())
        elif classification == "NO MEDICINE FOUND":
            esp32.notify_rejected()
            socketio.emit("no_medicine_found", state.to_dict())
        else:
            esp32.notify_manual_review()
            socketio.emit("manual_review_required", state.to_dict())
        socketio.emit("analysis_completed", state.to_dict())
        broadcast_state()
    except Exception:
        logger.exception("Image analysis failed for inspection %s", inspection_id)
        try:
            state.fail_analysis(inspection_id, "Image analysis failed. Please retry or review the image manually.")
        except OSError:
            logger.exception("Could not save the failed analysis record")
            state.last_error = "Image analysis failed and inspection history could not be saved."
        socketio.emit("manual_review_required", state.to_dict())
        broadcast_state()


def _local_capture_request() -> bool:
    return request.remote_addr in {"127.0.0.1", "::1", "localhost"} or (
        app.config.get("TESTING") and request.remote_addr in {"testclient", None}
    )


@app.route("/")
@app.route("/display")
def display_view():
    return render_template("inspection.html", lan_ip=config.get_local_ip(), port=config.FLASK_PORT)


@app.route("/admin")
def operator_view():
    return render_template("control.html", lan_ip=config.get_local_ip(), port=config.FLASK_PORT)


@app.route("/control")
def control_redirect():
    return redirect("/admin")


@app.route("/captures/<path:filename>")
def serve_capture(filename: str):
    if not re.fullmatch(r"scan_[A-Za-z0-9_-]+\.jpg", filename):
        abort(404)
    return send_from_directory(config.IMAGE_STORAGE_DIR, filename, max_age=0)


@app.route("/camera/stream")
def stream_video():
    def generate_frames():
        last_retry = 0.0
        last_reported_camera_state: Optional[bool] = None
        while True:
            frame = webcam.read_frame()
            if frame is None:
                if time.monotonic() - last_retry >= 2.0:
                    webcam.open(config.USB_CAMERA_INDEX)
                    last_retry = time.monotonic()
                frame = webcam.generate_placeholder_frame()
            connected = webcam.is_open()
            if connected != last_reported_camera_state:
                refresh_hardware_status()
                socketio.emit("inspection_updated", state.to_dict())
                last_reported_camera_state = connected
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
            socketio.sleep(0.04)

    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/status")
def api_status():
    refresh_hardware_status()
    return jsonify(state.to_dict())


@app.route("/api/medicines")
def api_medicines():
    return jsonify({"supported_medicine": "Iron and Folic Acid Tablets IP"})


@socketio.on("connect")
def on_connect():
    refresh_hardware_status(attempt_camera_open=True)
    emit("inspection_updated", state.to_dict())


@socketio.on("capture_image")
@socketio.on("trigger_scan")
def handle_capture():
    if not _local_capture_request():
        state.last_error = "Capture and retake are available only from the laptop dashboard."
        emit("inspection_updated", state.to_dict())
        return
    _capture_current_image()


@socketio.on("retake_scan")
@socketio.on("reset_scan")
def handle_retake():
    if not _local_capture_request():
        state.last_error = "Capture and retake are available only from the laptop dashboard."
        emit("inspection_updated", state.to_dict())
        return
    _capture_current_image()


@socketio.on("analyze_image")
def handle_analyze_image():
    try:
        analysis_request = state.start_analysis()
    except OSError:
        logger.exception("Could not persist analysis-start state")
        state.mark_storage_error("Could not save inspection history. Check the application log and storage permissions.")
        broadcast_state()
        return
    if analysis_request is None:
        state.last_error = "Capture an image before starting analysis, or wait for the current analysis to finish."
        broadcast_state()
        return
    image_name, inspection_id = analysis_request
    if not re.fullmatch(r"scan_[A-Za-z0-9_-]+\.jpg", image_name):
        state.fail_analysis(state.inspection_id or "", "The captured image name is invalid.")
        broadcast_state()
        return
    image_path = config.IMAGE_STORAGE_DIR / image_name
    if not image_path.is_file() or image_path.stat().st_size > config.MAX_IMAGE_BYTES:
        inspection_id = state.inspection_id or ""
        state.fail_analysis(inspection_id, "The captured image is missing or exceeds the configured image size limit.")
        broadcast_state()
        return
    esp32.notify_scanning()
    socketio.emit("analysis_started", state.to_dict())
    broadcast_state()
    socketio.start_background_task(_run_analysis, image_name, inspection_id)


@socketio.on("select_result")
def handle_operator_decision(data=None):
    if not isinstance(data, dict):
        state.last_error = "Invalid decision request."
        broadcast_state()
        return
    result = str(data.get("result", "")).strip().upper()
    if result not in {"REAL", "COUNTERFEIT"}:
        state.last_error = "Only REAL or COUNTERFEIT is a valid operator decision."
        broadcast_state()
        return
    try:
        decision_saved = state.set_decision(result)
    except OSError:
        logger.exception("Could not persist operator decision")
        state.last_error = "The operator decision could not be saved. Check inspection-history storage permissions."
        broadcast_state()
        return
    if not decision_saved:
        state.last_error = "A decision requires a currently accepted supported-medicine image."
        broadcast_state()
        return

    esp32.notify_result(result)
    socketio.emit("operator_decision", state.to_dict())
    socketio.emit("result_selected", {
        "result": result,
        "status": state.current_status,
        "inspection_id": state.inspection_id,
    })
    broadcast_state()


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Image exceeds the configured maximum size."}), 413


def shutdown_hardware() -> None:
    webcam.close()
    esp32.close()


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
