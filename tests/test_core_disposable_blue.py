"""Blue helper remains importable and scoped when launched from its script path."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "observe-disposable-blue.py"


class DisposableBlueHelperTests(unittest.TestCase):
    def test_live_bank_window_proposes_only_the_fixed_source_limit(self):
        source = {"source_ref": "load-demo", "requests": 4, "backend_requests": 4,
                  "server_errors": 0, "denied_requests": 0, "inflight": 4}
        window = {"window_id": "window-1", "seconds": 1, "requests": 4,
                  "backend_requests": 4, "server_errors": 0, "denied_requests": 0,
                  "inflight": 4, "latency_p95_ms": 1, "data_loss": False,
                  "sources": [source]}
        context = {"assessment_id": "disposable-test", "target_id": "bank-lab",
                   "target_version": "baseline-v1", "data_source": "live",
                   "window": window}
        result = subprocess.run([sys.executable, str(HELPER)], input=json.dumps(context),
                                capture_output=True, text=True, cwd=ROOT, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["assessment"], "suspected_http_flood")
        self.assertEqual(len(output["defense_proposals"]), 1)
        proposal = output["defense_proposals"][0]
        self.assertEqual(proposal["target_id"], "bank-lab")
        self.assertEqual(proposal["parameters"], {"source_ref": "load-demo",
                         "rate_per_second": 1, "burst": 1, "ttl_seconds": 3})

        context["target_id"] = "bank-local"
        rejected = subprocess.run([sys.executable, str(HELPER)], input=json.dumps(context),
                                  capture_output=True, text=True, cwd=ROOT, timeout=3)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, "")


if __name__ == "__main__":
    unittest.main()
