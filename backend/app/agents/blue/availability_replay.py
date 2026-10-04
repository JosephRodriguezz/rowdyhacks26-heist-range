"""Credential-free deterministic fixture replay. Never runs traffic or tools."""
import asyncio
import json
from pathlib import Path

from .availability import observe_availability


def main():
    context = json.loads((Path(__file__).parent / "fixtures" / "http-pressure.json").read_text())
    context["data_source"] = "fixture"
    result = asyncio.run(observe_availability(context))
    print(json.dumps({"schema": "range.blue.availability.replay/v1", "mode": "fixture_replay",
                      "live_execution": False, "arrest_permitted": False, "blue": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
