"""Blue patch manifest and ownership-patch proposal tests. Run from backend/: python -m unittest discover -s tests/blue -v"""

from dataclasses import replace
import json
from pathlib import Path
import unittest

from app.agents.blue import (
    APPLY_PATCH,
    PRIVATE_ORDERS_POLICY,
    REMEDIATION,
    PatchManifestError,
    detect_suspicious_access,
    load_patch_manifest,
    parse_patch_manifest,
    propose_ownership_patch,
)
from blue_test_helpers import ROOT, load_shared, log, secret_keys

MANIFEST_PATH = ROOT / "defenses/patches/ownership-fix-001/manifest.json"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "patches"


def manifest_data():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def alerts_for(*records):
    return detect_suspicious_access(list(records), PRIVATE_ORDERS_POLICY).alerts


class ShippedManifest(unittest.TestCase):
    def test_ownership_fix_loads_as_a_labeled_draft(self):
        manifest = load_patch_manifest("ownership-fix-001")
        self.assertEqual(manifest.status, "draft")
        self.assertFalse(manifest.ready)
        self.assertEqual(manifest.origin, "known_good_fallback")
        self.assertEqual(manifest.base_version, "lab-v1")
        self.assertEqual(manifest.policy_id, PRIVATE_ORDERS_POLICY.id)
        ids = {check.id for check in manifest.regression_checks}
        self.assertLessEqual({"unauthorized_access", "owner_access", "anonymous_access", "protected_control"}, ids)


class ManifestValidation(unittest.TestCase):
    def assertRejected(self, change, message=None):
        data = manifest_data()
        change(data)
        with self.assertRaises(PatchManifestError) as caught:
            parse_patch_manifest(data)
        if message:
            self.assertIn(message, str(caught.exception))

    def test_rejects_missing_fields_and_unknown_values(self):
        self.assertRejected(lambda d: d.pop("base_version"), "missing")
        self.assertRejected(lambda d: d.update(origin="copied_from_forum"), "origin")
        self.assertRejected(lambda d: d.update(status="shipped"), "status")
        self.assertRejected(lambda d: d.update(patch_id="Ownership Fix"), "patch_id")

    def test_ready_patch_needs_files_and_diff(self):
        self.assertRejected(lambda d: d.update(status="ready"), "ready")
        self.assertRejected(lambda d: d.update(status="ready", allowed_files=["cyber_range/app.py"]), "ready")

    def test_file_scope_stays_inside_the_repository(self):
        for bad in ("/etc/passwd", "../outside.py", "cyber_range\\app.py", "C:/lab/app.py", ""):
            with self.subTest(path=bad):
                self.assertRejected(lambda d, bad=bad: d.update(allowed_files=[bad]), "allowed file")
        self.assertRejected(lambda d: d.update(diff_file="../fix.diff"), "diff_file")
        self.assertRejected(lambda d: d.update(diff_file="nested/fix.diff"), "diff_file")

    def test_checks_must_cover_both_sides_of_the_fix(self):
        self.assertRejected(lambda d: d.update(regression_checks=[c for c in d["regression_checks"]
                                                                  if c["id"] != "owner_access"]), "owner_access")
        self.assertRejected(lambda d: d["regression_checks"].append(dict(d["regression_checks"][0])), "unique")
        self.assertRejected(lambda d: d["regression_checks"][0].update(expected="probably"), "expectation")

    def test_load_refuses_path_tricks_and_mismatches(self):
        with self.assertRaises(PatchManifestError):
            load_patch_manifest("../ownership-fix-001")
        with self.assertRaisesRegex(PatchManifestError, "folder"):
            load_patch_manifest("mismatched-id", FIXTURES_DIR)
        with self.assertRaisesRegex(PatchManifestError, "missing"):
            load_patch_manifest("missing-diff", FIXTURES_DIR)
        self.assertTrue(load_patch_manifest("ready-with-diff", FIXTURES_DIR).ready)


class OwnershipPatchProposal(unittest.TestCase):
    def setUp(self):
        self.manifest = load_patch_manifest("ownership-fix-001")
        self.fixture = load_shared("shared/fixtures/demo-run.json")
        self.contract = load_shared("shared/contracts/v1.json")

    def test_fixture_exposure_gets_a_patch_proposal(self):
        alerts = alerts_for(*self.fixture["telemetry"])
        proposal = propose_ownership_patch(alerts, self.manifest, "lab-v1")
        data = proposal.event_data()
        self.assertLessEqual(set(self.contract["event_types"]["defense.proposed"]["required"]), data.keys())
        self.assertEqual(data["action_type"], APPLY_PATCH)
        self.assertEqual(data["parameters"], {"patch_id": "ownership-fix-001", "base_version": "lab-v1"})
        expected = next(e for e in self.fixture["events"]
                        if e["type"] == "defense.proposed" and e["data"]["action_type"] == APPLY_PATCH)
        self.assertEqual(data["parameters"], expected["data"]["parameters"])
        self.assertEqual(secret_keys(data), set())

    def test_labeled_remediation_awaiting_retest_with_provenance(self):
        proposal = propose_ownership_patch(alerts_for(log("r1", "alice", "bob")), self.manifest, "lab-v1")
        self.assertEqual(proposal.effect, REMEDIATION)
        self.assertIn("unverified until the referee", proposal.expected_effect)
        self.assertEqual(proposal.details["origin"], "known_good_fallback")
        self.assertEqual(proposal.details["patch_status"], "draft")
        self.assertIn("owner_access", proposal.details["regression_check_ids"])

    def test_stale_base_version_is_not_proposed(self):
        alerts = alerts_for(log("r1", "alice", "bob", version="lab-v2"))
        self.assertIsNone(propose_ownership_patch(alerts, self.manifest, "lab-v2"))

    def test_only_alerts_on_the_current_version_count(self):
        alerts = alerts_for(log("r1", "alice", "bob", version="lab-v0"))
        self.assertIsNone(propose_ownership_patch(alerts, self.manifest, "lab-v1"))
        self.assertIsNone(propose_ownership_patch(alerts_for(log("r2", "bob", "bob")), self.manifest, "lab-v1"))

    def test_anonymous_exposure_also_needs_the_patch(self):
        proposal = propose_ownership_patch(alerts_for(log("r1", None, "bob")), self.manifest, "lab-v1")
        self.assertIn("unauthenticated", proposal.reason)

    def test_other_policies_do_not_trigger_this_patch(self):
        other = replace(self.manifest, policy_id="admin-only")
        self.assertIsNone(propose_ownership_patch(alerts_for(log("r1", "alice", "bob")), other, "lab-v1"))

    def test_not_proposed_twice_and_ids_are_stable(self):
        alerts = alerts_for(log("r1", "alice", "bob"))
        first = propose_ownership_patch(alerts, self.manifest, "lab-v1")
        again = propose_ownership_patch(alerts_for(log("r1", "alice", "bob"), log("r2", "alice", "bob", second=3)),
                                        self.manifest, "lab-v1")
        self.assertEqual(first.defense_id, again.defense_id)
        self.assertIsNone(propose_ownership_patch(alerts, self.manifest, "lab-v1", [first]))
        other_patch = {"action_type": APPLY_PATCH, "parameters": {"patch_id": "other-fix", "base_version": "lab-v1"}}
        self.assertIsNotNone(propose_ownership_patch(alerts, self.manifest, "lab-v1", [other_patch]))


if __name__ == "__main__":
    unittest.main()
