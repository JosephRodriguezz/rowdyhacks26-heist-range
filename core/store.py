"""Thread-safe persistence and audience enforcement for the core control plane.

Snapshots (including ``list_sessions``) and team boards are trusted INTERNAL
interfaces. Controllers must project their public session fields before exposing
them. Event and evidence reads enforce the requested audience here, at the source.
No model, network, credential, or session-lifecycle policy belongs in this module.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
from typing import Iterator


_SCHEMA_VERSION = "1.0"
_STATUSES = frozenset({
    "created", "running", "pausing", "paused", "stopping", "completed",
    "cancelled", "failed",
})
_AUDIENCES = {
    "judge_safe": frozenset({"judge_safe"}),
    "red_private": frozenset({"judge_safe", "red_private"}),
    "blue_private": frozenset({"judge_safe", "blue_private"}),
    "referee_only": frozenset({
        "judge_safe", "red_private", "blue_private", "referee_only",
    }),
}
_READERS = {
    visibility: frozenset(
        audience for audience, allowed in _AUDIENCES.items()
        if visibility in allowed
    )
    for visibility in _AUDIENCES
}
_EVENT_FIELDS = frozenset({
    "type", "actor", "target_id", "target_version", "data_source",
    "visibility", "producer", "evidence_refs", "data",
})
_EVIDENCE_FIELDS = frozenset({
    "evidence_id", "visibility", "data", "source_mode",
})
_IMMUTABLE_FIELDS = frozenset({"id", "schema_version", "last_event_id", "boards"})


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _integer(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _version(value: object) -> None:
    if type(value) is int and value > 0:
        return
    _string(value, "target_version")


def _audience(value: object) -> str:
    if not isinstance(value, str) or value not in _AUDIENCES:
        raise ValueError("unknown audience or visibility")
    return value


def _json_copy(value: object) -> object:
    """Reject non-JSON values rather than letting JSON silently coerce them."""
    def validate(item: object) -> None:
        if item is None or type(item) in (str, int, float, bool):
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                validate(child)
            return
        if isinstance(item, list):
            for child in item:
                validate(child)
            return
        raise ValueError("records must contain only JSON values")

    try:
        validate(value)
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("records must contain finite, acyclic JSON values") from exc


def _object(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a dict")
    return _json_copy(value)


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings")
    for item in value:
        _string(item, field)
    return value


def _boards(value: object) -> dict:
    result = _object(value, "boards")
    if result.keys() - {"red", "blue"}:
        raise ValueError("boards may contain only red and blue")
    for team, board in result.items():
        if not isinstance(board, dict):
            raise ValueError(f"{team} board must be a dict")
    return result


def _validate_snapshot(snapshot: dict) -> None:
    if snapshot["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    _string(snapshot["id"], "id")
    _string(snapshot["target_id"], "target_id")
    _version(snapshot["target_version"])
    if snapshot["mode"] != "autonomous":
        raise ValueError("unsupported session mode")
    _string(snapshot["data_source"], "data_source")
    if snapshot["planner_mode"] not in ("fixture", "model"):
        raise ValueError("unsupported planner_mode")
    if not isinstance(snapshot["status"], str) or snapshot["status"] not in _STATUSES:
        raise ValueError("unsupported session status")
    _string(snapshot["phase"], "phase")
    _integer(snapshot["last_event_id"], "last_event_id")
    for field in ("allowed_actions", "finding_ids", "defense_ids"):
        _strings(snapshot[field], field)
    if not isinstance(snapshot["budget"], dict):
        raise ValueError("budget must be a dict")
    if snapshot["verdict"] is not None and not isinstance(snapshot["verdict"], dict):
        raise ValueError("verdict must be a dict or None")
    _boards(snapshot["boards"])


def _records(value: object, field: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of dicts")
    return [_object(record, field) for record in value]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _encode(value: object) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


class Store:
    """A single locked SQLite connection, with transactions across all records.

    Independent Store instances also serialize writes using BEGIN IMMEDIATE.
    Evidence identifiers are session-scoped; event IDs start at 1 per session.
    ``boards`` in an apply call replaces only each supplied team's board.
    """

    def __init__(self, path):
        try:
            db_path = os.fspath(path)
        except TypeError as exc:
            raise ValueError("path must be a filesystem path or ':memory:'") from exc
        _string(db_path, "path")
        self._lock = threading.RLock()
        if db_path != ":memory:":
            # O_EXCL distinguishes a new database without chmodding existing files.
            try:
                descriptor = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
        self._connection = sqlite3.connect(
            db_path, timeout=30, isolation_level=None, check_same_thread=False,
        )
        self._closed = False
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY NOT NULL,
                    snapshot TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    session_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    visibility TEXT NOT NULL CHECK (visibility IN (
                        'judge_safe', 'red_private', 'blue_private', 'referee_only'
                    )),
                    record TEXT NOT NULL,
                    PRIMARY KEY (session_id, evidence_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    session_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL CHECK (event_id > 0),
                    visibility TEXT NOT NULL CHECK (visibility IN (
                        'judge_safe', 'red_private', 'blue_private', 'referee_only'
                    )),
                    record TEXT NOT NULL,
                    PRIMARY KEY (session_id, event_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS event_evidence (
                    session_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    evidence_id TEXT NOT NULL,
                    PRIMARY KEY (session_id, event_id, evidence_id),
                    FOREIGN KEY (session_id, event_id)
                        REFERENCES events(session_id, event_id),
                    FOREIGN KEY (session_id, evidence_id)
                        REFERENCES evidence(session_id, evidence_id)
                );
            """)
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("store is closed")

    @contextmanager
    def _write(self) -> Iterator[None]:
        with self._lock:
            self._ensure_open()
            nested = self._connection.in_transaction
            self._connection.execute("SAVEPOINT core_nested_write" if nested else "BEGIN IMMEDIATE")
            try:
                yield
                self._connection.execute("RELEASE core_nested_write" if nested else "COMMIT")
            except BaseException as exc:
                if nested:
                    self._connection.execute("ROLLBACK TO core_nested_write")
                    self._connection.execute("RELEASE core_nested_write")
                else:
                    self._connection.execute("ROLLBACK")
                if isinstance(exc, sqlite3.IntegrityError):
                    raise ValueError("duplicate identifier or invalid record reference") from exc
                raise

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Group a controller transition, its events, and idempotency receipt.

        Controllers acquire dispatch admission before this transaction, never
        while holding this lock, to preserve the gate -> store lock order.
        """
        with self._write():
            yield

    def _snapshot(self, session_id: str) -> dict:
        _string(session_id, "session_id")
        row = self._connection.execute(
            "SELECT snapshot FROM sessions WHERE session_id = ?", (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return json.loads(row[0])

    def create(self, snapshot: dict) -> dict:
        record = {
            "schema_version": _SCHEMA_VERSION,
            "target_version": 1,
            "mode": "autonomous",
            "data_source": "live",
            "planner_mode": "fixture",
            "status": "created",
            "phase": "created",
            "last_event_id": 0,
            "allowed_actions": [],
            "finding_ids": [],
            "defense_ids": [],
            "budget": {},
            "verdict": None,
            "boards": {"red": {}, "blue": {}},
        }
        record.update(_object(snapshot, "snapshot"))
        if "id" not in record or "target_id" not in record:
            raise ValueError("snapshot requires id and target_id")
        record["boards"] = {"red": {}, "blue": {}, **_boards(record["boards"])}
        _validate_snapshot(record)
        if record["last_event_id"] != 0:
            raise ValueError("new sessions must have last_event_id = 0")
        with self._write():
            self._connection.execute(
                "INSERT INTO sessions(session_id, snapshot) VALUES (?, ?)",
                (record["id"], _encode(record)),
            )
        return _json_copy(record)

    def apply(
        self, session_id, *, updates: dict | None = None,
        events: list[dict] | None = None, evidence: list[dict] | None = None,
        boards: dict | None = None,
    ) -> dict:
        changes = {} if updates is None else _object(updates, "updates")
        if changes.keys() & _IMMUTABLE_FIELDS:
            raise ValueError("identity, schema, event cursor, and boards are store-owned")
        event_records = _records(events, "events")
        evidence_records = _records(evidence, "evidence")
        team_boards = {} if boards is None else _boards(boards)
        with self._write():
            snapshot = self._snapshot(session_id)
            snapshot.update(changes)
            snapshot["boards"].update(team_boards)
            _validate_snapshot(snapshot)
            for item in evidence_records:
                self._add_evidence(snapshot, item)
            for item in event_records:
                self._add_event(snapshot, item)
            self._connection.execute(
                "UPDATE sessions SET snapshot = ? WHERE session_id = ?",
                (_encode(snapshot), session_id),
            )
        return _json_copy(snapshot)

    def _add_evidence(self, snapshot: dict, item: dict) -> None:
        if item.keys() - _EVIDENCE_FIELDS or not {
            "evidence_id", "visibility", "data",
        } <= item.keys():
            raise ValueError("malformed evidence envelope")
        evidence_id = _string(item["evidence_id"], "evidence_id")
        visibility = _audience(item["visibility"])
        if not isinstance(item["data"], dict):
            raise ValueError("evidence data must be a dict")
        if "source_mode" in item:
            _string(item["source_mode"], "source_mode")
        record = {
            **item,
            "schema_version": _SCHEMA_VERSION,
            "assessment_id": snapshot["id"],
            "timestamp": _timestamp(),
            "target_id": snapshot["target_id"],
            "target_version": snapshot["target_version"],
        }
        self._connection.execute(
            "INSERT INTO evidence(session_id, evidence_id, visibility, record) VALUES (?, ?, ?, ?)",
            (snapshot["id"], evidence_id, visibility, _encode(record)),
        )

    def _add_event(self, snapshot: dict, item: dict) -> None:
        if item.keys() - _EVENT_FIELDS or not {
            "type", "actor", "visibility", "evidence_refs", "data",
        } <= item.keys():
            raise ValueError("malformed event envelope")
        _string(item["type"], "type")
        _string(item["actor"], "actor")
        visibility = _audience(item["visibility"])
        references = _strings(item["evidence_refs"], "evidence_refs")
        if len(references) != len(set(references)):
            raise ValueError("duplicate evidence references")
        if not isinstance(item["data"], dict):
            raise ValueError("event data must be a dict")
        record = {
            "target_id": snapshot["target_id"],
            "target_version": snapshot["target_version"],
            "data_source": snapshot["data_source"],
            "producer": "core",
            **item,
            "schema_version": _SCHEMA_VERSION,
            "assessment_id": snapshot["id"],
            "timestamp": _timestamp(),
            "id": snapshot["last_event_id"] + 1,
            "sequence": snapshot["last_event_id"] + 1,
        }
        for field in ("target_id", "data_source", "producer"):
            _string(record[field], field)
        _version(record["target_version"])
        for reference in references:
            row = self._connection.execute(
                "SELECT visibility FROM evidence WHERE session_id = ? AND evidence_id = ?",
                (snapshot["id"], reference),
            ).fetchone()
            if row is None:
                raise ValueError("event references unknown evidence in this session")
            # Every reader of the event must be able to read its referenced evidence.
            if not _READERS[visibility] <= _READERS[row[0]]:
                raise ValueError("evidence is more private than its referencing event")
        self._connection.execute(
            "INSERT INTO events(session_id, event_id, visibility, record) VALUES (?, ?, ?, ?)",
            (snapshot["id"], record["id"], visibility, _encode(record)),
        )
        self._connection.executemany(
            "INSERT INTO event_evidence(session_id, event_id, evidence_id) VALUES (?, ?, ?)",
            [(snapshot["id"], record["id"], reference) for reference in references],
        )
        snapshot["last_event_id"] = record["id"]

    def snapshot(self, session_id) -> dict:
        """Return the unsanitized session snapshot to trusted core callers only."""
        with self._lock:
            self._ensure_open()
            return self._snapshot(session_id)

    def list_sessions(self) -> list[dict]:
        """Return independent INTERNAL snapshots in session creation order."""
        with self._lock:
            self._ensure_open()
            return [json.loads(row[0]) for row in self._connection.execute(
                "SELECT snapshot FROM sessions ORDER BY rowid",
            )]

    def events(self, session_id, *, after=0, audience="judge_safe", limit=200) -> dict:
        """Page visible events using a cursor over *all* events in the session.

        If visible events remain beyond the limit, stop at the last returned ID.
        Otherwise advance to the captured global cutoff, including private events.
        A zero limit cannot advance past any pending visible event.
        """
        _integer(after, "after")
        _integer(limit, "limit")
        allowed = sorted(_AUDIENCES[_audience(audience)])
        with self._lock:
            self._ensure_open()
            cutoff = self._snapshot(session_id)["last_event_id"]
            placeholders = ",".join("?" for _ in allowed)
            # Fetch one extra visible event to detect a truncated page. The upper
            # bound keeps the result stable even if another Store commits a write.
            sql = f"""SELECT event_id, record FROM events
                      WHERE session_id = ? AND event_id > ? AND event_id <= ?
                        AND visibility IN ({placeholders})
                      ORDER BY event_id LIMIT ?"""
            # SQLite INTEGER parameters are signed 64-bit; huge JSON cursors and
            # limits are valid nonnegative ints but must not overflow its binding.
            sqlite_max = (1 << 63) - 1
            rows = self._connection.execute(
                sql, (session_id, min(after, sqlite_max), cutoff, *allowed,
                      min(limit + 1, sqlite_max)),
            ).fetchall()
            if len(rows) > limit:
                cutoff = rows[limit - 1][0] if limit else after
                rows = rows[:limit]
            return {"events": [json.loads(row[1]) for row in rows], "last_event_id": cutoff}

    def evidence(self, session_id, evidence_id, *, audience="judge_safe") -> dict:
        _string(evidence_id, "evidence_id")
        allowed = _AUDIENCES[_audience(audience)]
        with self._lock:
            self._ensure_open()
            self._snapshot(session_id)
            row = self._connection.execute(
                "SELECT visibility, record FROM evidence WHERE session_id = ? AND evidence_id = ?",
                (session_id, evidence_id),
            ).fetchone()
            # A forbidden identifier is indistinguishable from a missing one.
            if row is None or row[0] not in allowed:
                raise KeyError(evidence_id)
            return json.loads(row[1])

    def board(self, session_id, team) -> dict:
        """Return exactly one private board; callers must enforce team identity."""
        if not isinstance(team, str) or team not in ("red", "blue"):
            raise ValueError("team must be red or blue")
        with self._lock:
            self._ensure_open()
            return self._snapshot(session_id)["boards"][team]

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True
