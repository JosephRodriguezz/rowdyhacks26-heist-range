"""Read-only playback projection for a locally saved run report."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


MAX_REPLAY_BYTES = 2_000_000
MAX_ITEMS = 10_000


class ReplayError(ValueError):
    pass


def load_recorded_trace(path: str | Path) -> dict[str, Any]:
    """Project a run record to displayable events; never dispatch or re-evaluate actions."""
    source = Path(path).expanduser()
    try:
        if source.stat().st_size > MAX_REPLAY_BYTES:
            raise ReplayError("run record exceeds the replay size limit")
        record = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReplayError(f"run record could not be read ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise ReplayError("run record is not valid JSON") from None
    if not isinstance(record, dict):
        raise ReplayError("run record must be an object")
    events, evidence = record.get("events"), record.get("evidence_records")
    hypotheses = record.get("hypotheses", [])
    if not isinstance(events, list) or not isinstance(evidence, list):
        raise ReplayError("run record is missing its event or evidence list")
    if len(events) > MAX_ITEMS or len(evidence) > MAX_ITEMS:
        raise ReplayError("run record has too many events or evidence items")
    if any(not isinstance(item, dict) for item in [*events, *evidence]):
        raise ReplayError("event and evidence entries must be objects")
    if not isinstance(hypotheses, list) or len(hypotheses) > MAX_ITEMS or any(not isinstance(item, dict) for item in hypotheses):
        raise ReplayError("hypothesis entries must be bounded objects")
    public_events = [item for item in events if item.get("visibility") != "referee_only"]
    return {
        "replay_id": "replay-" + uuid.uuid4().hex[:12],
        "source_mode": "recorded_replay",
        "evaluation_status": "recorded_original_not_recomputed",
        "original_run_id": str(record.get("run_id", "unknown")),
        "target_kind": str(record.get("target_kind", "unknown")),
        "original_planner_mode": str(record.get("planner_mode", "unknown")),
        "original_verdict": str(record.get("verdict", "unknown")),
        "events": public_events,
        "evidence_records": evidence,
        "tasks": record.get("tasks", []) if isinstance(record.get("tasks", []), list) else [],
        "handoffs": record.get("handoffs", []) if isinstance(record.get("handoffs", []), list) else [],
        "hypotheses": hypotheses,
        "evaluation_private": {"visibility": "referee_only", "included": False},
        "note": "Recorded activity only. Replay makes no target requests and does not recalculate the verdict.",
    }
