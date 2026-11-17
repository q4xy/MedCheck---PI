import unittest
from pathlib import Path

import config
from server.app import app
from server.state_manager import InspectionState


class MedCheckMasterSmokeTests(unittest.TestCase):
    def test_config_defaults(self):
        self.assertEqual(config.SERIAL_PORT, "COM4")
        self.assertEqual(config.SERIAL_BAUD_RATE, 115200)
        self.assertEqual(config.USB_CAMERA_INDEX, 1)
        self.assertEqual(config.FLASK_PORT, 8000)
        self.assertEqual(config.FLASK_HOST, "0.0.0.0")

    def test_routes_and_dashboards(self):
        client = app.test_client()

        # 1. Main Dashboard: accessible at / and /display
        res_main = client.get("/")
        self.assertEqual(res_main.status_code, 200)
        self.assertIn(b"SMART MEDICINE AUTHENTICITY SCREENING", res_main.data)
        self.assertIn(b"MEDCHECK-PI", res_main.data)
        self.assertIn(b"ANALYZE IMAGE", res_main.data)
        self.assertIn(b"START NEW SCAN", res_main.data)

        # Confirm strictly no search or history in main dashboard
        self.assertNotIn(b"Search history", res_main.data)
        self.assertNotIn(b"Scan history", res_main.data)
        self.assertNotIn(b"Image history", res_main.data)

        # 2. Admin Dashboard: accessible at /admin
        res_admin = client.get("/admin")
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b"ADMIN CONTROL PANEL", res_admin.data)
        self.assertIn(b"COUNTERFEIT", res_admin.data)
        self.assertIn(b"REAL", res_admin.data)
        self.assertIn(b"NO MEDICINE FOUND", res_admin.data)

        # Confirm strictly no ANALYZE IMAGE or history on admin dashboard
        self.assertNotIn(b"ANALYZE IMAGE", res_admin.data)
        self.assertNotIn(b"Search history", res_admin.data)
        self.assertNotIn(b"Scan history", res_admin.data)

        # 3. /control redirects to /admin
        res_control = client.get("/control")
        self.assertEqual(res_control.status_code, 302)
        self.assertTrue(res_control.headers["Location"].endswith("/admin"))

    def test_state_manager_no_history(self):
        state = InspectionState()
        payload = state.to_dict()

        # Verify no history arrays exist
        self.assertNotIn("history", payload)
        self.assertNotIn("search_history", payload)
        self.assertNotIn("image_history", payload)

        # Initial state is READY
        self.assertEqual(state.scan_state, "READY")
        self.assertEqual(state.current_status, "SYSTEM READY")
        self.assertIsNone(state.selected_result)

    def test_state_flow_and_decisions(self):
        state = InspectionState()

        # 1. Start scanning
        state.start_scanning()
        self.assertEqual(state.scan_state, "SCANNING")
        self.assertEqual(state.current_status, "SCANNING")

        # 2. Admin selects COUNTERFEIT
        state.set_result("COUNTERFEIT")
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "COUNTERFEIT")
        self.assertEqual(state.current_status, "RESULT: COUNTERFEIT")

        # 3. Admin selects REAL
        state.set_result("REAL")
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "REAL")
        self.assertEqual(state.current_status, "RESULT: REAL")

        # 4. Admin selects NO MEDICINE FOUND
        state.set_result("NO MEDICINE FOUND")
        self.assertEqual(state.scan_state, "RESULT")
        self.assertEqual(state.selected_result, "NO MEDICINE FOUND")
        self.assertEqual(state.current_status, "RESULT: NO MEDICINE FOUND")

        # 5. Reset to ready
        state.reset_ready()
        self.assertEqual(state.scan_state, "READY")
        self.assertEqual(state.current_status, "SYSTEM READY")
        self.assertIsNone(state.selected_result)

    def test_api_status(self):
        client = app.test_client()
        res = client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("lan_ip", data)
        self.assertIn("port", data)
        self.assertIn("current_status", data)
        self.assertIn("scan_state", data)


if __name__ == "__main__":
    unittest.main()
