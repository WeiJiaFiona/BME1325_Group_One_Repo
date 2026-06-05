from __future__ import annotations


class CapacityUnit:
    def __init__(self, *, unit_name: str, capacity: int):
        self.unit_name = str(unit_name or "UNIT").upper()
        self.capacity = max(0, int(capacity or 0))
        self._occupants: dict[str, str] = {}
        self._bed_sequence = 0

    @property
    def current_occupancy(self) -> int:
        return len(self._occupants)

    @property
    def available_capacity(self) -> int:
        return max(0, int(self.capacity) - int(self.current_occupancy))

    def can_accept(self) -> bool:
        return self.available_capacity > 0

    def accept(self, patient_id: str) -> str | None:
        patient_key = str(patient_id or "").strip()
        if not patient_key:
            raise ValueError("patient_id is required")
        if patient_key in self._occupants:
            return self._occupants[patient_key]
        if not self.can_accept():
            return None
        self._bed_sequence += 1
        bed_id = f"{self.unit_name}-BED-{self._bed_sequence:03d}"
        self._occupants[patient_key] = bed_id
        return bed_id

    def release(self, patient_id: str) -> bool:
        patient_key = str(patient_id or "").strip()
        if not patient_key:
            return False
        removed = self._occupants.pop(patient_key, None)
        return removed is not None
