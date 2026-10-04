"""Private one-shot Blue observer for the registered disposable bank run."""
import asyncio
from dataclasses import asdict
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.agents.blue.availability import AvailabilityPolicy, observe_availability


POLICY = AvailabilityPolicy(
    baseline_rps=1, rate_multiplier=2, min_requests=4,
    min_backend_samples=2, latency_limit_ms=400, inflight_threshold=2,
    suspect_source_rps=4, limit_rps=1, burst=1, ttl_seconds=3,
    max_proposals=1,
)


def main():
    raw = sys.stdin.buffer.read(16_385)
    if len(raw) > 16_384:
        raise ValueError("Blue telemetry exceeds its bound")
    context = json.loads(raw)
    if context.get("target_id") != "bank-lab" or context.get("data_source") != "live":
        raise ValueError("Blue telemetry is not scoped to the disposable bank")
    context["policy"] = asdict(POLICY)
    result = asyncio.run(observe_availability(context))
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("Disposable Blue observation failed.\n")
        raise SystemExit(1)
