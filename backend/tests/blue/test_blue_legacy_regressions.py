"""Bounded legacy validation and report CLI regressions; no availability execution."""

import asyncio
from contextlib import redirect_stdout
from datetime import timedelta
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from app.agents.blue import ContextError, PatchManifestError, observe, parse_context, parse_patch_manifest
from app.agents.blue.detection import parse_utc_timestamp
from app.agents.blue.report import main
from blue_test_helpers import load_shared, log
from test_blue_adversarial import applied, context, manifest_data
from test_blue_incident import PATCH_APPLIED, retest


class LegacyValidation(unittest.TestCase):
    def test_full_z_timestamps_remain_utc_aware(self):
        for stamp in ("2026-09-30T15:00:04Z", "2026-09-30T15:00:04.123456Z",
                      "2026-09-30T15:00:04,5Z", "20260930T150004Z", "2026-09-30 15:00:04Z"):
            with self.subTest(stamp=stamp):
                parsed = parse_utc_timestamp(stamp)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_date_only_naive_and_non_utc_timestamps_fail_before_tools_run(self):
        class UnusedTools:
            def cancelled(self):
                raise AssertionError("invalid context reached tools")

        for stamp in ("2026-09-30Z", "20260930Z", "2026-W40-3Z", "2026-09-30",
                      "2026-09-30T15:00:04", "2026-09-30T15:00:04+01:00",
                      "2026-09-30T15:00:04-05:00", "2026-09-30T15:00:04+01:00Z"):
            with self.subTest(stamp=stamp):
                self.assertIsNone(parse_utc_timestamp(stamp))
                with self.assertRaises(ContextError):
                    asyncio.run(observe(context([], generated_at=stamp), UnusedTools()))

    def test_every_nonfinite_budget_is_rejected_even_without_telemetry(self):
        for key in ("max_steps", "max_requests", "timeout_seconds"):
            for amount in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(key=key, amount=amount):
                    with self.assertRaises(ContextError) as caught:
                        parse_context(context([], budgets={key: amount}))
                    self.assertEqual(str(caught.exception), f"budget {key} must be finite")

    def test_large_integer_budgets_do_not_require_float_conversion(self):
        parsed = parse_context(context([], budgets={"max_steps": 10**1000}))
        self.assertEqual(parsed.budgets["max_steps"], 10**1000)

    def test_context_enum_errors_are_typed_and_never_echo_values(self):
        for value in (["ENUM-MARKER"], {"ENUM-MARKER": 1}, {"ENUM-MARKER"}, None, 7, "ENUM-MARKER"):
            cases = (context([], data_source=value),
                     context([], previous_defenses=[applied(type=value)]),
                     context([], previous_defenses=[applied(data_source=value)]),
                     context([], previous_defenses=[applied(data={**applied()["data"], "action_type": value})]))
            for ctx in cases:
                with self.subTest(value=value, ctx=ctx):
                    with self.assertRaises(ContextError) as caught:
                        parse_context(ctx)
                    self.assertNotIn("ENUM-MARKER", str(caught.exception))

    def test_manifest_enum_errors_are_typed_and_static(self):
        for value in (["ENUM-MARKER"], {"ENUM-MARKER": 1}, {"ENUM-MARKER"}, None, 7, "ENUM-MARKER"):
            for field, message in (("status", "status must be draft or ready"),
                                   ("origin", "origin must be generated or known_good_fallback"),
                                   ("expected", "regression check expectation must be allowed, denied, or unchanged")):
                data = manifest_data()
                if field == "expected":
                    data["regression_checks"][0].update(id="ID-MARKER", expected=value)
                else:
                    data[field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(PatchManifestError) as caught:
                        parse_patch_manifest(data)
                    self.assertEqual(str(caught.exception), message)


class LegacyReportCLI(unittest.TestCase):
    def render_fixture(self, events, output_format="json"):
        fixture = {"snapshot": {"id": "run-1", "data_source": "fixture"},
                   "telemetry": [log("r1", "alice", "bob")], "events": events}
        output = io.StringIO()
        with patch.object(Path, "read_text", return_value=json.dumps(fixture)), redirect_stdout(output):
            self.assertEqual(main(["--fixture", "fixture.json", "--format", output_format]), 0)
        return output.getvalue()

    def test_cli_incomplete_pass_is_unverified_in_json_and_markdown(self):
        report = json.loads(self.render_fixture([PATCH_APPLIED, retest("passed", [])]))
        self.assertEqual(report["status"], "awaiting_retest")
        self.assertIsNone(report["times"]["fix_verified"])
        self.assertEqual(report["respond"]["mitigation"][0]["outcome"], "applied, awaiting retest")
        markdown = self.render_fixture([PATCH_APPLIED, retest("passed", [])], "markdown")
        self.assertNotIn("applied, retest passed", markdown)
        self.assertIn("| Fix verified | N/A | N/A |", markdown)

    def test_cli_preserves_fixture_label_even_when_snapshot_claims_live(self):
        fixture = load_shared("shared/fixtures/demo-run.json")
        fixture["snapshot"]["data_source"] = "live"
        output = io.StringIO()
        with patch.object(Path, "read_text", return_value=json.dumps(fixture)), redirect_stdout(output):
            self.assertEqual(main(["--fixture", "fixture.json", "--format", "json"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["data_source"], "fixture")
        self.assertIn("fixture data", " ".join(report["limitations"]))

    def test_cli_no_alerts_does_not_claim_no_incident(self):
        fixture = {"snapshot": {"id": "run-1", "data_source": "fixture"}, "telemetry": [], "events": []}
        output = io.StringIO()
        with patch.object(Path, "read_text", return_value=json.dumps(fixture)), redirect_stdout(output):
            self.assertEqual(main(["--fixture", "fixture.json"]), 0)
        self.assertIn("No suspicious access detected in the supplied fixture telemetry", output.getvalue())
        self.assertNotIn("No incident", output.getvalue())


if __name__ == "__main__":
    unittest.main()
