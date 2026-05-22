from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app_core.his.config import utc_now_iso

from ._base import ensure_list_of_dicts, require_dict, require_str


@dataclass(frozen=True)
class HandoffSnapshotRecord:
    snapshot_id: str
    encounter_id: str
    patient_id: str
    from_role: str
    to_role: str
    handoff_stage: str
    patient_brief: str
    current_state: dict[str, Any] = field(default_factory=dict)
    completed_actions: list[dict[str, Any]] = field(default_factory=list)
    pending_tasks: list[dict[str, Any]] = field(default_factory=list)
    active_risks: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_str(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "encounter_id", require_str(self.encounter_id, "encounter_id"))
        object.__setattr__(self, "patient_id", require_str(self.patient_id, "patient_id"))
        object.__setattr__(self, "from_role", require_str(self.from_role, "from_role"))
        object.__setattr__(self, "to_role", require_str(self.to_role, "to_role"))
        object.__setattr__(self, "handoff_stage", require_str(self.handoff_stage, "handoff_stage"))
        object.__setattr__(self, "patient_brief", require_str(self.patient_brief, "patient_brief"))
        object.__setattr__(self, "current_state", require_dict(self.current_state, "current_state"))
        object.__setattr__(self, "completed_actions", ensure_list_of_dicts(self.completed_actions, "completed_actions"))
        object.__setattr__(self, "pending_tasks", ensure_list_of_dicts(self.pending_tasks, "pending_tasks"))
        object.__setattr__(self, "active_risks", ensure_list_of_dicts(self.active_risks, "active_risks"))
        object.__setattr__(self, "next_actions", ensure_list_of_dicts(self.next_actions, "next_actions"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
