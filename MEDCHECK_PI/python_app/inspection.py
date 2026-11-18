"""
inspection.py
Manages the Python-side inspection state, snapshot capture when a medicine
packet is aligned, and clean overlay rendering for the live camera window.
"""

import os
from datetime import datetime
from typing import Optional
import cv2
import numpy as np
from detection import DetectionResult


class InspectionManager:
    def __init__(self, captures_dir: str = "captures") -> None:
        self.captures_dir = captures_dir
        os.makedirs(self.captures_dir, exist_ok=True)
        self.captured_for_current_cycle = False
        self.last_capture_path: Optional[str] = None

    def reset_cycle(self) -> None:
        self.captured_for_current_cycle = False

    def save_aligned_capture(self, frame: np.ndarray) -> Optional[str]:
        """Save one clean image of the aligned medicine back-side packet."""
        if self.captured_for_current_cycle:
            return self.last_capture_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"medicine_aligned_{timestamp}.jpg"
        filepath = os.path.join(self.captures_dir, filename)

        if cv2.imwrite(filepath, frame):
            self.captured_for_current_cycle = True
            self.last_capture_path = filepath
            print(f"[CAPTURE] Saved aligned medicine frame -> {filepath}")
            return filepath
        return None

    @staticmethod
    def render_overlay(
        frame: np.ndarray,
        det: DetectionResult,
        uno_state: str,
        serial_connected: bool,
    ) -> np.ndarray:
        """Draw alignment frame, bounding box, stability bar, and status banner."""
        canvas = frame.copy()
        fh, fw = canvas.shape[:2]
        rx1, ry1, rx2, ry2 = det.roi

        if det.status == "MEDICINE_ALIGNED":
            roi_color = (0, 230, 80)      # Bright Green
        elif det.detected:
            roi_color = (0, 190, 255)    # Amber / Yellow
        else:
            roi_color = (255, 220, 0)    # Cyan

        # Central Alignment Guide Rectangle
        cv2.rectangle(canvas, (rx1, ry1), (rx2, ry2), roi_color, 2)

        # Corner Brackets
        blen = 24
        t = 4
        cv2.line(canvas, (rx1, ry1), (rx1 + blen, ry1), roi_color, t)
        cv2.line(canvas, (rx1, ry1), (rx1, ry1 + blen), roi_color, t)
        cv2.line(canvas, (rx2, ry1), (rx2 - blen, ry1), roi_color, t)
        cv2.line(canvas, (rx2, ry1), (rx2, ry1 + blen), roi_color, t)
        cv2.line(canvas, (rx1, ry2), (rx1 + blen, ry2), roi_color, t)
        cv2.line(canvas, (rx1, ry2), (rx1, ry2 - blen), roi_color, t)
        cv2.line(canvas, (rx2, ry2), (rx2 - blen, ry2), roi_color, t)
        cv2.line(canvas, (rx2, ry2), (rx2, ry2 - blen), roi_color, t)

        # Detected Object Bounding Box
        if det.bbox is not None:
            bx, by, bw, bh = det.bbox
            box_col = (0, 255, 100) if det.inside_roi else (0, 140, 255)
            cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), box_col, 2)

        # Top Status Bar
        cv2.rectangle(canvas, (0, 0), (fw, 44), (15, 15, 15), -1)
        cv2.putText(
            canvas,
            det.label,
            (16, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            roi_color,
            2,
            cv2.LINE_AA,
        )

        # Stability Progress Bar (Top-Right)
        bar_x1, bar_y1, bar_x2, bar_y2 = fw - 170, 13, fw - 16, 31
        cv2.rectangle(canvas, (bar_x1, bar_y1), (bar_x2, bar_y2), (140, 140, 140), 1)
        fill_w = int((bar_x2 - bar_x1 - 2) * det.stability_progress)
        if fill_w > 0:
            cv2.rectangle(
                canvas,
                (bar_x1 + 1, bar_y1 + 1),
                (bar_x1 + 1 + fill_w, bar_y2 - 1),
                roi_color,
                -1,
            )

        # Bottom Telemetry Strip
        cv2.rectangle(canvas, (0, fh - 32), (fw, fh), (15, 15, 15), -1)
        link_txt = f"UNO R4: {uno_state}" if serial_connected else "UNO R4: SEARCHING PORT..."
        link_col = (0, 230, 80) if serial_connected else (0, 165, 255)
        cv2.putText(
            canvas,
            f"CAM 1 ACTIVE  |  {link_txt}  |  [Q] QUIT  [R] RESET",
            (12, fh - 11),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            link_col,
            1,
            cv2.LINE_AA,
        )

        return canvas