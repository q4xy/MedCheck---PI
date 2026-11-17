from __future__ import annotations

import os
import sys
from typing import List

import cv2


def detect_usb_cameras(limit: int = 8) -> List[int]:
    detected: List[int] = []
    for index in range(limit):
        backends = [cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY]
        if os.name == "nt":
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
        backends = [cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY]
        if os.name == "nt":
            backends.append(cv2.CAP_ANY)
        cap = None
        for backend in backends:
            candidate = cv2.VideoCapture(index, backend)
            if candidate.isOpened():
                cap = candidate
                break
            candidate.release()
        if cap is None:
            print(f"Index {index}: failed to open.")
            continue

        print(f"Previewing index {index}. Press S to select it, N for next, Q to quit.")
        selected = False
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok or frame is None:
                print(f"Index {index}: no frame received.")
                break
            cv2.putText(frame, f"CAMERA INDEX {index} - S SELECT / N NEXT / Q QUIT", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 230, 120), 2)
            cv2.imshow(f"MEDCHECK PI Camera Discovery - {index}", frame)
            key = cv2.waitKey(20) & 0xFF
            if key in (ord("s"), ord("S")):
                selected = True
                break
            if key in (ord("n"), ord("N"), ord("q"), ord("Q"), 27):
                break
        cv2.destroyAllWindows()
        cap.release()
        if selected:
            print(f"Selected candidate index {index}. Configure USB_CAMERA_INDEX = {index} in config.py.")
            break
        if key in (ord("q"), ord("Q"), 27):
            break

    print("\nCamera check complete. Select the correct index in config.py and keep it fixed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCamera test interrupted by user.")
        sys.exit(0)
