from __future__ import annotations

import json
import math
import random
import uuid
from pathlib import Path
from typing import Any

import yaml

from .icu_unit import ICUUnit
from .schemas import TransferRequest, TransferResponse
from .ward_unit import WardUnit


_CURRENT_FILE = Path(__file__).resolve()
_BACKEND_SERVER_DIR = _CURRENT_FILE.parents[1]
_REPO_ROOT = _CURRENT_FILE.parents[3]
DEFAULT_PROFILE_PATH = _REPO_ROOT / "configs" / "downstream_units_profiles.yaml"


def load_downstream_profiles(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path or DEFAULT_PROFILE_PATH)
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(payload.get("downstream_units", {}) or {})


def resolve_downstream_profile(profile_name: str | None, config_path: str | Path | None = None) -> dict[str, Any]:
    profiles = load_downstream_profiles(config_path)
    if not profile_name:
        return {}
    return dict(profiles.get(str(profile_name), {}) or {})


class TransferBroker:
    def __init__(
        self,
        *,
        profile_name: str,
        icu_capacity: int,
        ward_capacity: int,
        transfer_turnaround_minutes: int,
        boarding_timeout_minutes: int,
        minutes_per_step: int = 1,
        request_log_path: str | Path | None = None,
        retry_after_seconds: int | None = None,
        icu_acceptance_probability: float | None = None,
        random_seed: int | None = None,
    ):
        self.profile_name = str(profile_name or "default")
        self.minutes_per_step = max(1, int(minutes_per_step or 1))
        self.icu_unit = ICUUnit(int(icu_capacity or 0))
        self.ward_unit = WardUnit(int(ward_capacity or 0))
        self.transfer_turnaround_minutes = max(0, int(transfer_turnaround_minutes or 0))
        self.boarding_timeout_minutes = max(0, int(boarding_timeout_minutes or 0))
        self.retry_after_seconds = int(
            retry_after_seconds
            if retry_after_seconds is not None
            else max(60, self.transfer_turnaround_minutes * 60 or 300)
        )
        self.accepted_transfer_count = 0
        self.pending_transfer_count = 0
        self.transfer_request_count = 0
        self.icu_probability_gate_pending_count = 0
        self._transfer_sequence = 0
        self._attempts_by_transfer_id: dict[str, int] = {}
        self.icu_acceptance_probability = self._normalize_probability(icu_acceptance_probability)
        self._rng = random.Random(random_seed)
        self.request_log_path = Path(request_log_path) if request_log_path else None
        if self.request_log_path:
            self.request_log_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_profile_name(
        cls,
        profile_name: str | None,
        *,
        minutes_per_step: int = 1,
        request_log_path: str | Path | None = None,
        profile_overrides: dict[str, Any] | None = None,
        config_path: str | Path | None = None,
    ) -> "TransferBroker":
        profile = resolve_downstream_profile(profile_name, config_path=config_path)
        profile.update(dict(profile_overrides or {}))
        return cls(
            profile_name=str(profile_name or "default"),
            icu_capacity=int(profile.get("icu_capacity", 0) or 0),
            ward_capacity=int(profile.get("ward_capacity", 0) or 0),
            transfer_turnaround_minutes=int(profile.get("transfer_turnaround_minutes", 30) or 30),
            boarding_timeout_minutes=int(profile.get("boarding_timeout_minutes", 240) or 240),
            minutes_per_step=minutes_per_step,
            request_log_path=request_log_path,
            retry_after_seconds=profile.get("retry_after_seconds"),
            icu_acceptance_probability=profile.get("icu_acceptance_probability"),
            random_seed=profile.get("random_seed"),
        )

    @staticmethod
    def _normalize_probability(value: float | None) -> float:
        if value in (None, ""):
            return 1.0
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 1.0
        return max(0.0, min(1.0, parsed))

    def _next_transfer_id(self) -> str:
        self._transfer_sequence += 1
        return f"transfer_{self._transfer_sequence:05d}_{uuid.uuid4().hex[:8]}"

    def _append_log(self, payload: dict[str, Any]) -> None:
        if not self.request_log_path:
            return
        with open(self.request_log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _unit_for_target(self, to_unit: str):
        target = str(to_unit or "").strip().lower()
        if target == "icu":
            return self.icu_unit
        return self.ward_unit

    def request_transfer(
        self,
        *,
        encounter_id: str,
        patient_id: str,
        from_group: str,
        to_group: str,
        from_unit: str,
        to_unit: str,
        request_step: int,
        request_minute: int,
        ctas_level,
        reason: str | None = None,
        summary: str | None = None,
        requested_resources: list[str] | None = None,
        transfer_id: str | None = None,
    ) -> TransferResponse:
        transfer_id = str(transfer_id or self._next_transfer_id())
        attempt = int(self._attempts_by_transfer_id.get(transfer_id, 0) or 0) + 1
        self._attempts_by_transfer_id[transfer_id] = attempt
        request = TransferRequest(
            transfer_id=transfer_id,
            encounter_id=str(encounter_id or patient_id),
            patient_id=str(patient_id),
            from_group=str(from_group),
            to_group=str(to_group),
            from_unit=str(from_unit),
            to_unit=str(to_unit),
            request_step=int(request_step),
            request_minute=int(request_minute),
            ctas_level=int(ctas_level) if ctas_level is not None else None,
            reason=reason,
            summary=summary,
            requested_resources=list(requested_resources or ["bed"]),
            status="requested",
        )
        unit = self._unit_for_target(to_unit)
        self.transfer_request_count += 1

        unit_can_accept = unit.can_accept()
        probability_gate_blocked = (
            str(to_unit or "").strip().lower() == "icu"
            and unit_can_accept
            and self.icu_acceptance_probability < 1.0
            and self._rng.random() > self.icu_acceptance_probability
        )

        if unit_can_accept and not probability_gate_blocked:
            assigned_bed = unit.accept(patient_id=str(patient_id))
            completed_minute = int(request.request_minute) + int(self.transfer_turnaround_minutes)
            completed_step = int(request.request_step) + int(
                math.ceil(float(self.transfer_turnaround_minutes) / float(self.minutes_per_step))
            )
            response = TransferResponse(
                transfer_id=transfer_id,
                accepted=True,
                status="accepted",
                reason=f"{str(to_unit).lower()}_bed_assigned",
                assigned_bed=assigned_bed,
                available_capacity=unit.available_capacity,
                expected_eta_minutes=int(self.transfer_turnaround_minutes),
                retry_after_seconds=None,
                next_check_minute=None,
                next_check_step=None,
                transfer_completed_minute=completed_minute,
                transfer_completed_step=completed_step,
            )
            self.accepted_transfer_count += 1
        else:
            next_check_minute = int(request.request_minute) + int(math.ceil(self.retry_after_seconds / 60.0))
            next_check_step = int(request.request_step) + int(
                math.ceil((next_check_minute - int(request.request_minute)) / float(self.minutes_per_step))
            )
            response = TransferResponse(
                transfer_id=transfer_id,
                accepted=False,
                status="pending",
                reason=(
                    "icu_acceptance_probability_gate"
                    if probability_gate_blocked
                    else f"{str(to_unit).lower()}_bed_unavailable"
                ),
                assigned_bed=None,
                available_capacity=unit.available_capacity,
                expected_eta_minutes=None,
                retry_after_seconds=int(self.retry_after_seconds),
                next_check_minute=next_check_minute,
                next_check_step=next_check_step,
                transfer_completed_minute=None,
                transfer_completed_step=None,
            )
            self.pending_transfer_count += 1
            if probability_gate_blocked:
                self.icu_probability_gate_pending_count += 1

        self._append_log(
            {
                "profile_name": self.profile_name,
                "attempt": attempt,
                "request": request.to_dict(),
                "response": response.to_dict(),
            }
        )
        return response

    def runtime_summary(self) -> dict[str, int]:
        return {
            "icu_capacity": int(self.icu_unit.capacity),
            "icu_occupancy": int(self.icu_unit.current_occupancy),
            "ward_capacity": int(self.ward_unit.capacity),
            "ward_occupancy": int(self.ward_unit.current_occupancy),
            "transfer_request_count": int(self.transfer_request_count),
            "accepted_transfer_count": int(self.accepted_transfer_count),
            "pending_transfer_count": int(self.pending_transfer_count),
            "icu_acceptance_probability": float(self.icu_acceptance_probability),
            "icu_probability_gate_pending_count": int(self.icu_probability_gate_pending_count),
        }
