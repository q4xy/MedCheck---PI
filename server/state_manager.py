from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InspectionState:
    """Thread-safe current inspection state and persisted, real inspection history."""

    def __init__(self, history_path: Optional[Path] = None) -> None:
        self.lock = threading.RLock()
        self.history_path = Path(history_path) if history_path else None
        self.history: List[Dict[str, Any]] = self._load_history()
        self.camera_connected = False
        self.camera_name = "USB WEBCAM DISCONNECTED"
        self.camera_index = 1
        self.esp32_connected = False
        self._reset_current_locked()

    def _load_history(self) -> List[Dict[str, Any]]:
        if self.history_path is None or not self.history_path.is_file():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read inspection history from %s", self.history_path)
            return []
        if not isinstance(data, list):
            logger.error("Inspection history at %s is not a JSON list.", self.history_path)
            return []
        return data

    def _persist_history_locked(self) -> None:
        if self.history_path is None:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.history_path.with_suffix(self.history_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.history_path)

    def _reset_current_locked(self) -> None:
        self.current_status = "SYSTEM READY"
        self.scan_state = "READY"
        self.selected_result: Optional[str] = None
        self.captured_image_url = ""
        self.captured_image_name: Optional[str] = None
        self.inspection_id: Optional[str] = None
        self.classification = "WAITING FOR CAPTURE"
        self.analysis_message = "Capture the rear side of the supported medicine package."
        self.analysis_confidence: Optional[float] = None
        self.analysis_confidence_label = ""
        self.image_accepted = False
        self.red_mark_detected = False
        self.red_mark_observation = ""
        self.visual_observations: List[str] = []
        self.last_update_ts = time.time()
        self.last_error = ""
        self.analysis_running = False

    def reset_current(self) -> None:
        with self.lock:
            if self.inspection_id and self.scan_state in {"CAPTURED", "ANALYZING"}:
                record = next(
                    (item for item in self.history if item.get("inspection_id") == self.inspection_id),
                    None,
                )
                if record is not None:
                    record["classification"] = "CAPTURE SUPERSEDED"
                    record["analysis_message"] = "A newer capture replaced this image before analysis completed."
                    record["operator_decision"] = None
                    record.pop("decision_timestamp", None)
                    self._persist_history_locked()
            self._reset_current_locked()

    def start_capture(self, image_name: str, image_url: str) -> str:
        with self.lock:
            self._reset_current_locked()
            self.inspection_id = uuid.uuid4().hex
            self.captured_image_name = image_name
            self.captured_image_url = image_url
            self.current_status = "IMAGE CAPTURED — ANALYSIS REQUIRED"
            self.scan_state = "CAPTURED"
            self.last_update_ts = time.time()
            self.history.insert(0, {
                "inspection_id": self.inspection_id,
                "image_name": image_name,
                "image_url": image_url,
                "medicine_name": None,
                "classification": "WAITING FOR ANALYSIS",
                "analysis_message": "Image captured; analysis has not run yet.",
                "confidence": None,
                "confidence_label": "",
                "visual_observations": [],
                "red_mark_detected": False,
                "red_mark_observation": "",
                "operator_decision": None,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self._persist_history_locked()
            return self.inspection_id

    def start_analysis(self) -> Optional[tuple[str, str]]:
        with self.lock:
            if not self.captured_image_name or not self.inspection_id or self.analysis_running:
                return None
            self.analysis_running = True
            self.image_accepted = False
            self.selected_result = None
            self.analysis_confidence = None
            self.analysis_confidence_label = ""
            self.classification = "ANALYZING IMAGE"
            self.analysis_message = "Checking image quality, package appearance, reference match, and lower printed area."
            self.current_status = "ANALYZING IMAGE"
            self.scan_state = "ANALYZING"
            self.last_update_ts = time.time()
            record = next(
                (item for item in self.history if item.get("inspection_id") == self.inspection_id),
                None,
            )
            if record is not None:
                record["classification"] = "ANALYZING IMAGE"
                record["analysis_message"] = self.analysis_message
                record["confidence"] = None
                record["confidence_label"] = ""
                record["operator_decision"] = None
                record.pop("decision_timestamp", None)
                self._persist_history_locked()
            return self.captured_image_name, self.inspection_id

    def finish_analysis(
        self,
        result: Dict[str, Any],
        expected_inspection_id: Optional[str] = None,
    ) -> Optional[str]:
        with self.lock:
            if (
                not self.inspection_id
                or not self.captured_image_name
                or (expected_inspection_id and self.inspection_id != expected_inspection_id)
            ):
                return None
            self.analysis_running = False
            self.classification = str(result.get("classification", "NEEDS MANUAL REVIEW"))
            self.analysis_message = str(result.get("message", "Manual review is required."))
            self.analysis_confidence = result.get("confidence")
            self.analysis_confidence_label = str(result.get("confidence_label", ""))
            self.image_accepted = self.classification == "SUPPORTED MEDICINE FOUND"
            self.red_mark_detected = bool(result.get("red_mark_detected", False))
            self.red_mark_observation = str(result.get("red_mark_observation", ""))
            self.visual_observations = list(result.get("visual_observations", []))
            self.current_status = self.classification
            self.scan_state = "ANALYZED"
            self.last_update_ts = time.time()

            existing = next((item for item in self.history if item.get("inspection_id") == self.inspection_id), None)
            record = {
                "inspection_id": self.inspection_id,
                "image_name": self.captured_image_name,
                "image_url": self.captured_image_url,
                "medicine_name": str(result.get("medicine_name")) if self.image_accepted else None,
                "classification": self.classification,
                "analysis_message": self.analysis_message,
                "confidence": self.analysis_confidence,
                "confidence_label": self.analysis_confidence_label,
                "visual_observations": self.visual_observations,
                "red_mark_detected": self.red_mark_detected,
                "red_mark_observation": self.red_mark_observation,
                "operator_decision": None,
                "timestamp": existing.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")) if existing else time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if existing is None:
                self.history.insert(0, record)
            else:
                existing.update(record)
            self._persist_history_locked()
            return self.inspection_id

    def fail_analysis(self, expected_inspection_id: str, message: str) -> bool:
        with self.lock:
            if self.inspection_id != expected_inspection_id:
                return False
            self.analysis_running = False
            self.image_accepted = False
            self.classification = "NEEDS MANUAL REVIEW"
            self.analysis_message = message
            self.analysis_confidence = None
            self.analysis_confidence_label = ""
            self.current_status = "ANALYSIS ERROR — MANUAL REVIEW REQUIRED"
            self.scan_state = "ANALYZED"
            self.last_error = message
            self.last_update_ts = time.time()
            record = next(
                (item for item in self.history if item.get("inspection_id") == expected_inspection_id),
                None,
            )
            if record is not None:
                record["classification"] = self.classification
                record["analysis_message"] = message
                self._persist_history_locked()
            return True

    def mark_storage_error(self, message: str) -> None:
        with self.lock:
            self.analysis_running = False
            self.image_accepted = False
            self.selected_result = None
            self.classification = "NEEDS MANUAL REVIEW"
            self.analysis_message = message
            self.current_status = "HISTORY STORAGE ERROR"
            self.scan_state = "ANALYZED"
            self.last_error = message
            self.last_update_ts = time.time()

    def set_decision(self, result: str) -> bool:
        normalized = result.strip().upper()
        if normalized not in {"REAL", "COUNTERFEIT"}:
            return False
        with self.lock:
            if not self.image_accepted or not self.inspection_id:
                return False
            record = next(
                (item for item in self.history if item.get("inspection_id") == self.inspection_id),
                None,
            )
            if record is None:
                return False
            old_decision = record.get("operator_decision")
            old_timestamp = record.get("decision_timestamp")
            record["operator_decision"] = normalized
            record["decision_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                self._persist_history_locked()
            except OSError:
                if old_decision is None:
                    record.pop("operator_decision", None)
                else:
                    record["operator_decision"] = old_decision
                if old_timestamp is None:
                    record.pop("decision_timestamp", None)
                else:
                    record["decision_timestamp"] = old_timestamp
                raise
            self.selected_result = normalized
            self.current_status = f"OPERATOR SELECTED: {normalized}"
            self.scan_state = "RESULT"
            self.last_update_ts = time.time()
            return True

    def set_hardware_status(
        self,
        camera_connected: bool,
        camera_name: str,
        camera_index: int,
        esp32_connected: bool,
    ) -> None:
        with self.lock:
            self.camera_connected = camera_connected
            self.camera_name = camera_name
            self.camera_index = camera_index
            self.esp32_connected = esp32_connected

    def summary_counts(self) -> Dict[str, int]:
        with self.lock:
            return {
                "counterfeit": sum(item.get("operator_decision") == "COUNTERFEIT" for item in self.history),
                "real": sum(item.get("operator_decision") == "REAL" for item in self.history),
                "no_medicine_found": sum(item.get("classification") == "NO MEDICINE FOUND" for item in self.history),
            }

    def to_dict(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "project_name": "MEDCHECK PI",
                "camera_connected": self.camera_connected,
                "camera_name": self.camera_name,
                "camera_index": self.camera_index,
                "esp32_connected": self.esp32_connected,
                "current_status": self.current_status,
                "scan_state": self.scan_state,
                "selected_result": self.selected_result,
                "captured_image_url": self.captured_image_url,
                "captured_image_name": self.captured_image_name,
                "inspection_id": self.inspection_id,
                "classification": self.classification,
                "analysis_message": self.analysis_message,
                "analysis_confidence": self.analysis_confidence,
                "analysis_confidence_label": self.analysis_confidence_label,
                "image_accepted": self.image_accepted,
                "red_mark_detected": self.red_mark_detected,
                "red_mark_observation": self.red_mark_observation,
                "visual_observations": list(self.visual_observations),
                "analysis_running": self.analysis_running,
                "history": [dict(item) for item in self.history[:20]],
                "summary_counts": self.summary_counts(),
                "last_update_ts": self.last_update_ts,
                "last_error": self.last_error,
            }
