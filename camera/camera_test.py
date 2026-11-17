from __future__ import annotations

import os
import sys
from typing import List

import cv2


def detect_usb_cameras(limit: int = 8) -> List[int]:
    detected: List[int] = []
    for index in range(limit):
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(index, backend)
        if cap is not None and cap.isOpened():
            detected.append(index)
            cap.release()
    return detected


def main() -> None:
    print("Inspecting available camera indices...")
    indices = detect_usb_cameras(10)
    if not indices:
        print("No external USB camera detected. Confirm the webcam is connected and try again.")
        return

    print(f"Detected camera indices: {indices}")
    print("Use the configured USB_CAMERA_INDEX in config.py to select the external USB webcam.")
    print("Do not use the laptop webcam as a fallback.")

    for index in indices:
        print(f"\nTesting index {index}...")
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            print(f"Index {index}: failed to open.")
            continue

        ok, frame = cap.read()
        if not ok or frame is None:
            print(f"Index {index}: opened but no usable frame was returned.")
            cap.release()
            continue

        print(f"Index {index}: preview successful. This is a likely external USB webcam candidate.")
        print("Press Ctrl+C to stop or close the preview window.")
        cv2.imshow(f"MEDCHECK - PI Camera Test {index}", frame)
        key = cv2.waitKey(0)
        cv2.destroyAllWindows()
        cap.release()
        if key in (27, ord("q"), ord("Q")):
            break

    print("\nCamera check complete. Select the correct index in config.py and keep it fixed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCamera test interrupted by user.")
        sys.exit(0)
