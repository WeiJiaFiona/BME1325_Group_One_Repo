from __future__ import annotations

from .base import CapacityUnit


class ICUUnit(CapacityUnit):
    def __init__(self, capacity: int):
        super().__init__(unit_name="ICU", capacity=capacity)
