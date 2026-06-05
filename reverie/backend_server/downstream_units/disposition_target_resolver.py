from __future__ import annotations

import random


DEFAULT_TARGET_PROBABILITIES = {
    "1": {"ICU": 0.85, "ward": 0.15},
    "2": {"ICU": 0.45, "ward": 0.55},
    "3": {"ICU": 0.10, "ward": 0.90},
    "4": {"ICU": 0.05, "ward": 0.95},
    "5": {"ICU": 0.00, "ward": 1.00},
}


class DispositionTargetResolver:
    def __init__(self, target_probabilities: dict | None = None):
        source = target_probabilities or DEFAULT_TARGET_PROBABILITIES
        self.target_probabilities: dict[str, dict[str, float]] = {}
        for key, value in source.items():
            payload = dict(value or {})
            icu_probability = float(payload.get("ICU", 0.0) or 0.0)
            icu_probability = min(max(icu_probability, 0.0), 1.0)
            self.target_probabilities[str(key)] = {
                "ICU": icu_probability,
                "ward": 1.0 - icu_probability,
            }

    @staticmethod
    def _coerce_ctas(ctas_level) -> str:
        try:
            score = int(ctas_level)
        except (TypeError, ValueError):
            score = 3
        score = min(max(score, 1), 5)
        return str(score)

    def resolve(self, *, ctas_level, admitted: bool, rng=None) -> str:
        if not admitted:
            return "discharge"
        rng = rng or random
        ctas_key = self._coerce_ctas(ctas_level)
        default_profile = self.target_probabilities.get("3")
        if default_profile is None:
            default_profile = next(iter(self.target_probabilities.values()), {"ICU": 0.0, "ward": 1.0})
        profile = self.target_probabilities.get(ctas_key, default_profile)
        if float(profile.get("ICU", 0.0) or 0.0) <= 0:
            return "ward"
        return "ICU" if rng.random() < float(profile["ICU"]) else "ward"
