from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class WebcamManager:
    """Owns exactly one configured camera device; it never probes or falls back."""

    def __init__(
        self,
        device_index: int = 1,
        width: int = 1280,
        height: int = 720,
        storage_dir: Optional[Path] = None,
    ) -> None:
        self.device_index = int(device_index)
        self.width = width
        self.height = height
        self.storage_dir = Path(storage_dir or "captures")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.capture: Optional[cv2.VideoCapture] = None
        self.lock = threading.RLock()
        self.camera_name = f"USB WEBCAM DISCONNECTED (index {self.device_index})"
        self.last_error = ""
        self._last_frame: Optional[np.ndarray] = None

    @staticmethod
    def _backend() -> int:
        return cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY

    @classmethod
    def detect_cameras(cls, limit: int = 8) -> list[int]:
        """Return openable indices for the standalone discovery tool only."""
        detected: list[int] = []
        for index in range(limit):
            backends = [cls._backend()]
            if cls._backend() != cv2.CAP_ANY:
                backends.append(cv2.CAP_ANY)
            for backend in backends:
                cap = cv2.VideoCapture(index, backend)
                try:
                    if cap.isOpened():
                        detected.append(index)
                        break
                finally:
                    cap.release()
        return detected

    def open(self, device_index: Optional[int] = None) -> bool:
        with self.lock:
            if device_index is not None and int(device_index) != self.device_index:
                self.last_error = "Only the USB_CAMERA_INDEX configured in config.py may be opened."
                return False
            if self.capture is not None and self.capture.isOpened():
                return True

            self._release_locked()
            backends = [self._backend()]
            if self._backend() != cv2.CAP_ANY:
                backends.append(cv2.CAP_ANY)
            cap = None
            for backend in backends:
                candidate = cv2.VideoCapture(self.device_index, backend)
                if candidate.isOpened():
                    cap = candidate
                    break
                candidate.release()
            if cap is None:
                self.last_error = f"Configured USB camera index {self.device_index} could not be opened."
                self.camera_name = f"USB WEBCAM DISCONNECTED (index {self.device_index})"
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            frame = None
            for _ in range(5):
                ok, candidate = cap.read()
                if ok and candidate is not None and candidate.size:
                    frame = candidate
                    break
                time.sleep(0.05)
            if frame is None:
                cap.release()
                self.last_error = f"Configured USB camera index {self.device_index} opened but returned no frame."
                self.camera_name = f"USB WEBCAM DISCONNECTED (index {self.device_index})"
                return False

            self.capture = cap
            self._last_frame = frame
            self.last_error = ""
            self.camera_name = f"USB WEBCAM CONNECTED (index {self.device_index})"
            return True

    def is_open(self) -> bool:
        with self.lock:
            return self.capture is not None and self.capture.isOpened()

    def read_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.capture is None or not self.capture.isOpened():
                return None
            ok, frame = self.capture.read()
            if not ok or frame is None or not frame.size:
                self.last_error = "The configured USB webcam stopped returning frames."
                self._release_locked()
                self.camera_name = f"USB WEBCAM DISCONNECTED (index {self.device_index})"
                return None
            self._last_frame = frame
            return frame.copy()

    def capture_current_frame(self, filename: str) -> Optional[str]:
        if not re.fullmatch(r"scan_[A-Za-z0-9_-]+\.jpg", filename):
            self.last_error = "Invalid capture filename."
            return None
        frame = self.read_frame()
        if frame is None:
            return None
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.storage_dir / filename
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not success or encoded is None:
            self.last_error = "Could not encode the captured webcam frame."
            return None
        try:
            target_path.write_bytes(encoded.tobytes())
        except OSError as exc:
            self.last_error = f"Could not save captured image: {exc}"
            return None
        return filename

    def generate_placeholder_frame(self, message: str = "USB WEBCAM DISCONNECTED") -> np.ndarray:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[:] = (20, 11, 5)
        for x in range(0, frame.shape[1], 48):
            cv2.line(frame, (x, 0), (x, frame.shape[0]), (28, 22, 16), 1)
        for y in range(0, frame.shape[0], 48):
            cv2.line(frame, (0, y), (frame.shape[1], y), (28, 22, 16), 1)
        cv2.rectangle(frame, (285, 155), (995, 565), (90, 75, 35), 2)
        cv2.line(frame, (590, 360), (690, 360), (120, 110, 75), 2)
        cv2.line(frame, (640, 310), (640, 410), (120, 110, 75), 2)
        cv2.putText(frame, message, (325, 455), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (170, 170, 170), 2)
        cv2.putText(frame, f"CONFIGURED DEVICE INDEX {self.device_index}", (430, 505), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 145, 180), 1)
        return frame

    def _release_locked(self) -> None:
        if self.capture is not None:
            self.capture.release()
        self.capture = None

    def close(self) -> None:
        with self.lock:
            self._release_locked()
            self._last_frame = None
            self.camera_name = f"USB WEBCAM DISCONNECTED (index {self.device_index})"
