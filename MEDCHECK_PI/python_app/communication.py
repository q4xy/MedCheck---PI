"""
communication.py
Manages PySerial communication with the Arduino UNO R4 WiFi,
handles acknowledgements, auto-reconnects, and prevents duplicate events.
"""

import time
from typing import Optional
import serial
import serial.tools.list_ports


class ArduinoCommunicator:
    VALID_TOKENS = {
        "MEDICINE_NOT_ALIGNED",
        "MEDICINE_ADJUST",
        "MEDICINE_ALIGNED",
        "INSPECTION_RESULT_REAL",
        "INSPECTION_RESULT_COUNTERFEIT",
    }

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.last_sent_alignment: Optional[str] = None
        self.alignment_confirmed_sent = False
        self.uno_state = "UNKNOWN"

    def _detect_uno_port(self) -> Optional[str]:
        if self.port:
            return self.port

        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            # Arduino UNO R4 WiFi USB VID:PID = 2341:1002
            if "2341:1002" in hwid or "arduino" in desc or "uno r4" in desc:
                return p.device

        if ports:
            return ports[0].device
        return None

    def connect(self) -> bool:
        self.close()
        target_port = self._detect_uno_port()
        if not target_port:
            print("[SERIAL WARNING] No Arduino UNO R4 serial port detected.")
            return False

        try:
            ser = serial.Serial(target_port, self.baudrate, timeout=0.15)
            time.sleep(1.5)  # Allow UNO R4 USB CDC port to stabilize
            ser.reset_input_buffer()
            self.ser = ser
            self.port = target_port

            if self.ping():
                print(f"[SERIAL] Connected to Arduino UNO R4 on {target_port} @ {self.baudrate} baud.")
                return True

            print(f"[SERIAL] Opened {target_port} (waiting for UNO R4 response).")
            return True
        except Exception as exc:
            print(f"[SERIAL ERROR] Could not open {target_port}: {exc}")
            self.ser = None
            return False

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def reset_cycle(self) -> None:
        """Reset duplicate-event tracking when a new placement cycle starts."""
        self.last_sent_alignment = None
        self.alignment_confirmed_sent = False

    def _send_and_wait_ack(self, message: str, expected_prefix: str = "ACK:") -> bool:
        if not self.is_connected():
            return False

        try:
            assert self.ser is not None
            self.ser.write((message + "\n").encode("utf-8"))
            self.ser.flush()

            deadline = time.time() + 0.25
            while time.time() < deadline:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    self._handle_async_line(line)
                    if line.startswith(expected_prefix):
                        return True
                time.sleep(0.005)
        except Exception as exc:
            print(f"[SERIAL WRITE ERROR] {exc}")
            self.close()
        return False

    def _handle_async_line(self, line: str) -> None:
        if line == "EVENT:ENTER_PLACEMENT":
            self.uno_state = "PLACEMENT"
            self.reset_cycle()
            print("[UNO -> PY] User opened SCAN placement screen.")
        elif line == "EVENT:EXIT_PLACEMENT":
            self.uno_state = "HOME"
            self.reset_cycle()
        elif line == "EVENT:INSPECTION_STARTED":
            self.uno_state = "SCANNING"
            print("[UNO -> PY] Inspection workflow started at 0%.")
        elif line == "EVENT:INSPECTION_COMPLETE":
            self.uno_state = "RESULT"
            print("[UNO -> PY] Inspection completed (100%).")
        elif line.startswith("STATE:"):
            self.uno_state = line.split(":", 1)[1]

    def poll_incoming(self) -> None:
        """Read any unsolicited status/event lines from UNO R4."""
        if not self.is_connected():
            return
        try:
            assert self.ser is not None
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    self._handle_async_line(line)
        except Exception:
            self.close()

    def ping(self) -> bool:
        return self._send_and_wait_ack("PING", "ACK:PONG")

    def query_state(self) -> str:
        self._send_and_wait_ack("GET_STATE", "STATE:")
        return self.uno_state

    def send_alignment_status(self, status: str) -> bool:
        """
        Send alignment state to UNO R4 without spamming duplicates.
        Once MEDICINE_ALIGNED is sent and acknowledged, lock it for this cycle.
        """
        if status not in self.VALID_TOKENS:
            return False

        if self.alignment_confirmed_sent:
            return True

        if status == self.last_sent_alignment:
            return True

        ack_ok = self._send_and_wait_ack(status, f"ACK:{status}")
        if ack_ok:
            self.last_sent_alignment = status
            if status == "MEDICINE_ALIGNED":
                self.alignment_confirmed_sent = True
        return ack_ok

    def send_result(self, verdict: str) -> bool:
        """Optional Python-side result trigger using the exact required protocol."""
        token = (
            "INSPECTION_RESULT_REAL"
            if verdict.upper() == "REAL"
            else "INSPECTION_RESULT_COUNTERFEIT"
        )
        return self._send_and_wait_ack(token, f"ACK:{token}")

    def close(self) -> None:
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None