"""Synthetic SQLite store tests; these do not exercise a lab or model provider."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.store import Store


VISIBILITIES = ("judge_safe", "red_private", "blue_private", "referee_only")
ALLOWED = {
    "judge_safe": {"judge_safe"},
    "red_private": {"judge_safe", "red_private"},
    "blue_private": {"judge_safe", "blue_private"},
    "referee_only": set(VISIBILITIES),
}


def session(session_id="run-1", **changes):
    return {
        "id": session_id,
        "target_id": "synthetic-bank",
        "target_version": 1,
        "data_source": "fixture",
        "planner_mode": "fixture",
        **changes,
    }


def event(visibility="judge_safe", refs=None, **changes):
    return {
        "type": "observation.recorded",
        "actor": "synthetic-core",
        "producer": "fixture",
        "visibility": visibility,
        "evidence_refs": [] if refs is None else refs,
        "data": {"summary": "Synthetic observation"},
        **changes,
    }


def evidence(evidence_id="ev-1", visibility="judge_safe", **changes):
    return {
        "evidence_id": evidence_id,
        "visibility": visibility,
        "data": {"summary": "Synthetic evidence"},
        "source_mode": "fixture",
        **changes,
    }


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.store.create(session())

    def test_canonical_snapshot_and_internal_fields_survive(self):
        created = self.store.create(session(
            "run-2", evaluation_private={"visibility": "referee_only", "marker": "synthetic"},
        ))
        self.assertEqual(created, self.store.snapshot("run-2"))
        self.assertEqual(created["schema_version"], "1.0")
        self.assertEqual(created["mode"], "autonomous")
        self.assertEqual(created["status"], "created")
        self.assertEqual(created["last_event_id"], 0)
        self.assertEqual(created["boards"], {"red": {}, "blue": {}})
        for field in ("phase", "allowed_actions", "finding_ids", "defense_ids", "budget", "verdict"):
            self.assertIn(field, created)
        self.assertEqual(created["evaluation_private"]["marker"], "synthetic")
        self.assertEqual([item["id"] for item in self.store.list_sessions()], ["run-1", "run-2"])
        minimal = self.store.create({"id": "minimal", "target_id": "synthetic-bank"})
        self.assertEqual(minimal["data_source"], "live")
        self.assertEqual(minimal["planner_mode"], "fixture")

    def test_apply_commits_state_records_and_boards_together(self):
        result = self.store.apply(
            "run-1", updates={"status": "running", "phase": "survey", "budget": {"calls": 9}},
            events=[event(refs=["ev-1"])], evidence=[evidence()],
            boards={"red": {"tasks": [{"id": "scout-task"}]}},
        )
        self.assertEqual(result, self.store.snapshot("run-1"))
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["last_event_id"], 1)
        recorded = self.store.events("run-1")["events"][0]
        self.assertEqual(recorded["id"], 1)
        self.assertEqual(recorded["sequence"], 1)
        self.assertEqual(recorded["assessment_id"], "run-1")
        self.assertEqual(recorded["schema_version"], "1.0")
        self.assertEqual(recorded["target_id"], "synthetic-bank")
        self.assertEqual(recorded["target_version"], 1)
        self.assertEqual(recorded["data_source"], "fixture")
        self.assertEqual(recorded["producer"], "fixture")
        self.assertEqual(recorded["visibility"], "judge_safe")
        self.assertEqual(recorded["evidence_refs"], ["ev-1"])
        self.assertTrue(recorded["timestamp"].endswith("Z"))
        parsed = datetime.fromisoformat(recorded["timestamp"].replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), timezone.utc.utcoffset(parsed))
        self.assertEqual(self.store.evidence("run-1", "ev-1")["source_mode"], "fixture")
        self.assertEqual(self.store.board("run-1", "red")["tasks"][0]["id"], "scout-task")
        self.assertEqual(self.store.board("run-1", "blue"), {})

    def test_event_defaults_use_updated_session_and_preserve_explicit_source(self):
        default_event = event()
        del default_event["producer"]
        self.store.apply(
            "run-1", updates={"target_version": "v2"},
            events=[default_event, event(target_id="other-registered-lab", target_version=3,
                                          data_source="recorded", producer="referee")],
            evidence=[{"evidence_id": "no-source", "visibility": "judge_safe", "data": {}}],
        )
        first, second = self.store.events("run-1")["events"]
        self.assertEqual(first["target_version"], "v2")
        self.assertEqual(first["producer"], "core")
        self.assertEqual(second["data_source"], "recorded")
        self.assertEqual(second["target_id"], "other-registered-lab")
        self.assertEqual(second["target_version"], 3)
        self.assertNotIn("source_mode", self.store.evidence("run-1", "no-source"))

    def test_late_invalid_event_rolls_back_state_evidence_events_and_boards(self):
        before = self.store.snapshot("run-1")
        with self.assertRaises(ValueError):
            self.store.apply(
                "run-1", updates={"status": "running"},
                evidence=[evidence("new-evidence")],
                events=[event(refs=["new-evidence"]), event(refs=["missing"])],
                boards={"red": {"private": "should roll back"}},
            )
        self.assertEqual(self.store.snapshot("run-1"), before)
        self.assertEqual(self.store.events("run-1"), {"events": [], "last_event_id": 0})
        with self.assertRaises(KeyError):
            self.store.evidence("run-1", "new-evidence")
        self.store.apply("run-1", events=[event()])
        self.assertEqual(self.store.events("run-1")["events"][0]["id"], 1)

    def test_duplicate_identifiers_roll_back_without_overwriting(self):
        before = self.store.snapshot("run-1")
        with self.assertRaises(ValueError):
            self.store.create(session(status="running"))
        self.assertEqual(self.store.snapshot("run-1"), before)
        with self.assertRaises(ValueError):
            self.store.apply("run-1", updates={"status": "running"},
                             evidence=[evidence("new"), evidence("new")])
        self.assertEqual(self.store.snapshot("run-1"), before)
        with self.assertRaises(KeyError):
            self.store.evidence("run-1", "new")
        self.store.apply("run-1", evidence=[evidence()])
        original = self.store.evidence("run-1", "ev-1")
        with self.assertRaises(ValueError):
            self.store.apply("run-1", evidence=[evidence("other"), evidence(data={"changed": True})])
        self.assertEqual(self.store.evidence("run-1", "ev-1"), original)
        with self.assertRaises(KeyError):
            self.store.evidence("run-1", "other")
        with self.assertRaises(ValueError):
            self.store.apply("run-1", events=[event(id=88)])
        self.assertEqual(self.store.snapshot("run-1")["last_event_id"], 0)

    def test_events_and_evidence_enforce_every_audience(self):
        self.store.apply(
            "run-1", evidence=[evidence(v, v) for v in VISIBILITIES],
            events=[event(v, [v], data={"marker": v}) for v in VISIBILITIES],
        )
        for audience in VISIBILITIES:
            with self.subTest(audience=audience):
                page = self.store.events("run-1", audience=audience)
                self.assertEqual(page["last_event_id"], 4)
                self.assertEqual(
                    {item["data"]["marker"] for item in page["events"]}, ALLOWED[audience],
                )
                for visibility in VISIBILITIES:
                    if visibility in ALLOWED[audience]:
                        self.assertEqual(self.store.evidence(
                            "run-1", visibility, audience=audience,
                        )["visibility"], visibility)
                    else:
                        with self.assertRaises(KeyError):
                            self.store.evidence("run-1", visibility, audience=audience)

    def test_reference_visibility_matrix_rejects_audience_leaks(self):
        self.store.apply("run-1", evidence=[evidence(v, v) for v in VISIBILITIES])
        for event_visibility in VISIBILITIES:
            event_readers = {a for a in VISIBILITIES if event_visibility in ALLOWED[a]}
            for evidence_visibility in VISIBILITIES:
                with self.subTest(event=event_visibility, evidence=evidence_visibility):
                    evidence_readers = {a for a in VISIBILITIES if evidence_visibility in ALLOWED[a]}
                    before = self.store.snapshot("run-1")
                    operation = lambda: self.store.apply(
                        "run-1", updates={"phase": "reference-test"},
                        events=[event(event_visibility, [evidence_visibility])],
                    )
                    if event_readers <= evidence_readers:
                        self.assertEqual(operation()["last_event_id"], before["last_event_id"] + 1)
                    else:
                        with self.assertRaises(ValueError):
                            operation()
                        self.assertEqual(self.store.snapshot("run-1"), before)

    def test_references_are_session_scoped_and_unknown_refs_reject(self):
        self.store.create(session("run-2"))
        self.store.apply("run-2", evidence=[evidence("foreign-only"), evidence("same-id")])
        for ref in ("missing", "foreign-only", "same-id"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                self.store.apply("run-1", events=[event(refs=[ref])])
        with self.assertRaises(KeyError):
            self.store.evidence("run-1", "foreign-only", audience="referee_only")
        self.store.apply(
            "run-1", evidence=[evidence("same-id", "red_private", data={"marker": "local"})],
            events=[event("red_private", ["same-id"])],
        )
        self.assertEqual(self.store.evidence(
            "run-1", "same-id", audience="red_private",
        )["data"], {"marker": "local"})
        self.assertEqual(self.store.events("run-1")["events"], [])

    def test_cursor_pagination_never_skips_pending_visible_events(self):
        visibilities = ["red_private", "judge_safe", "referee_only", "judge_safe",
                        "blue_private", "judge_safe", "referee_only"]
        self.store.apply("run-1", events=[event(v) for v in visibilities])
        first = self.store.events("run-1", limit=1)
        self.assertEqual([e["id"] for e in first["events"]], [2])
        self.assertEqual(first["last_event_id"], 2)
        self.assertEqual(first, self.store.events("run-1", limit=1))
        second = self.store.events("run-1", after=first["last_event_id"], limit=1)
        self.assertEqual([e["id"] for e in second["events"]], [4])
        self.assertEqual(second["last_event_id"], 4)
        third = self.store.events("run-1", after=second["last_event_id"], limit=1)
        self.assertEqual([e["id"] for e in third["events"]], [6])
        self.assertEqual(third["last_event_id"], 7)
        self.assertEqual(self.store.events("run-1", after=7), {"events": [], "last_event_id": 7})
        self.assertEqual(self.store.events("run-1", after=999), {"events": [], "last_event_id": 7})
        self.assertEqual(self.store.events("run-1", limit=0), {"events": [], "last_event_id": 0})
        self.assertEqual(self.store.events("run-1", after=4, limit=0), {"events": [], "last_event_id": 4})
        self.assertEqual(self.store.events("run-1", after=6, limit=0), {"events": [], "last_event_id": 7})
        for audience in VISIBILITIES:
            cursor, ids = 0, []
            while cursor < 7:
                page = self.store.events("run-1", after=cursor, audience=audience, limit=2)
                self.assertGreater(page["last_event_id"], cursor)
                ids.extend(item["id"] for item in page["events"])
                cursor = page["last_event_id"]
            self.assertEqual(ids, [i for i, v in enumerate(visibilities, 1) if v in ALLOWED[audience]])

    def test_hidden_only_tail_advances_cutoff_and_later_events_are_readable(self):
        self.store.apply("run-1", events=[event("referee_only"), event("blue_private")])
        self.assertEqual(self.store.events("run-1", limit=0), {"events": [], "last_event_id": 2})
        self.store.apply("run-1", events=[event()])
        page = self.store.events("run-1", after=2)
        self.assertEqual([item["id"] for item in page["events"]], [3])
        self.assertEqual(page["last_event_id"], 3)

    def test_boards_remain_isolated_and_replace_only_supplied_team(self):
        self.store.apply("run-1", boards={"red": {"hypotheses": ["red-only"]},
                                           "blue": {"responses": ["blue-only"]}})
        blue = self.store.board("run-1", "blue")
        self.store.apply("run-1", boards={"red": {"tasks": []}})
        self.assertEqual(self.store.board("run-1", "red"), {"tasks": []})
        self.assertEqual(self.store.board("run-1", "blue"), blue)
        self.assertNotIn("responses", self.store.board("run-1", "red"))
        self.store.create(session("seeded", boards={"blue": {"tasks": ["monitor"]}}))
        self.assertEqual(self.store.board("seeded", "red"), {})
        self.assertEqual(self.store.board("seeded", "blue"), {"tasks": ["monitor"]})

    def test_input_and_output_mutation_cannot_change_persistence(self):
        original = session("copy", budget={"calls": [1]})
        created = self.store.create(original)
        original["budget"]["calls"].append(2)
        created["budget"]["calls"].append(3)
        update = {"budget": {"calls": [4]}}
        records = [event(data={"markers": ["event"]})]
        observations = [evidence(data={"markers": ["evidence"]})]
        boards = {"red": {"markers": ["board"]}}
        applied = self.store.apply("copy", updates=update, events=records,
                                   evidence=observations, boards=boards)
        update["budget"]["calls"].append(5)
        records[0]["data"]["markers"].append("changed")
        observations[0]["data"]["markers"].append("changed")
        boards["red"]["markers"].append("changed")
        applied["boards"]["red"]["markers"].append("changed")
        snapshot = self.store.snapshot("copy")
        snapshot["budget"]["calls"].append(6)
        listing = self.store.list_sessions()
        next(item for item in listing if item["id"] == "copy")["budget"]["calls"].append(7)
        self.store.events("copy")["events"][0]["data"]["markers"].append("changed")
        self.store.evidence("copy", "ev-1")["data"]["markers"].append("changed")
        self.store.board("copy", "red")["markers"].append("changed")
        self.assertEqual(self.store.snapshot("copy")["budget"], {"calls": [4]})
        self.assertEqual(self.store.events("copy")["events"][0]["data"], {"markers": ["event"]})
        self.assertEqual(self.store.evidence("copy", "ev-1")["data"], {"markers": ["evidence"]})
        self.assertEqual(self.store.board("copy", "red"), {"markers": ["board"]})

    def test_malformed_snapshots_and_updates_raise_value_error(self):
        invalid = [
            {"schema_version": "2.0"}, {"id": ""}, {"target_id": 3},
            {"target_version": True}, {"target_version": 0}, {"mode": "manual"},
            {"data_source": ""}, {"planner_mode": "deterministic_baseline"},
            {"status": "unknown"}, {"status": []}, {"phase": None},
            {"last_event_id": -1}, {"last_event_id": True}, {"last_event_id": 1},
            {"allowed_actions": "pause"}, {"finding_ids": [3]}, {"defense_ids": [""]},
            {"budget": []}, {"verdict": []}, {"boards": {"referee": {}}},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.create(session("invalid", **changes))
        for value in (None, [], "invalid", {}, {"id": "only-id"}):
            with self.subTest(snapshot=value), self.assertRaises(ValueError):
                self.store.create(value)
        before = self.store.snapshot("run-1")
        for changes in invalid:
            with self.subTest(update=changes), self.assertRaises(ValueError):
                self.store.apply("run-1", updates=changes)
            self.assertEqual(self.store.snapshot("run-1"), before)
        for status in ("created", "running", "pausing", "paused", "stopping", "completed", "cancelled", "failed"):
            self.assertEqual(self.store.apply("run-1", updates={"status": status})["status"], status)

    def test_malformed_envelopes_and_non_json_values_reject_atomically(self):
        invalid_events = [
            {}, event(type=""), event(actor=None), event(visibility="unknown"),
            event(evidence_refs="ev-1"), event(evidence_refs=[3]), event(data=[]),
            event(producer=""), event(target_version=False), event(target_id=""),
            event(data_source=None), event(timestamp="forged"),
            event(refs=["ev-1", "ev-1"]), event(data={"nan": float("nan")}),
        ]
        invalid_evidence = [
            {}, evidence(evidence_id=""), evidence(visibility="unknown"),
            evidence(data=[]), evidence(source_mode=""), evidence(session_id="foreign"),
        ]
        self.store.apply("run-1", evidence=[evidence()])
        before = self.store.snapshot("run-1")
        for item in invalid_events:
            with self.subTest(event=item), self.assertRaises(ValueError):
                self.store.apply("run-1", events=[event(), item])
            self.assertEqual(self.store.snapshot("run-1"), before)
        for item in invalid_evidence:
            with self.subTest(evidence=item), self.assertRaises(ValueError):
                self.store.apply("run-1", evidence=[evidence("new"), item])
            with self.assertRaises(KeyError):
                self.store.evidence("run-1", "new")
        cyclic = {}
        cyclic["cycle"] = cyclic
        for value in ({1: "bad key"}, {"tuple": (1,)}, {"object": object()}, cyclic,
                      {"infinity": float("inf")}):
            with self.subTest(value_type=type(value)), self.assertRaises(ValueError):
                self.store.apply("run-1", updates={"private": value})
        for kwargs in ({"updates": []}, {"events": {}}, {"events": [3]}, {"evidence": {}},
                       {"boards": {"blue": []}}, {"boards": {"green": {}}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.store.apply("run-1", **kwargs)
        self.assertEqual(self.store.snapshot("run-1"), before)

    def test_cursor_limit_and_audience_validation(self):
        for value in (-1, 1.0, True, None, "1", []):
            for field in ("after", "limit"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.store.events("run-1", **{field: value})
        for audience in ("red", "judge", "all", "", None, []):
            with self.subTest(audience=audience):
                with self.assertRaises(ValueError):
                    self.store.events("run-1", audience=audience)
                with self.assertRaises(ValueError):
                    self.store.evidence("run-1", "ev-1", audience=audience)
        self.assertEqual(self.store.events("run-1", after=10**100, limit=10**100),
                         {"events": [], "last_event_id": 0})

    def test_unknown_identifiers_and_invalid_teams_fail_closed(self):
        for operation in (
            lambda: self.store.snapshot("unknown"), lambda: self.store.apply("unknown"),
            lambda: self.store.events("unknown"), lambda: self.store.evidence("unknown", "ev-1"),
            lambda: self.store.board("unknown", "red"),
            lambda: self.store.evidence("run-1", "unknown"),
        ):
            with self.assertRaises(KeyError):
                operation()
        for team in ("judge_safe", "referee", "Red", None, []):
            with self.subTest(team=team), self.assertRaises(ValueError):
                self.store.board("run-1", team)
        for session_id in ("", None, 3):
            with self.subTest(session_id=session_id), self.assertRaises(ValueError):
                self.store.snapshot(session_id)

    def test_threads_produce_contiguous_per_session_sequences(self):
        workers, writes = 8, 20
        start = threading.Barrier(workers)

        def write(worker):
            start.wait(timeout=10)
            receipts = []
            for index in range(writes):
                marker = f"worker-{worker}-write-{index}"
                result = self.store.apply(
                    "run-1", updates={"phase": marker},
                    evidence=[evidence(marker)], events=[event(refs=[marker], data={"marker": marker})],
                )
                receipts.append((result["last_event_id"], result["phase"]))
            return receipts

        with ThreadPoolExecutor(max_workers=workers) as pool:
            receipts = [receipt for batch in pool.map(write, range(workers)) for receipt in batch]
        recorded = self.store.events("run-1", audience="referee_only", limit=workers * writes)["events"]
        self.assertEqual([item["id"] for item in recorded], list(range(1, workers * writes + 1)))
        self.assertEqual([item["sequence"] for item in recorded], list(range(1, workers * writes + 1)))
        self.assertEqual(dict(receipts), {item["id"]: item["data"]["marker"] for item in recorded})
        self.assertEqual(self.store.snapshot("run-1")["phase"], recorded[-1]["data"]["marker"])
        self.store.create(session("other-run"))
        self.store.apply("other-run", events=[event()])
        self.assertEqual(self.store.events("other-run")["events"][0]["id"], 1)

    def test_close_is_idempotent_and_serialized(self):
        self.store.close()
        self.store.close()
        for operation in (lambda: self.store.snapshot("run-1"), lambda: self.store.list_sessions(),
                          lambda: self.store.apply("run-1"), lambda: self.store.create(session("new")),
                          lambda: self.store.events("run-1"), lambda: self.store.board("run-1", "red"),
                          lambda: self.store.evidence("run-1", "ev-1")):
            with self.assertRaises(ValueError):
                operation()


class FileStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sessions.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(self.store.close)

    def test_reload_persists_all_records_and_resumes_sequence(self):
        self.store.create(session(boards={"red": {"tasks": ["scout"]}}))
        before = self.store.apply(
            "run-1", updates={"status": "paused", "budget": {"calls": 5}},
            evidence=[evidence("private", "blue_private")],
            events=[event(), event("blue_private", ["private"])],
            boards={"blue": {"tasks": ["monitor"]}},
        )
        old_events = self.store.events("run-1", audience="referee_only")
        old_evidence = self.store.evidence("run-1", "private", audience="blue_private")
        self.store.close()
        reloaded = Store(self.path)
        self.addCleanup(reloaded.close)
        self.assertEqual(reloaded.snapshot("run-1"), before)
        self.assertEqual(reloaded.events("run-1", audience="referee_only"), old_events)
        self.assertEqual(reloaded.evidence("run-1", "private", audience="blue_private"), old_evidence)
        self.assertEqual(reloaded.board("run-1", "blue"), {"tasks": ["monitor"]})
        self.assertEqual(reloaded.board("run-1", "red"), {"tasks": ["scout"]})
        with self.assertRaises(KeyError):
            reloaded.evidence("run-1", "private")
        reloaded.apply("run-1", events=[event()])
        self.assertEqual(reloaded.events("run-1", after=2)["events"][0]["id"], 3)

    def test_new_database_is_owner_only_and_uses_wal_and_foreign_keys(self):
        # Windows ignores POSIX permission bits; this assertion is about POSIX
        # creation mode, not a Windows ACL audit. Persistence checks run on both.
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.store.create(session())
        self.store.apply("run-1", evidence=[evidence()], events=[event(refs=["ev-1"])])
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists() and os.name != "nt":
                self.assertEqual(stat.S_IMODE(sidecar.stat().st_mode) & 0o077, 0)
        with closing(sqlite3.connect(self.path)) as inspection:
            self.assertEqual(inspection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(inspection.execute("PRAGMA foreign_key_check").fetchall(), [])
            inspection.execute("PRAGMA foreign_keys = ON")
            self.assertGreater(len(inspection.execute("PRAGMA foreign_key_list(event_evidence)").fetchall()), 0)
            with self.assertRaises(sqlite3.IntegrityError):
                inspection.execute(
                    "INSERT INTO event_evidence VALUES (?, ?, ?)", ("run-1", 1, "missing"),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                inspection.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?)", ("missing", 1, "judge_safe", json.dumps({})),
                )

    def test_independent_connections_serialize_sequence_and_atomic_state(self):
        self.store.create(session())
        other = Store(self.path)
        self.addCleanup(other.close)
        start = threading.Barrier(2)

        def write(arguments):
            store, worker = arguments
            start.wait(timeout=10)
            for index in range(30):
                marker = f"connection-{worker}-write-{index}"
                store.apply("run-1", updates={"phase": marker}, events=[event(data={"marker": marker})])

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(write, [(self.store, 1), (other, 2)]))
        events = self.store.events("run-1")["events"]
        self.assertEqual([item["id"] for item in events], list(range(1, 61)))
        self.assertEqual(self.store.snapshot("run-1"), other.snapshot("run-1"))
        self.assertEqual(self.store.snapshot("run-1")["phase"], events[-1]["data"]["marker"])

    def test_page_cutoff_is_stable_when_another_connection_commits_during_read(self):
        self.store.create(session())
        self.store.apply("run-1", events=[event()])
        other = Store(self.path)
        self.addCleanup(other.close)
        read_snapshot = self.store._snapshot

        def concurrent_commit(session_id):
            captured = read_snapshot(session_id)
            other.apply(session_id, events=[event()])
            return captured

        with patch.object(self.store, "_snapshot", side_effect=concurrent_commit):
            page = self.store.events("run-1")
        self.assertEqual(page["last_event_id"], 1)
        self.assertEqual([item["id"] for item in page["events"]], [1])
        following = self.store.events("run-1", after=page["last_event_id"])
        self.assertEqual([item["id"] for item in following["events"]], [2])
        self.assertEqual(following["last_event_id"], 2)


if __name__ == "__main__":
    unittest.main()
