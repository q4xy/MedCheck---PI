from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

PRESET_MEDICINES: List[Dict[str, str]] = [
    {
        "id": "dolo650",
        "name": "DOLO 650",
        "generic": "Paracetamol Tablets IP 650mg",
        "manufacturer": "Micro Labs Limited",
        "batch_no": "DL-24891A",
        "mfg_date": "03/2026",
        "exp_date": "02/2028",
        "composition": "Paracetamol IP 650 mg, Excipients q.s.",
        "packaging": "Alu-Alu Blister Strip (15 Tablets)",
        "security_features": "Micro-text embossing, Tamper-evident seal, 2D DataMatrix",
        "dosage": "As directed by physician",
    },
    {
        "id": "augmentin625",
        "name": "AUGMENTIN 625 DUO",
        "generic": "Amoxicillin and Potassium Clavulanate Tablets IP",
        "manufacturer": "GlaxoSmithKline Pharmaceuticals Ltd",
        "batch_no": "AG-9902X",
        "mfg_date": "01/2026",
        "exp_date": "12/2027",
        "composition": "Amoxicillin Trihydrate 500mg + Potassium Clavulanate 125mg",
        "packaging": "Moisture-barrier Alu-Alu Strip (10 Tablets)",
        "security_features": "GSK Watermark, Braille script, Hologram foil",
        "dosage": "Oral prescription antibiotic",
    },
    {
        "id": "azithral500",
        "name": "AZITHRAL 500",
        "generic": "Azithromycin Tablets IP 500mg",
        "manufacturer": "Alembic Pharmaceuticals Ltd",
        "batch_no": "AZ-4410B",
        "mfg_date": "02/2026",
        "exp_date": "01/2028",
        "composition": "Azithromycin Dihydrate equivalent to Azithromycin 500 mg",
        "packaging": "Blister Pack PVC/PVDC (5 Tablets)",
        "security_features": "Alembic Security Guilloche, QR Verification, Batch laser etching",
        "dosage": "1 tablet daily or as advised",
    },
    {
        "id": "pan40",
        "name": "PAN 40",
        "generic": "Pantoprazole Gastro-resistant Tablets IP",
        "manufacturer": "Alkem Laboratories Ltd",
        "batch_no": "PN-7812C",
        "mfg_date": "04/2026",
        "exp_date": "03/2028",
        "composition": "Pantoprazole Sodium Sesquihydrate IP 40mg",
        "packaging": "Silver Alu-Alu Blister (15 Tablets)",
        "security_features": "Alkem Holographic strip, Heat-seal verification, Micro-lettering",
        "dosage": "Once daily before breakfast",
    },
    {
        "id": "allegra120",
        "name": "ALLEGRA 120mg",
        "generic": "Fexofenadine Hydrochloride Tablets IP",
        "manufacturer": "Sanofi Healthcare India Pvt Ltd",
        "batch_no": "AL-3105D",
        "mfg_date": "05/2026",
        "exp_date": "04/2028",
        "composition": "Fexofenadine HCl IP 120mg",
        "packaging": "Clear Blister Strip (10 Tablets)",
        "security_features": "Sanofi Anti-counterfeit 3D Tag, Registered Font Type, Microprint",
        "dosage": "One tablet daily",
    },
]


class InspectionState:
    """Central state manager for MEDCHECK-PI.
    
    Holds real-time verification state shared synchronously across
    Main Dashboard, Admin Dashboard, and ESP32 hardware bridge.
    Strictly contains NO history, NO gallery, and NO search mechanisms.
    """

    def __init__(self) -> None:
        self.camera_connected: bool = False
        self.camera_name: str = "Camera offline"
        self.camera_index: int = 1
        self.esp32_connected: bool = False
        self.current_status: str = "SYSTEM READY"
        self.scan_state: str = "READY"  # "READY" | "SCANNING" | "RESULT"
        self.selected_result: Optional[str] = None  # "REAL" | "COUNTERFEIT" | "NO MEDICINE FOUND" | None
        self.captured_image_url: str = ""
        self.last_update_ts: float = time.time()
        self.last_error: str = "System initialized"
        self.current_medicine_index: int = 0
        self.current_medicine: Dict[str, str] = PRESET_MEDICINES[0]

    def set_medicine_index(self, index: int) -> Dict[str, str]:
        if 0 <= index < len(PRESET_MEDICINES):
            self.current_medicine_index = index
            self.current_medicine = PRESET_MEDICINES[index]
        return self.current_medicine

    def set_medicine_by_id(self, med_id: str) -> Dict[str, str]:
        for idx, med in enumerate(PRESET_MEDICINES):
            if med["id"] == med_id:
                self.current_medicine_index = idx
                self.current_medicine = med
                return med
        return self.current_medicine

    def start_scanning(self, image_url: str = "/captures/current_scan.jpg") -> None:
        self.scan_state = "SCANNING"
        self.current_status = "SCANNING"
        self.selected_result = None
        self.captured_image_url = f"{image_url}?t={int(time.time() * 1000)}"
        self.last_update_ts = time.time()

    def set_result(self, result: str) -> None:
        normalized = result.strip().upper()
        if normalized not in {"REAL", "COUNTERFEIT", "NO MEDICINE FOUND"}:
            normalized = "NO MEDICINE FOUND"
        self.scan_state = "RESULT"
        self.selected_result = normalized
        self.current_status = f"RESULT: {normalized}"
        self.last_update_ts = time.time()

    def reset_ready(self) -> None:
        self.scan_state = "READY"
        self.current_status = "SYSTEM READY"
        self.selected_result = None
        self.last_update_ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_connected": self.camera_connected,
            "camera_name": self.camera_name,
            "camera_index": self.camera_index,
            "esp32_connected": self.esp32_connected,
            "current_status": self.current_status,
            "scan_state": self.scan_state,
            "selected_result": self.selected_result,
            "captured_image_url": self.captured_image_url,
            "last_update_ts": self.last_update_ts,
            "last_error": self.last_error,
            "current_medicine": self.current_medicine,
            "preset_medicines": PRESET_MEDICINES,
        }
