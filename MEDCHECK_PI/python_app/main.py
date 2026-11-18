"""
main.py
Single entry point for MEDCHECK PI USB-Camera Presence & Alignment System.
Run with: python main.py
"""

import sys
import time
import cv2
import numpy as np

from camera import USBCamera
from detection import MedicinePlacementDetector
from communication import ArduinoCommunicator
from inspection import InspectionManager


WINDOW_NAME = "MEDCHECK PI - Optical Placement Monitor (USB Cam 1)"


def create_camera_error_frame(width: int = 640, height: int = 480) -> np.ndarray:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        img,
        "USB CAMERA (INDEX 1) UNAVAILABLE",
        (55, height // 2 - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 120, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Connect external USB camera and retrying automatically...",
        (68, height // 2 + 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )
    return img


def main() -> None:
    print("==========================================")
    print(" MEDCHECK PI - USB CAMERA ALIGNMENT ENGINE")
    print("==========================================")

    camera = USBCamera(width=640, height=480)
    detector = MedicinePlacementDetector(required_stable_frames=12)
    comm = ArduinoCommunicator(baudrate=115200)
    inspector = InspectionManager(captures_dir="captures")

    comm.connect()
    camera.open()

    last_cam_retry = time.time()
    last_serial_retry = time.time()
    last_state_poll = time.time()
    prev_uno_state = "UNKNOWN"

    try:
        while True:
            now = time.time()

            # 1. Maintain USB Serial connection to UNO R4
            if not comm.is_connected():
                if now - last_serial_retry >= 2.0:
                    last_serial_retry = now
                    comm.connect()
            else:
                comm.poll_incoming()
                if now - last_state_poll >= 1.0:
                    last_state_poll = now
                    comm.query_state()

            # Reset alignment cycle whenever UNO enters PLACEMENT mode
            if comm.uno_state == "PLACEMENT" and prev_uno_state != "PLACEMENT":
                detector.reset()
                comm.reset_cycle()
                inspector.reset_cycle()
            prev_uno_state = comm.uno_state

            # 2. Ensure External USB Camera (index 1) is open
            if not camera.is_open:
                if now - last_cam_retry >= 2.0:
                    last_cam_retry = now
                    camera.open()

                err_frame = create_camera_error_frame()
                cv2.imshow(WINDOW_NAME, err_frame)
                key = cv2.waitKey(30) & 0xFF
                if key == ord("q"):
                    break
                continue

            # 3. Capture live frame from USB Camera 1
            ok, frame = camera.read_frame()
            if not ok or frame is None:
                print("[CAMERA WARNING] Frame read failed; reinitializing camera index 1...")
                camera.release()
                continue

            # 4. Run presence, ROI alignment, and temporal stability analysis
            det = detector.analyze(frame)

            # 5. Communicate alignment status to Arduino UNO R4 when on placement screen
            if comm.is_connected():
                if det.status == "MEDICINE_ALIGNED":
                    inspector.save_aligned_capture(frame)
                    if comm.uno_state in ("PLACEMENT", "UNKNOWN"):
                        comm.send_alignment_status("MEDICINE_ALIGNED")
                elif det.status == "MEDICINE_ADJUST":
                    if comm.uno_state == "PLACEMENT":
                        comm.send_alignment_status("MEDICINE_ADJUST")
                else:
                    if comm.uno_state == "PLACEMENT":
                        comm.send_alignment_status("MEDICINE_NOT_ALIGNED")

            # 6. Display live annotated feed
            display_frame = InspectionManager.render_overlay(
                frame=frame,
                det=det,
                uno_state=comm.uno_state,
                serial_connected=comm.is_connected(),
            )
            cv2.imshow(WINDOW_NAME, display_frame)

            key = cv2.waitKey(15) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                detector.reset()
                comm.reset_cycle()
                inspector.reset_cycle()
                print("[SYSTEM] Alignment state manually reset.")

    except KeyboardInterrupt:
        print("\n[SYSTEM] Shutting down cleanly...")
    finally:
        camera.release()
        comm.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()