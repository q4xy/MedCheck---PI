import time
import unittest
from unittest.mock import MagicMock, patch

from server.app import app, socketio, state, esp32


class TestEndToEndSynchronization(unittest.TestCase):
    def setUp(self):
        state.reset_ready()
        self.original_connected = esp32.connected
        esp32.connected = True
        self.esp32_patch = patch.object(esp32, "send_command", MagicMock(return_value=True))
        self.mock_send = self.esp32_patch.start()

    def tearDown(self):
        self.esp32_patch.stop()
        esp32.connected = self.original_connected

    def test_full_exhibition_workflow(self):
        # Two connected clients: Main dashboard and Admin dashboard
        main_client = socketio.test_client(app)
        admin_client = socketio.test_client(app)
        self.assertTrue(main_client.is_connected())
        self.assertTrue(admin_client.is_connected())

        # Clear connection events
        main_client.get_received()
        admin_client.get_received()

        # STEP 1: Main clicks ANALYZE IMAGE
        main_client.emit("analyze_image")

        # ESP32 must receive STATUS:SCANNING
        self.mock_send.assert_called_with("STATUS:SCANNING")
        self.assertEqual(state.scan_state, "SCANNING")

        # Both dashboards receive scanning state
        main_evts = [e for e in main_client.get_received() if e["name"] == "inspection_updated"]
        admin_evts = [e for e in admin_client.get_received() if e["name"] == "inspection_updated"]
        self.assertTrue(len(main_evts) > 0)
        self.assertTrue(len(admin_evts) > 0)
        self.assertEqual(main_evts[-1]["args"][0]["scan_state"], "SCANNING")
        self.assertEqual(admin_evts[-1]["args"][0]["scan_state"], "SCANNING")

        # STEP 2: Admin selects COUNTERFEIT
        admin_client.emit("select_result", {"result": "COUNTERFEIT"})

        # ESP32 receives RESULT:COUNTERFEIT
        self.mock_send.assert_called_with("RESULT:COUNTERFEIT")
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "COUNTERFEIT")

        # Both dashboards receive COUNTERFEIT update
        main_evts = [e for e in main_client.get_received() if e["name"] == "result_selected"]
        admin_evts = [e for e in admin_client.get_received() if e["name"] == "result_selected"]
        self.assertEqual(main_evts[-1]["args"][0]["result"], "COUNTERFEIT")
        self.assertEqual(admin_evts[-1]["args"][0]["result"], "COUNTERFEIT")

        # STEP 3: Main clicks START NEW SCAN
        main_client.emit("reset_scan")
        self.mock_send.assert_called_with("STATUS:READY")
        self.assertEqual(state.scan_state, "READY")
        self.assertIsNone(state.selected_result)

        # STEP 4: Main clicks ANALYZE IMAGE -> Admin selects REAL
        main_client.emit("analyze_image")
        self.mock_send.assert_called_with("STATUS:SCANNING")
        admin_client.emit("select_result", {"result": "REAL"})
        self.mock_send.assert_called_with("RESULT:REAL")
        self.assertEqual(state.selected_result, "REAL")

        # STEP 5: Reset -> ANALYZE IMAGE -> Admin selects NO MEDICINE FOUND
        main_client.emit("reset_scan")
        main_client.emit("analyze_image")
        admin_client.emit("select_result", {"result": "NO MEDICINE FOUND"})
        # When NO MEDICINE FOUND is selected, send STATUS:READY to ESP32
        self.mock_send.assert_called_with("STATUS:READY")
        self.assertEqual(state.selected_result, "NO MEDICINE FOUND")

        main_client.disconnect()
        admin_client.disconnect()


if __name__ == "__main__":
    unittest.main()

