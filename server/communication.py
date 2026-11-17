from __future__ import annotations

import logging
import threading
import time
from typing import Optional

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger(__name__)


class ESP32Bridge:
    """Single-owner serial bridge; every command is newline terminated."""

    def __init__(self, serial_port: Optional[str] = "COM4", baud_rate: int = 115200) -> None:
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.serial_handle = None
        self.connected = False
        self.last_error = "ESP32 is not connected."
        self.lock = threading.RLock()

    def connect(self) -> bool:
        with self.lock:
            if self.serial_handle is not None and getattr(self.serial_handle, "is_open", False):
                self.connected = True
                return True
            if not self.serial_port:
                self.last_error = "ESP32 serial port is not configured."
                return False
            if serial is None:
                self.last_error = "pyserial is not installed."
                return False
            try:
                self.serial_handle = serial.Serial(
                    self.serial_port,
                    self.baud_rate,
                    timeout=0.25,
                    write_timeout=0.5,
                )
                self.connected = True
                self.last_error = ""
                time.sleep(2.0)
                self.serial_handle.reset_input_buffer()
                self.send_command("STATUS:READY")
                return True
            except Exception as exc:
                self.last_error = f"Could not connect to {self.serial_port}: {exc}"
                self.connected = False
                self._close_locked()
                logger.warning(self.last_error)
                return False

    def send_command(self, command: str) -> bool:
        with self.lock:
            normalized = command.strip()
            allowed = {
                "STATUS:READY",
                "STATUS:SCANNING",
                "STATUS:ACCEPTED",
                "STATUS:REJECTED",
                "STATUS:MANUAL_REVIEW",
                "STATUS:RED_MARK",
                "CAMERA:CONNECTED",
                "CAMERA:DISCONNECTED",
                "RESULT:REAL",
                "RESULT:COUNTERFEIT",
            }
            if normalized not in allowed:
                self.last_error = f"Rejected unsupported ESP32 command: {normalized[:40]}"
                return False
            if self.serial_handle is None or not getattr(self.serial_handle, "is_open", False):
                self.connected = False
                if not self.connect():
                    return False
            try:
                self.serial_handle.write(f"{normalized}\n".encode("ascii"))
                self.serial_handle.flush()
                self.connected = True
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = f"ESP32 serial write failed: {exc}"
                self.connected = False
                self._close_locked()
                logger.warning(self.last_error)
                return False

    def notify_scanning(self) -> bool:
        return self.send_command("STATUS:SCANNING")

    def notify_accepted(self) -> bool:
        return self.send_command("STATUS:ACCEPTED")

    def notify_rejected(self) -> bool:
        return self.send_command("STATUS:REJECTED")

    def notify_manual_review(self) -> bool:
        return self.send_command("STATUS:MANUAL_REVIEW")

    def notify_red_mark(self) -> bool:
        return self.send_command("STATUS:RED_MARK")

    def notify_camera(self, connected: bool) -> bool:
        return self.send_command("CAMERA:CONNECTED" if connected else "CAMERA:DISCONNECTED")

    def notify_result(self, result: str) -> bool:
        normalized = result.strip().upper()
        if normalized not in {"REAL", "COUNTERFEIT"}:
            return False
        return self.send_command(f"RESULT:{normalized}")

    def notify_ready(self) -> bool:
        return self.send_command("STATUS:READY")

    def _close_locked(self) -> None:
        handle, self.serial_handle = self.serial_handle, None
        if handle is not None:
            try:
                handle.close()
            except Exception as exc:
                logger.debug("Error closing ESP32 serial port: %s", exc)

    def close(self) -> None:
        with self.lock:
            self._close_locked()
            self.connected = False
