"""Run the reproducible local integration, or serve presenter controls."""

import argparse
import json
import os
import secrets
import shutil
from pathlib import Path
import threading
import uuid
import webbrowser

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
    serve.add_argument("--availability-fixture", action="store_true", help="Register the disposable availability fixture; requires Node and bank dependencies")
    availability = subcommands.add_parser("availability", help="Run core/Red/Blue against an owned disposable bank fixture only")
    availability.add_argument("--db", default=":memory:")
    availability.add_argument("--node", help="Trusted local Node executable; never a target destination")
    demo = subcommands.add_parser("demo", help="Open the local availability demo; no Omar arena or deployed bank required")
    demo.add_argument("--db", default=".core-state/demo.sqlite3")
    demo.add_argument("--port", type=int, default=8765)
    demo.add_argument("--node", help="Trusted local Node executable")
    demo.add_argument("--no-browser", action="store_true", help="Use private HEIST_CORE_TOKEN and open the displayed URL manually")
    args = parser.parse_args(argv)
    if args.command == "run" and args.mode == "model" and not args.allow_remote_model:
        parser.error("model mode requires --allow-remote-model")
    if args.db != ":memory:":
        Path(args.db).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HEIST_CORE_TOKEN") if args.command == "serve" else None
    if args.command == "serve" and (not token or len(token) < 16):
        parser.error("set HEIST_CORE_TOKEN to a strong presenter credential of at least 16 characters; it is never printed")
    if args.command == "demo":
        token = os.environ.get("HEIST_CORE_TOKEN") or secrets.token_urlsafe(32)
        if args.no_browser and not os.environ.get("HEIST_CORE_TOKEN"):
            parser.error("--no-browser requires private HEIST_CORE_TOKEN (32-128 URL-safe characters)")
        if not (args.node or shutil.which("node")):
            parser.error("Node is required; install Node or pass --node")
        if not (Path(__file__).resolve().parents[1] / "apps/bank-lab/node_modules/@electric-sql/pglite").exists():
            parser.error("Install the locked bank dependencies first: cd apps/bank-lab; pnpm install --frozen-lockfile --ignore-scripts")
    try:
        from .availability import AvailabilityBridge
        factory = (lambda assessment_id: AvailabilityBridge(assessment_id, node=args.node)) if args.command in ("availability", "demo") else None
        with CoreService(args.db, allow_remote_model=getattr(args, "allow_remote_model", False),
                         enable_availability_fixture=args.command in ("availability", "demo") or getattr(args, "availability_fixture", False),
                         availability_bridge_factory=factory) as service:
            if args.command in ("run", "availability"):
                request_prefix = "cli-" + uuid.uuid4().hex[:16]
                mode = getattr(args, "mode", "fixture")
                snapshot = service.create(target_id="availability-fixture" if args.command == "availability" else "bank-local",
                                          planner_mode=mode, action_id=request_prefix + "-create")
                service.action(snapshot["id"], "start", action_id=request_prefix + "-start")
                final = service.wait(snapshot["id"], timeout=service.limits.wall_seconds + 5)
                print(json.dumps({"preparation_slice": True, "target_execution": "local_lab_http",
                    "agent_decisions": "scripted_fixture" if mode == "fixture" else "model",
                    "model_performance_measured": False, "session": final}, indent=2))
                return 0 if final["status"] == "completed" and (args.command != "availability" or final["verdict"]["result"] == "achieved") else 1
            with CoreHTTPServer(service, token=token, port=args.port, demo=args.command == "demo") as api:
                print("Core presenter API: " + api.origin, flush=True)
                print("Authenticated judge-safe views only; no remote model call without explicit opt-in.", flush=True)
                if args.command == "demo":
                    print("Rowdy Bank disposable demo: " + api.origin + "/demo", flush=True)
                    print("Press Ctrl+C to stop core and clean up any active target. Evidence is retained.", flush=True)
                    if not args.no_browser:
                        # Fragment never reaches HTTP logs. The page erases it
                        # and retains it in origin/tab-scoped sessionStorage.
                        webbrowser.open(api.origin + "/demo#presenter=" + token)
                threading.Event().wait()
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError):
        parser.exit(2, "Core could not start: check database ownership, port, and credential configuration.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
