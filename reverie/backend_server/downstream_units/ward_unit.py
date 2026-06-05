from __future__ import annotations

from .base import CapacityUnit


class WardUnit(CapacityUnit):
    def __init__(self, capacity: int):
        super().__init__(unit_name="WARD", capacity=capacity)
