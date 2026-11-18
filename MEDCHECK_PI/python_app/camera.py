"""
camera.py
Handles external USB camera initialization (strictly index 1),
frame capture, error recovery, and clean release.
"""

import cv2
import numpy as np
from typing import Optional, Tuple


class USBCamera:
    CAMERA_INDEX = 1  # Mandatory external USB camera index (no fallback to 0)

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.width = width
        self.height = height
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_open = False

    def open(self) -> bool:
        """Open external USB camera index 1 only."""
        self.release()
        try:
            # Prefer DirectShow on Windows for fast USB camera startup, fallback to default backend
            cap = cv2.VideoCapture(self.CAMERA_INDEX, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(self.CAMERA_INDEX)

            if not cap.isOpened():
                print(f"[CAMERA ERROR] External USB camera (index {self.CAMERA_INDEX}) is unavailable.")
                self.cap = None
                self.is_open = False
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"[CAMERA ERROR] Opened index {self.CAMERA_INDEX} but failed to read initial frame.")
                cap.release()
                self.cap = None
                self.is_open = False
                return False

            self.cap = cap
            self.is_open = True
            print(f"[CAMERA] External USB camera (index {self.CAMERA_INDEX}) connected ({frame.shape[1]}x{frame.shape[0]}).")
            return True

        except Exception as exc:
            print(f"[CAMERA EXCEPTION] {exc}")
            self.cap = None
            self.is_open = False
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Capture a single BGR frame safely."""
        if not self.is_open or self.cap is None:
            return False, None

        try:
            ret, frame = self.cap.read()
            if not ret or frame is None or frame.size == 0:
                self.is_open = False
                return False, None
            return True, frame
        except Exception as exc:
            print(f"[CAMERA READ ERROR] {exc}")
            self.is_open = False
            return False, None

    def release(self) -> None:
        """Safely release camera hardware."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.is_open = False