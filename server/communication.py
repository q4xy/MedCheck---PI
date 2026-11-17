from __future__ import annotations

import logging
from threading import Lock
from typing import Optional

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("esp32_bridge")


class ESP32Bridge:
    def __init__(self, serial_port: Optional[str] = "COM4", baud_rate: int = 115200) -> None:
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.serial_handle: Optional[serial.Serial] = None
        self.connected = False
        self.last_error = "Serial not connected."
        self.lock = Lock()

    def connect(self) -> bool:
        """Attempt to open the configured serial COM port safely without blocking."""
        with self.lock:
            if not self.serial_port:
                self.last_error = "Serial port not configured."
                self.connected = False
                return False

            if serial is None:
                self.last_error = "pyserial library not installed."
                self.connected = False
                return False

            # If already open, close first to ensure fresh state
            if self.serial_handle is not None:
                try:
                    self.serial_handle.close()
                except Exception:
                    pass
                self.serial_handle = None

            try:
                self.serial_handle = serial.Serial(
                    self.serial_port,
                    self.baud_rate,
                    timeout=0.5,
                    write_timeout=0.5,
                )
                self.connected = True
                self.last_error = "Connected to ESP32."
                # Initial ready message
                self._write_raw("STATUS:READY\n")
                return True
            except Exception as exc:
                self.connected = False
                self.serial_handle = None
                self.last_error = f"Cannot open {self.serial_port}: {exc}"
                return False

    def _write_raw(self, line: str) -> bool:
        if self.serial_handle is None:
            return False
        try:
            self.serial_handle.write(line.encode("utf-8"))
            self.serial_handle.flush()
            return True
        except Exception as exc:
            self.connected = False
            self.last_error = f"Write failed: {exc}"
            try:
                if self.serial_handle:
                    self.serial_handle.close()
            except Exception:
                pass
            self.serial_handle = None
            return False

    def send_command(self, command: str) -> bool:
        """Send a formatted newline-terminated command string to ESP32."""
        with self.lock:
            cleaned = command.strip()
            if not cleaned:
                return False

            # If currently disconnected, attempt one auto-reconnect
            if not self.connected or self.serial_handle is None:
                # Do not block app if reconnect fails
                try:
                    if self.serial_port and serial is not None:
                        self.serial_handle = serial.Serial(
                            self.serial_port,
                            self.baud_rate,
                            timeout=0.5,
                            write_timeout=0.5,
                        )
                        self.connected = True
                        self.last_error = "Reconnected"
                except Exception:
                    self.connected = False
                    return False

            success = self._write_raw(f"{cleaned}\n")
            return success

    def notify_scanning(self) -> bool:
        """STATUS:SCANNING command when AI analyzing begins."""
        return self.send_command("STATUS:SCANNING")

    def notify_real(self) -> bool:
        """RESULT:REAL command when REAL is selected."""
        return self.send_command("RESULT:REAL")

    def notify_counterfeit(self) -> bool:
        """RESULT:COUNTERFEIT command when COUNTERFEIT is selected."""
        return self.send_command("RESULT:COUNTERFEIT")

    def notify_ready(self) -> bool:
        """STATUS:READY command when NO MEDICINE FOUND or reset."""
        return self.send_command("STATUS:READY")

    def close(self) -> None:
        with self.lock:
            if self.serial_handle is not None:
                try:
                    self.serial_handle.close()
                except Exception:
                    pass
            self.serial_handle = None
            self.connected = False
