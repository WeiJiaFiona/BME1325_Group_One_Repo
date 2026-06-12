from __future__ import annotations

from typing import Any, Dict
import json
import urllib.error
import urllib.request

from app_core.integration.fullview_config import FullViewConfig


class FullViewClient:
    def __init__(self, config: FullViewConfig) -> None:
        self.config = config
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get_snapshot(self) -> Dict[str, Any]:
        return self._request_json("GET", "/api/hospital/snapshot")

    def ensure_patient(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_json("POST", "/api/hospital/patients/ensure", payload)

    def move_patient(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_json("POST", "/api/hospital/events/move", payload)

    def _request_json(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.config.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with self._opener.open(req, timeout=self.config.timeout_sec) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"message": body or str(exc)}
            payload.setdefault("accepted", False)
            payload.setdefault("reasonCode", f"HTTP_{exc.code}")
            return payload


def find_patient_in_snapshot(snapshot: Dict[str, Any], *, patient_id: str | None, external_case_id: str | None, source: str) -> Dict[str, Any] | None:
    for patient in snapshot.get("patients", []) or []:
        patient_source = str(patient.get("source") or "").strip().lower()
        if patient_id and str(patient.get("patientId") or patient.get("patient_id") or "").strip() == patient_id:
            return patient
        if source and patient_source != str(source).strip().lower():
            continue
        if patient_id and str(patient.get("externalPatientId") or patient.get("external_patient_id") or "").strip() == patient_id:
            return patient
        if external_case_id and str(patient.get("externalCaseId") or patient.get("external_case_id") or "").strip() == external_case_id:
            return patient
    return None
