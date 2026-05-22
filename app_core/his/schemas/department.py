from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app_core.his.config import utc_now_iso

from ._base import optional_str, require_str


@dataclass(frozen=True)
class DepartmentRecord:
    department_id: str
    department_name: str
    zone: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "department_id", require_str(self.department_id, "department_id"))
        object.__setattr__(self, "department_name", require_str(self.department_name, "department_name"))
        object.__setattr__(self, "zone", optional_str(self.zone, "zone"))
        object.__setattr__(self, "created_at", require_str(self.created_at, "created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
