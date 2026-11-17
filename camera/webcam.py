from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Lock
from typing import List, Optional

import cv2
import numpy as np


class WebcamManager:
    def __init__(self, device_index: int = 1, width: int = 1280, height: int = 720, storage_dir: Optional[Path] = None) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self.storage_dir = storage_dir or Path("captures")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.capture: Optional[cv2.VideoCapture] = None
        self.lock = Lock()
        self.camera_name = "Camera offline"
        self._last_frame: Optional[np.ndarray] = None

    @staticmethod
    def detect_cameras(limit: int = 4) -> List[int]:
        """Detect openable camera device indices."""
        available: List[int] = []
        for idx in range(limit):
            backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
            cap = cv2.VideoCapture(idx, backend)
            if cap is not None and cap.isOpened():
                available.append(idx)
                cap.release()
            else:
                # Try default backend if DSHOW failed
                cap2 = cv2.VideoCapture(idx)
                if cap2 is not None and cap2.isOpened():
                    available.append(idx)
                    cap2.release()
        return available

    def open(self, device_index: Optional[int] = None) -> bool:
        if device_index is not None:
            self.device_index = device_index

        with self.lock:
            if self.capture is not None and self.capture.isOpened():
                try:
                    self.capture.release()
                except Exception:
                    pass
                self.capture = None

            backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
            cap = cv2.VideoCapture(self.device_index, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.device_index)

            # If preferred device index failed, try index 0 as automatic fallback
            if not cap.isOpened() and self.device_index != 0:
                cap = cv2.VideoCapture(0, backend)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    self.device_index = 0

            if not cap.isOpened():
                self.capture = None
                self.camera_name = f"Camera #{self.device_index} not detected"
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self.capture = cap
            self.camera_name = f"Camera #{self.device_index} ({int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})"
            return True

    def switch_camera(self, new_index: int) -> bool:
        """Switch to a specific camera index."""
        self.device_index = new_index
        return self.open(new_index)

    def is_open(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

    def read_frame(self) -> Optional[np.ndarray]:
        if not self.is_open():
            return None
        with self.lock:
            if self.capture is None:
                return None
            ok, frame = self.capture.read()
            if ok and frame is not None:
                self._last_frame = frame
                return frame
            return self._last_frame

    def capture_current_frame(self, filename: str = "current_scan.jpg") -> Optional[str]:
        """Capture the current frame and save to a single active image file (NO history)."""
        frame = self.read_frame()
        if frame is None:
            # Fallback to generating a synthetic simulation frame if camera is detached
            frame = self.generate_placeholder_frame("SIMULATED SCAN FRAME")

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.storage_dir / filename
        success = cv2.imwrite(str(target_path), frame)
        if success:
            return filename
        return None

    def generate_placeholder_frame(self, message: str = "CAMERA OFFLINE") -> np.ndarray:
        """Generate high-tech HUD placeholder frame when camera is not detected."""
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Deep navy background
        img[:] = (20, 12, 6)

        # Draw tech grid
        for x in range(0, 1280, 40):
            cv2.line(img, (x, 0), (x, 720), (35, 25, 12), 1)
        for y in range(0, 720, 40):
            cv2.line(img, (0, y), (1280, y), (35, 25, 12), 1)

        # Center target
        cx, cy = 640, 360
        cv2.circle(img, (cx, cy), 180, (80, 60, 20), 1)
        cv2.circle(img, (cx, cy), 90, (140, 100, 30), 1)
        cv2.circle(img, (cx, cy), 4, (255, 180, 0), -1)

        # Text banner
        cv2.putText(img, "MEDCHECK-PI OPTICAL SENSOR", (cx - 240, cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 255), 2)
        cv2.putText(img, message, (cx - 160, cy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 180, 255), 2)
        cv2.putText(img, f"DEVICE INDEX: {self.device_index} | BACK SIDE SCAN READY", (cx - 220, cy + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (140, 140, 170), 1)
        return img

    def close(self) -> None:
        with self.lock:
            if self.capture is not None:
                try:
                    self.capture.release()
                except Exception:
                    pass
                self.capture = None
            self.camera_name = "Camera offline"
