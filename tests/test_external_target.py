from __future__ import annotations

import contextlib
import hashlib
import io
import itertools
import json
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from red.evaluation.evaluator import InvalidTarget
from red.prototype.actions import FixedTargetRegistry
from red.prototype.cli import main, make_parser
from red.prototype.lab import LabState, LocalBankServer
from red.prototype.runner import PrototypeRunner, RunOptions


def pinned_default_report(runner=PrototypeRunner) -> str:
    """Pin only nondeterministic IDs, clocks and opaque tokens; use real HTTP."""
    counter = itertools.count(1)
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=next(counter) << 96)))
        stack.enter_context(patch("time.monotonic", return_value=100.0))
        stack.enter_context(patch("secrets.token_hex", return_value="0123456789abcdef"))
        clock = stack.enter_context(patch("red.prototype.board.datetime"))
        clock.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return json.dumps(runner(RunOptions()).run().to_dict(), indent=2, ensure_ascii=False) + "\n"


class ExternalTargetTests(unittest.TestCase):
    def test_default_report_bytes_match_pre_av05_runner(self):
        # Captured from HEAD's runner with the same pinned clocks/IDs and real HTTP.
        # Updated once, deliberately, for the fixtures-only ordinary-access-during-load
        # check: RunReport gained an always-populated `ordinary_access` field (same
        # pattern as `availability`), which changes every report's bytes, including this
        # one. Re-pin again only for another equally deliberate, reported shape change.
        self.assertEqual(hashlib.sha256(pinned_default_report().encode()).hexdigest(),
                         "c6acc0f9b61a5ff519fc17e7b53231d18c968611a0683db732a2fc1285f9e001")
        self.assertIsNone(make_parser().parse_args(["run"]).target_origin)

    def test_external_vault_run_uses_serving_state_and_keeps_server_open(self):
        with LocalBankServer(LabState("access_control")) as server:
            with patch("red.prototype.runner.LocalBankServer", wraps=LocalBankServer) as factory, \
                    patch("red.prototype.runner.LabState", side_effect=AssertionError("must not construct state")):
                report = PrototypeRunner(RunOptions(scenario_id="access_control",
                                                   external_target_origin=server.origin)).run()
                factory.assert_not_called()
            self.assertEqual(report.verdict, "achieved")
            self.assertTrue(server.state.read_log)
            self.assertTrue(server.thread.is_alive())
            self.assertIs(LocalBankServer.running_at(server.origin), server)
            self.assertFalse(report.evaluation_private["reset_verified"])
            self.assertIsNone(report.evaluation_private["reset_receipt"])
            self.assertEqual(report.metadata["target_lifecycle"], "caller_owned_local_mock")

    def test_cli_external_availability_uses_real_http(self):
        with LocalBankServer(LabState("availability")) as server, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["run", "--scenario", "availability", "--target-origin", server.origin]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["availability"]["verdict"], "achieved")
            self.assertTrue(any(row["label"] == "degraded" for row in server.state.status_log))
            self.assertTrue(server.thread.is_alive())

    def test_invalid_origins_have_same_registry_rejection(self):
        for origin in ("http://example.com:80", "http://localhost:80", "https://127.0.0.1:80",
                       "http://127.0.0.1", "http://127.0.0.1:bad", "http://127.0.0.1:70000",
                       "http://127.0.0.1:80/path", "http://127.0.0.1:80?q=x", "http://127.0.0.1:80#x"):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError) as expected:
                    FixedTargetRegistry(origin)
                with self.assertRaises(ValueError) as actual:
                    PrototypeRunner(RunOptions(external_target_origin=origin)).run()
                self.assertEqual(str(actual.exception), str(expected.exception))

    def test_unregistered_or_closed_server_rejected(self):
        with LocalBankServer(LabState("clean")) as server:
            origin = server.origin
        with self.assertRaisesRegex(ValueError, "already-running LocalBankServer"):
            PrototypeRunner(RunOptions(external_target_origin=origin)).run()

    def test_scenario_and_seed_must_match(self):
        with LocalBankServer(LabState("clean", seed=17)) as server:
            for options in (RunOptions(external_target_origin=server.origin),
                            RunOptions(scenario_id="availability", seed=17, external_target_origin=server.origin)):
                with self.assertRaisesRegex(ValueError, "scenario and seed"):
                    PrototypeRunner(options).run()

    def test_reused_evaluation_state_rejected(self):
        with LocalBankServer(LabState("clean")) as server:
            options = RunOptions(external_target_origin=server.origin)
            PrototypeRunner(options).run()
            with self.assertRaisesRegex(ValueError, "fresh evaluation state"):
                PrototypeRunner(options).run()

    def test_cli_separate_process_limitation_is_explicit(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit) as exit_info:
            main(["run", "--target-origin", "http://127.0.0.1:1"])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("cross-process bank integration is not supported", errors.getvalue())

    def test_external_preflight_failure_does_not_close_server(self):
        with LocalBankServer(LabState("clean")) as server:
            with patch("red.prototype.runner.preflight_local_target", side_effect=InvalidTarget("unhealthy")) as preflight:
                report = PrototypeRunner(RunOptions(external_target_origin=server.origin)).run()
            self.assertEqual(report.verdict, "inconclusive")
            self.assertIs(preflight.call_args.args[1], server.state)
            self.assertEqual(preflight.call_args.args[0], server.origin)
            self.assertTrue(server.thread.is_alive())

    def test_simulated_defense_changes_actual_external_state(self):
        with LocalBankServer(LabState("access_control")) as server:
            report = PrototypeRunner(RunOptions(scenario_id="access_control", external_target_origin=server.origin,
                                               defense_family="access_control", defense_after_actions=0)).run()
            self.assertEqual(report.verdict, "not_achieved")
            self.assertNotIn("access_control", server.state.active_flaws)
            self.assertTrue(report.evaluation_private["simulated_defense"]["applied"])


if __name__ == "__main__":
    unittest.main()
