"""Operator CLI. Model network access is behind an explicit flag."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path
from typing import Any

from .actions import TARGET_ID, ActionExecutor, ActionRejected, FixedTargetRegistry
from .board import BudgetLedger, RedBoard
from .domain import ActionProposal, LoadProfile, RunLimits
from .lab import DEFENSE_MODES, SCENARIOS, LabState, LocalBankServer
from .providers import OpenAIResponsesProvider, ProviderError
from .replay import ReplayError, load_recorded_trace
from .runner import PrototypeRunner, RunOptions


def _limits(args: argparse.Namespace) -> RunLimits:
    return RunLimits(
        action_calls=args.max_actions,
        model_calls=args.max_model_calls,
        wall_seconds=args.max_seconds,
        request_timeout_seconds=args.request_timeout,
        response_bytes=args.max_response_bytes,
        model_timeout_seconds=args.model_timeout,
        max_agent_turns=args.max_turns,
    )


def _load_profile(args: argparse.Namespace) -> LoadProfile:
    return LoadProfile(
        max_requests=args.load_max_requests,
        concurrency=args.load_concurrency,
        duration_seconds=args.load_duration_seconds,
        request_timeout_seconds=args.load_timeout,
    )


def _run_once(args: argparse.Namespace, *, scenario: str | None = None,
              defense: str | None = None) -> dict[str, Any]:
    mode = getattr(args, "mode", "deterministic_baseline")
    provider = None
    if mode == "model":
        if not args.allow_remote_model:
            raise ProviderError("model mode is disabled unless --allow-remote-model is passed explicitly")
        provider = OpenAIResponsesProvider()
    report = PrototypeRunner(
        RunOptions(
            scenario_id=scenario or args.scenario,
            seed=args.seed,
            mode=mode,
            limits=_limits(args),
            defense_family=(defense if scenario is not None else args.simulated_defense),
            defense_after_actions=args.defense_after_actions,
            load_profile=_load_profile(args),
            external_target_origin=getattr(args, "target_origin", None),
        ),
        provider=provider,
    ).run()
    return report.to_dict()


def _emit(value: Any, report_path: str | None = None) -> None:
    rendered = json.dumps(value, indent=2, ensure_ascii=False)
    if report_path:
        path = Path(report_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _add_run_options(parser: argparse.ArgumentParser, *, model: bool = True) -> None:
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="clean")
    parser.add_argument("--seed", type=int, default=26)
    if model:
        parser.add_argument("--mode", choices=("deterministic_baseline", "model"), default="deterministic_baseline")
        parser.add_argument("--allow-remote-model", action="store_true",
                            help="explicitly permit the configured provider to receive synthetic lab observations")
    parser.add_argument("--max-actions", type=int, default=60)
    parser.add_argument("--max-model-calls", type=int, default=30)
    parser.add_argument("--max-seconds", type=float, default=180.0)
    parser.add_argument("--request-timeout", type=float, default=2.0)
    parser.add_argument("--model-timeout", type=float, default=30.0)
    parser.add_argument("--max-response-bytes", type=int, default=16_384)
    parser.add_argument("--max-turns", type=int, default=18)
    parser.add_argument("--simulated-defense", choices=DEFENSE_MODES)
    parser.add_argument("--defense-after-actions", type=int, default=4)
    parser.add_argument("--load-max-requests", type=int, default=24,
                        help="availability scenario: max requests in the bounded load profile")
    parser.add_argument("--load-concurrency", type=int, default=6,
                        help="availability scenario: concurrent requests in the bounded load profile")
    parser.add_argument("--load-duration-seconds", type=float, default=4.0,
                        help="availability scenario: max wall-clock duration of the bounded load profile")
    parser.add_argument("--load-timeout", type=float, default=1.0,
                        help="availability scenario: per-request timeout inside the bounded load profile")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heist-red", description="Loopback-only Red Team preparation prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run one target scenario")
    _add_run_options(run_parser)
    run_parser.add_argument("--target-origin", help="already-running HTTP origin on 127.0.0.1; requires a prototype LocalBankServer in this process")
    run_parser.add_argument("--report", help="optional path for a local JSON run record")

    eval_parser = subparsers.add_parser("evaluate", help="run the deterministic baseline across the scenario set")
    _add_run_options(eval_parser, model=False)
    eval_parser.add_argument("--report", help="optional path for a local JSON evaluation record")

    serve_parser = subparsers.add_parser("serve", help="serve the synthetic target on loopback for inspection")
    serve_parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="clean")
    serve_parser.add_argument("--seed", type=int, default=26)
    serve_parser.add_argument("--port", type=int, default=8765)

    replay_parser = subparsers.add_parser("replay", help="display a saved run record without contacting its target")
    replay_parser.add_argument("--from", dest="source_path", required=True, help="path to a JSON run report")

    probe_parser = subparsers.add_parser(
        "probe-target",
        help="AV-05: register one additional real target and reach it with a single read-only action, "
             "through the same registry and action boundary every scenario uses",
    )
    probe_parser.add_argument("--target-id", required=True,
                               help=f"id to register for this target; must not be '{TARGET_ID}' (reserved)")
    probe_parser.add_argument("--origin", required=True,
                               help="the target's http origin on 127.0.0.1, e.g. http://127.0.0.1:3000")
    probe_parser.add_argument("--path", default="/api/health")
    probe_parser.add_argument("--method", choices=("GET", "POST"), default="GET")
    probe_parser.add_argument("--capability", choices=("request_api", "read_page"), default="request_api",
                               help="only these two capabilities are available on a non-bank-local target today")
    probe_parser.add_argument("--request-timeout", type=float, default=2.0)
    probe_parser.add_argument("--max-response-bytes", type=int, default=16_384)
    probe_parser.add_argument("--report", help="optional path for a local JSON evidence record")

    subparsers.add_parser("scenarios", help="list local scenario labels")
    return parser


def _serve(args: argparse.Namespace) -> int:
    if not (0 < args.port < 65_536):
        raise ValueError("port must be between 1 and 65535")
    state = LabState(args.scenario, seed=args.seed)
    server = LocalBankServer(state, port=args.port).start()
    print(f"Local synthetic bank: {server.origin}/")
    print("Bound to 127.0.0.1. Press Ctrl-C to stop.")
    stopped = threading.Event()
    try:
        while not stopped.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


def _probe_target(args: argparse.Namespace) -> dict[str, Any]:
    """Reach one additional registered target through the real action boundary.

    This is a read-only reachability check, not the availability scenario: the load
    test and the bank-local login flow still only work against this prototype's own
    lab (see AVAILABILITY_SCENARIO.md and DIEGO_AVAILABILITY_ASK.md for why). What
    this proves is narrower and already true today: the runner resolves a registered
    target id rather than taking an arbitrary URL, an unregistered id or a
    non-127.0.0.1 origin is refused by the same registry every scenario uses, and a
    `request_api`/`read_page` action against a real external process returns real
    evidence through the same validated, budgeted, bounded dispatch path.
    """
    if args.target_id == TARGET_ID:
        raise ValueError(f"'{TARGET_ID}' is the reserved bank-local id; choose another target id")
    registry = FixedTargetRegistry(extra_targets={args.target_id: args.origin})
    state = LabState("clean", seed=26)
    board = RedBoard(session_id="probe-" + args.target_id)
    limits = RunLimits(request_timeout_seconds=args.request_timeout, response_bytes=args.max_response_bytes)
    budget = BudgetLedger(limits)
    executor = ActionExecutor(
        registry=registry, state=state, limits=limits, budget=budget, board=board,
        max_response_bytes=args.max_response_bytes,
    )
    task = board.add_task("scout", f"Probe registered target {args.target_id}", status="queued")
    board.claim_task(task.task_id, "probe-target")
    proposal = ActionProposal(capability=args.capability, target_id=args.target_id, path=args.path, method=args.method)
    try:
        result = executor.execute(proposal, role="scout", task_id=task.task_id)
        board.finish_task(task.task_id, "completed")
    except ActionRejected as exc:
        board.finish_task(task.task_id, "yielded")
        return {"target_id": args.target_id, "origin": args.origin, "rejected": str(exc)}
    return {"target_id": args.target_id, "origin": args.origin, "evidence": result.evidence.public_dict()}


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scenarios":
            _emit({"target_kind": "local_mock", "scenarios": sorted(SCENARIOS)})
            return 0
        if args.command == "serve":
            return _serve(args)
        if args.command == "replay":
            _emit(load_recorded_trace(args.source_path))
            return 0
        if args.command == "run":
            report = _run_once(args)
            _emit(report, args.report)
            return 0 if report["verdict"] != "inconclusive" else 2
        if args.command == "probe-target":
            result = _probe_target(args)
            _emit(result, args.report)
            return 0 if "rejected" not in result else 2
        if args.command == "evaluate":
            scenarios = sorted(SCENARIOS)
            reports = []
            for scenario in scenarios:
                defense = {"defense_alternative": "access_control", "all_paths_blocked": "all",
                           "expanded_defense_alternative": "mass_assignment"}.get(scenario)
                reports.append(_run_once(args, scenario=scenario, defense=defense))
            suite = {
                "suite_mode": "deterministic_baseline",
                "source_mode": "local_mock",
                "cases": reports,
                "note": "This baseline sweep does not measure model adaptation or Blue-team capability.",
            }
            _emit(suite, args.report)
            return 0
    except (ProviderError, ReplayError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    sys.exit(main())
