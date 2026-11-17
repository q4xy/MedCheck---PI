import unittest
from unittest.mock import MagicMock, patch

import config
from server.app import app, socketio, state, esp32


class MedCheckSocketIOTests(unittest.TestCase):
    def setUp(self):
        state.reset_ready()
        self.mock_esp32 = MagicMock()
        self.original_connected = esp32.connected
        esp32.connected = True
        self.esp32_patch = patch.object(esp32, "send_command", MagicMock(return_value=True))
        self.mock_send = self.esp32_patch.start()

    def tearDown(self):
        self.esp32_patch.stop()
        esp32.connected = self.original_connected

    def test_analyze_image_triggers_scanning_and_esp32_command(self):
        client = socketio.test_client(app)
        self.assertTrue(client.is_connected())

        # Trigger ANALYZE IMAGE
        client.emit("analyze_image")

        # Verify state is SCANNING
        self.assertEqual(state.scan_state, "SCANNING")
        self.assertEqual(state.current_status, "SCANNING")
        self.assertIsNone(state.selected_result)

        # Verify ESP32 received STATUS:SCANNING
        self.mock_send.assert_called_with("STATUS:SCANNING")

        # Verify scan_started event was broadcasted
        received = client.get_received()
        event_names = [e["name"] for e in received]
        self.assertIn("scan_started", event_names)
        self.assertIn("inspection_updated", event_names)

        client.disconnect()

    def test_admin_decision_counterfeit(self):
        client = socketio.test_client(app)
        client.emit("analyze_image")

        # Admin selects COUNTERFEIT
        client.emit("select_result", {"result": "COUNTERFEIT"})

        # Verify state
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "COUNTERFEIT")
        self.assertEqual(state.current_status, "RESULT: COUNTERFEIT")

        # Verify ESP32 received RESULT:COUNTERFEIT
        self.mock_send.assert_called_with("RESULT:COUNTERFEIT")

        # Verify broadcast
        received = client.get_received()
        event_names = [e["name"] for e in received]
        self.assertIn("result_selected", event_names)
        last_result_evt = [e for e in received if e["name"] == "result_selected"][-1]
        self.assertEqual(last_result_evt["args"][0]["result"], "COUNTERFEIT")

        client.disconnect()

    def test_admin_decision_real(self):
        client = socketio.test_client(app)
        client.emit("analyze_image")

        # Admin selects REAL
        client.emit("select_result", {"result": "REAL"})

        # Verify state
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "REAL")

        # Verify ESP32 received RESULT:REAL
        self.mock_send.assert_called_with("RESULT:REAL")

        client.disconnect()

    def test_admin_decision_no_medicine_found(self):
        client = socketio.test_client(app)
        client.emit("analyze_image")

        # Admin selects NO MEDICINE FOUND
        client.emit("select_result", {"result": "NO MEDICINE FOUND"})

        # Verify state
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "NO MEDICINE FOUND")

        # Verify ESP32 received STATUS:READY
        self.mock_send.assert_called_with("STATUS:READY")

        client.disconnect()

    def test_reset_scan(self):
        client = socketio.test_client(app)
        client.emit("select_result", {"result": "REAL"})

        # User clicks START NEW SCAN
        client.emit("reset_scan")

        self.assertEqual(state.scan_state, "READY")
        self.assertEqual(state.current_status, "SYSTEM READY")
        self.assertIsNone(state.selected_result)
        self.mock_send.assert_called_with("STATUS:READY")

        client.disconnect()


if __name__ == "__main__":
    unittest.main()

