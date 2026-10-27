import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.core import run_guided_access_control


class GuidedAccessControlTests(unittest.TestCase):
    def test_guided_run_completes_golden_scenario(self):
        result = run_guided_access_control(assessment_id="guided-test-1")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["target_version"], "lab-v2")
        self.assertEqual(result["summary"], {
            "finding": "verified", "adaptation": "still_exposed", "containment": "applied",
            "fix": "known_good_fallback", "retest": "verified",
        })
        retest = next(event for event in result["events"] if event["type"] == "retest.completed")
        self.assertTrue(retest["data"]["all_checks_passed"])
        self.assertEqual(retest["data"]["referee"]["verdict"], "rejected")
        self.assertNotIn("token", json.dumps(result).lower())

    def test_guided_run_persists_append_only_event_trail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "assessment.sqlite3")
            result = run_guided_access_control(path, assessment_id="guided-test-2")
            connection = sqlite3.connect(path)
            try:
                status = connection.execute(
                    "SELECT status, target_version FROM assessments WHERE assessment_id = ?",
                    ("guided-test-2",),
                ).fetchone()
                event_count = connection.execute(
                    "SELECT COUNT(*) FROM assessment_events WHERE assessment_id = ?",
                    ("guided-test-2",),
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(status, ("completed", "lab-v2"))
            self.assertEqual(event_count, len(result["events"]))
            self.assertEqual([event["id"] for event in result["events"]],
                             list(range(1, len(result["events"]) + 1)))


if __name__ == "__main__":
    unittest.main()
