"""Build a blue incident report from a run fixture.

Run from backend/:
    python -m app.agents.blue.report [--format json] [--out FILE]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .detection import PRIVATE_ORDERS_POLICY, detect_suspicious_access
from .incident import build_incident_report, render_markdown

ROOT = Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", type=Path, default=ROOT / "shared" / "fixtures" / "demo-run.json")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--out", type=Path, help="write the report to this file instead of printing it")
    args = parser.parse_args(argv)

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    result = detect_suspicious_access(fixture["telemetry"], PRIVATE_ORDERS_POLICY)
    report = build_incident_report(
        assessment_id=fixture["snapshot"]["id"], data_source=fixture["snapshot"]["data_source"],
        telemetry=fixture["telemetry"], alerts=result.alerts, events=fixture["events"],
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if report is None:
        print("No incident: the telemetry contains no suspicious access.")
        return 0
    text = json.dumps(report, indent=2) if args.format == "json" else render_markdown(report)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
