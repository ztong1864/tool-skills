from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..fsutil import atomic_write_text
from .feedback import FeedbackStore
from .experience import ExperienceStore
from .models import MissionState


class StateStore:
    def __init__(self, root: Path, mission_id: str):
        self.mission_id = mission_id
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", mission_id)
        self.run_dir = Path(root) / safe_id
        self.state_path = self.run_dir / "state.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.feedback = FeedbackStore(self.run_dir.parent)
        self.experiences = ExperienceStore(self.run_dir.parent)

    @property
    def lock_path(self) -> Path:
        """Beside the run directory, so locking never creates a mission folder."""
        return self.run_dir.with_name(f".{self.run_dir.name}.lock")

    def save(self, state: MissionState) -> None:
        # Readers see either the previous or the new state, never a partial file.
        atomic_write_text(self.state_path, json.dumps(state.to_dict(), ensure_ascii=False, indent=2))

    def load(self) -> MissionState:
        state = MissionState.from_dict(json.loads(self.state_path.read_text(encoding="utf-8")))
        state.artifacts = {key: self._rebase(value) for key, value in state.artifacts.items()}
        for record in state.artifact_records.values():
            if isinstance(record, dict) and record.get("path"):
                record["path"] = self._rebase(record["path"])
        return state

    def _rebase(self, value: str) -> str:
        """Point mission-owned artifact paths at this run directory after a workspace move."""
        path = Path(str(value))
        if path.exists():
            return str(value)
        parts = path.parts
        for index in range(1, len(parts) - 1):
            if parts[index - 1] == "runs" and parts[index] == self.run_dir.name and parts[index + 1] == "artifacts":
                candidate = self.run_dir.joinpath(*parts[index + 1:])
                if candidate.exists():
                    return str(candidate)
        return str(value)

    def event(self, event: str, payload: dict[str, Any]) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **payload}
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
