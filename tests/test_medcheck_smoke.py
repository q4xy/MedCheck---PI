import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

import config
from camera.webcam import WebcamManager
from intelligence.predict import analyze_image, _detect_red_mark
from server.app import app, socketio, state, webcam, esp32
from server.communication import ESP32Bridge
from server.state_manager import InspectionState


class MedCheckSmokeTests(unittest.TestCase):
    def setUp(self):
        self.old_testing = app.config.get("TESTING", False)
        app.config["TESTING"] = True
        self.old_history_path = state.history_path
        self.old_history = state.history
        state.history_path = None
        state.history = []
        state.reset_current()
        self.hardware_patches = [
            patch.object(webcam, "open", return_value=False),
            patch.object(esp32, "notify_camera", return_value=True),
        ]
        for item in self.hardware_patches:
            item.start()

    def tearDown(self):
        for item in self.hardware_patches:
            item.stop()
        state.history_path = self.old_history_path
        state.history = self.old_history
        state.reset_current()
        app.config["TESTING"] = self.old_testing

    def test_config_uses_one_external_index_and_com4(self):
        self.assertEqual(config.SERIAL_PORT, "COM4")
        self.assertEqual(config.USB_CAMERA_INDEX, 1)
        self.assertFalse(config.ALLOW_INTERNAL_CAMERA_FALLBACK)

    def test_dashboard_routes(self):
        client = app.test_client()
        display = client.get("/display")
        operator = client.get("/admin")
        self.assertEqual(display.status_code, 200)
        self.assertEqual(operator.status_code, 200)
        self.assertEqual(client.get("/control").status_code, 302)
        self.assertNotIn(b"<button", display.data)
        self.assertEqual(operator.data.count(b"<button "), 3)

    def test_camera_open_does_not_fall_back_to_another_index(self):
        cap = MagicMock()
        cap.isOpened.return_value = False
        with patch("camera.webcam.cv2.VideoCapture", return_value=cap) as open_camera:
            camera = WebcamManager(device_index=2, storage_dir=Path(tempfile.gettempdir()))
            self.assertFalse(camera.open())
        self.assertGreaterEqual(open_camera.call_count, 1)
        self.assertTrue(all(call.args[0] == 2 for call in open_camera.call_args_list))

    def test_black_image_classifies_as_no_medicine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "blank.jpg"
            cv2.imwrite(str(image_path), np.zeros((300, 400, 3), dtype=np.uint8))
            result = analyze_image(image_path)
        self.assertEqual(result["classification"], "NO MEDICINE FOUND")
        self.assertFalse(result["red_mark_detected"])

    def test_installed_reference_matches_its_source_photo(self):
        image_path = config.IMAGE_STORAGE_DIR / "current_scan.jpg"
        if not image_path.is_file() or not config.MEDICINE_REFERENCE_IMAGE.is_file():
            self.skipTest("Project reference sample is unavailable.")
        result = analyze_image(image_path)
        self.assertEqual(result["classification"], "SUPPORTED MEDICINE FOUND")
        self.assertEqual(result["medicine_name"], "Iron and Folic Acid Tablets IP")
        self.assertIn("does not verify medicine authenticity", result["message"])

    def test_red_mark_detector_uses_lower_printed_area(self):
        image = np.zeros((300, 400, 3), dtype=np.uint8)
        image[:] = (220, 220, 220)
        cv2.rectangle(image, (150, 220), (250, 235), (0, 0, 220), -1)
        self.assertTrue(_detect_red_mark(image))

    def test_analysis_reports_red_mark_only_when_pixels_are_present(self):
        image = np.full((300, 400, 3), 220, dtype=np.uint8)
        cv2.rectangle(image, (40, 35), (360, 265), (30, 30, 30), 4)
        cv2.rectangle(image, (150, 220), (250, 235), (0, 0, 220), -1)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.jpg"
            cv2.imwrite(str(path), image)
            result = analyze_image(path)
        self.assertTrue(result["red_mark_detected"])
        self.assertIn("Exact expiry-date alignment requires manual verification.", result["red_mark_observation"])

    def test_history_counts_only_decisions_and_no_medicine_classification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history = InspectionState(Path(temp_dir) / "history.json")
            first = history.start_capture("scan_one.jpg", "/captures/scan_one.jpg")
            history.finish_analysis({"classification": "SUPPORTED MEDICINE FOUND"}, first)
            self.assertTrue(history.set_decision("REAL"))
            second = history.start_capture("scan_two.jpg", "/captures/scan_two.jpg")
            history.finish_analysis({"classification": "NO MEDICINE FOUND"}, second)
            self.assertEqual(history.summary_counts(), {"counterfeit": 0, "real": 1, "no_medicine_found": 1})
            reloaded = InspectionState(Path(temp_dir) / "history.json")
            self.assertEqual(reloaded.summary_counts(), history.summary_counts())

    def test_reset_marks_unanalyzed_capture_as_superseded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history = InspectionState(Path(temp_dir) / "history.json")
            inspection_id = history.start_capture("scan_one.jpg", "/captures/scan_one.jpg")
            history.reset_current()
            record = next(item for item in history.history if item["inspection_id"] == inspection_id)
            self.assertEqual(record["classification"], "CAPTURE SUPERSEDED")
            self.assertEqual(
                record["analysis_message"],
                "A newer capture replaced this image before analysis completed.",
            )

    def test_decision_is_rejected_without_accepted_current_capture(self):
        state.start_capture("scan_test.jpg", "/captures/scan_test.jpg")
        self.assertFalse(state.set_decision("COUNTERFEIT"))
        self.assertIsNone(state.selected_result)

    def test_socket_initial_state_is_sent(self):
        with patch.object(webcam, "is_open", return_value=False), patch.object(webcam, "open", return_value=False):
            flask_client = app.test_client()
            flask_client.environ_base["REMOTE_ADDR"] = "127.0.0.1"
            client = socketio.test_client(app, flask_test_client=flask_client)
        self.assertTrue(client.is_connected())
        events = client.get_received()
        state_events = [event for event in events if event["name"] == "inspection_updated"]
        self.assertTrue(state_events)
        client.disconnect()

    def test_invalid_operator_result_does_not_change_state(self):
        client = socketio.test_client(app)
        client.emit("select_result", {"result": "FAKE"})
        self.assertIsNone(state.selected_result)
        client.disconnect()

    def test_serial_protocol_is_newline_terminated_and_single_owner(self):
        bridge = ESP32Bridge("COM4", 115200)
        fake_serial = MagicMock()
        fake_serial.is_open = True
        bridge.serial_handle = fake_serial
        bridge.connected = True
        with patch("server.communication.serial.Serial") as open_serial:
            self.assertTrue(bridge.connect())
            self.assertTrue(bridge.notify_scanning())
            self.assertFalse(bridge.send_command("RESULT:FAKE"))
        open_serial.assert_not_called()
        fake_serial.write.assert_called_once_with(b"STATUS:SCANNING\n")

    def test_capture_analysis_decision_and_retake_flow(self):
        image_name = f"scan_test_{uuid4().hex}.jpg"
        image_path = config.IMAGE_STORAGE_DIR / image_name
        image_path.write_bytes(b"test frame")
        try:
            with (
                patch.object(webcam, "is_open", return_value=True),
                patch.object(webcam, "capture_current_frame", return_value=image_name),
                patch.object(esp32, "notify_camera", return_value=True),
                patch.object(esp32, "notify_scanning", return_value=True),
                patch.object(esp32, "notify_accepted", return_value=True),
                patch.object(esp32, "notify_result", return_value=True),
                patch("server.app.analyze_image", return_value={
                    "classification": "SUPPORTED MEDICINE FOUND",
                    "message": "Reference match.",
                    "confidence": 0.9,
                    "visual_observations": [],
                    "red_mark_detected": False,
                    "red_mark_observation": "",
                }),
                patch.object(socketio, "start_background_task", side_effect=lambda fn, *args: fn(*args)),
            ):
                presentation_client = socketio.test_client(app)
                operator_client = socketio.test_client(app)
                presentation_client.emit("capture_image")
                self.assertEqual(state.scan_state, "CAPTURED")
                operator_client.emit("analyze_image")
                self.assertTrue(state.image_accepted)
                operator_client.emit("select_result", {"result": "COUNTERFEIT"})
                self.assertEqual(state.selected_result, "COUNTERFEIT")
                self.assertEqual(state.summary_counts()["counterfeit"], 1)
                synced = [
                    event for event in presentation_client.get_received()
                    if event["name"] == "inspection_updated"
                ]
                self.assertTrue(synced)
                self.assertEqual(synced[-1]["args"][0]["selected_result"], "COUNTERFEIT")
                presentation_client.emit("retake_scan")
                self.assertFalse(state.image_accepted)
                self.assertIsNone(state.selected_result)
                presentation_client.disconnect()
                operator_client.disconnect()
        finally:
            image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
