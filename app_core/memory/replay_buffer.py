from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import MemoryItem
from .storage import JsonFileMemoryStorage


class ExperienceReplayBuffer:
    def __init__(self, storage: JsonFileMemoryStorage) -> None:
        self.storage = storage

    def export(
        self,
        *,
        run_id: str | None = None,
        mode: str | None = None,
        encounter_id: str | None = None,
        step_range: tuple[int | None, int | None] | None = None,
        scenario_tag: str | None = None,
    ) -> dict[str, Any]:
        events = self._load_events(
            run_id=run_id,
            mode=mode,
            encounter_id=encounter_id,
            step_range=step_range,
            scenario_tag=scenario_tag,
        )
        summaries = self._load_summaries(run_id=run_id, mode=mode, encounter_id=encounter_id)
        snapshots = [snapshot.to_dict() for snapshot in self.storage.list_snapshots(run_id=run_id, mode=mode, encounter_id=encounter_id)]
        audits = [record.to_dict() for record in self.storage.list_audits(run_id=run_id, mode=mode, encounter_id=encounter_id)]
        return {
            "events": events,
            "summaries": summaries,
            "snapshots": snapshots,
            "audits": audits,
        }

    def _load_events(
        self,
        *,
        run_id: str | None,
        mode: str | None,
        encounter_id: str | None,
        step_range: tuple[int | None, int | None] | None,
        scenario_tag: str | None,
    ) -> list[dict[str, Any]]:
        path = self.storage.events_path
        if not path.exists():
            return []
        start_step, end_step = step_range or (None, None)
        output: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = MemoryItem.from_dict(json.loads(line))
                if run_id and item.run_id != run_id:
                    continue
                if mode and item.mode != mode:
                    continue
                if encounter_id and item.encounter_id != encounter_id:
                    continue
                if start_step is not None and item.step < start_step:
                    continue
                if end_step is not None and item.step > end_step:
                    continue
                if scenario_tag and scenario_tag not in item.tags:
                    continue
                output.append(item.to_dict())
        return output

    def _load_summaries(
        self,
        *,
        run_id: str | None,
        mode: str | None,
        encounter_id: str | None,
    ) -> list[dict[str, Any]]:
        root = self.storage.root / "current"
        if mode:
            root = root / mode
        if run_id:
            root = root / run_id
        if not root.exists():
            return []
        output: list[dict[str, Any]] = []
        paths = [root / f"{encounter_id}.json"] if encounter_id else list(root.rglob("*.json"))
        for path in paths:
            if not path.exists():
                continue
            output.append(json.loads(path.read_text(encoding="utf-8")))
        return output

    def export_to_path(self, destination: Path, **kwargs: Any) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self.export(**kwargs)
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destination
