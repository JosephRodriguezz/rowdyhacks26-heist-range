"""Run the reproducible local integration, or serve presenter controls."""

import argparse
import json
import os
from pathlib import Path
import threading
import uuid

from .api import CoreHTTPServer
from .service import CoreService


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local preparation core; fixture decisions are not live AI evidence.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run", help="Run the live local-lab integration with labeled fixture decisions")
    run.add_argument("--db", default=":memory:")
    run.add_argument("--mode", choices=("fixture", "model"), default="fixture")
    run.add_argument("--allow-remote-model", action="store_true")
    serve = subcommands.add_parser("serve", help="Serve loopback presenter API; HEIST_CORE_TOKEN is required")
    serve.add_argument("--db", default=".core-state/core.sqlite3")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--allow-remote-model", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run" and args.mode == "model" and not args.allow_remote_model:
        parser.error("model mode requires --allow-remote-model")
    if args.db != ":memory:":
        Path(args.db).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HEIST_CORE_TOKEN") if args.command == "serve" else None
    if args.command == "serve" and (not token or len(token) < 16):
        parser.error("set HEIST_CORE_TOKEN to a strong presenter credential of at least 16 characters; it is never printed")
    try:
        with CoreService(args.db, allow_remote_model=args.allow_remote_model) as service:
            if args.command == "run":
                request_prefix = "cli-" + uuid.uuid4().hex[:16]
                snapshot = service.create(planner_mode=args.mode, action_id=request_prefix + "-create")
                service.action(snapshot["id"], "start", action_id=request_prefix + "-start")
                final = service.wait(snapshot["id"], timeout=service.limits.wall_seconds + 5)
                print(json.dumps({"preparation_slice": True, "target_execution": "local_lab_http",
                    "agent_decisions": "scripted_fixture" if args.mode == "fixture" else "model",
                    "model_performance_measured": False, "session": final}, indent=2))
                return 0 if final["status"] == "completed" else 1
            with CoreHTTPServer(service, token=token, port=args.port) as api:
                print("Core presenter API: " + api.origin, flush=True)
                print("Authenticated judge-safe views only; no remote model call without explicit opt-in.", flush=True)
                threading.Event().wait()
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError):
        parser.exit(2, "Core could not start: check database ownership, port, and credential configuration.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
