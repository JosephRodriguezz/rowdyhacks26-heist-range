"""Check starter contract/fixture consistency; not a live-input schema validator."""

import argparse
import copy
from datetime import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, label):
    require(isinstance(value, dict), f"{label}: expected object")
    require(set(names) <= value.keys(), f"{label}: missing required field")


def check_no_secrets(value):
    if isinstance(value, dict):
        forbidden = {"password", "token", "api_key", "authorization", "cookie"}
        require(not (forbidden & {k.lower() for k in value}), "Raw secret field in fixture")
        for child in value.values():
            check_no_secrets(child)
    elif isinstance(value, list):
        for child in value:
            check_no_secrets(child)


def validate(contract, fixture):
    snapshot = fixture["snapshot"]
    events = fixture["events"]
    evidence = fixture["evidence"]
    fields(snapshot, contract["snapshot_required"], "snapshot")
    require(snapshot["schema_version"] == contract["schema_version"], "Snapshot version mismatch")
    require(snapshot["status"] in contract["assessment_statuses"], "Unknown assessment status")
    require(snapshot["phase"] in contract["phases"], "Unknown phase")
    require(snapshot["data_source"] == "fixture", "Sample must be labeled fixture")
    require(set(snapshot["allowed_actions"]) <= set(contract["actions"]), "Unknown action")
    evidence_ids = {item["id"] for item in evidence}
    require(len(evidence_ids) == len(evidence), "Duplicate evidence ID")
    require(bool(events), "Empty sample run")
    seen_findings, seen_defenses, applied_defenses = set(), {}, set()
    version = events[0]["target_version"]
    for index, event in enumerate(events, 1):
        fields(event, contract["event_required"], f"event {index}")
        require(type(event["id"]) is int and event["id"] == index, "Broken event ordering")
        require(event["assessment_id"] == snapshot["id"], "Wrong assessment")
        require(event["target_id"] == snapshot["target_id"], "Wrong target")
        require(event["schema_version"] == contract["schema_version"], "Event version mismatch")
        require(event["data_source"] == "fixture", "Sample event is not labeled fixture")
        require(event["actor"] in contract["actors"], "Unknown actor")
        require(event["type"] in contract["event_types"], "Unknown event type")
        require(event["timestamp"].endswith("Z"), "Timestamp must be UTC")
        datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        require(isinstance(event["evidence_refs"], list), "Evidence refs must be a list")
        require(set(event["evidence_refs"]) <= evidence_ids, "Unresolved evidence reference")
        spec = contract["event_types"][event["type"]]
        require(spec["actor"] is None or spec["actor"] == event["actor"], "Wrong event producer")
        data, kind = event["data"], event["type"]
        fields(data, spec["required"], kind)
        if kind == "agent.status":
            require(data["status"] in contract["agent_statuses"], "Unknown agent status")
        if kind == "finding.candidate":
            require(data["finding_id"] not in seen_findings, "Duplicate candidate")
            seen_findings.add(data["finding_id"])
            path = data["repro"]["path"]
            require(path.startswith("/") and not path.startswith("//") and "://" not in path,
                    "Replay destination must be a relative lab path")
        elif "finding_id" in data:
            require(data["finding_id"] in seen_findings, "Unknown finding reference")
        if kind in {"finding.verified", "finding.rejected", "finding.inconclusive"}:
            require(data["verdict"] == kind.split(".")[1], "Verdict/event mismatch")
            require(bool(event["evidence_refs"]), "Verdict missing evidence")
        if kind == "defense.proposed":
            require(data["defense_id"] not in seen_defenses, "Duplicate defense proposal")
            require(data["action_type"] in {"revoke_session", "apply_patch"}, "Unsupported defense")
            params = ["session_ref"] if data["action_type"] == "revoke_session" else ["patch_id", "base_version"]
            fields(data["parameters"], params, "defense parameters")
            seen_defenses[data["defense_id"]] = data
        if kind == "defense.applied":
            require(data["defense_id"] in seen_defenses, "Defense applied without proposal")
            require(data["defense_id"] not in applied_defenses, "Duplicate defense application")
            proposal = seen_defenses[data["defense_id"]]
            require(data["action_type"] == proposal["action_type"], "Defense action mismatch")
            require(data["original_version"] == version, "Wrong defense base version")
            if data["action_type"] == "apply_patch":
                require(proposal["parameters"]["base_version"] == version, "Stale patch proposal")
                require(data["origin"] in {"generated", "known_good_fallback"}, "Missing patch provenance")
            else:
                require(data["origin"] == "policy_action", "Invalid session-action origin")
            version = data["resulting_version"]
            applied_defenses.add(data["defense_id"])
        require(event["target_version"] == version, "Event target version mismatch")
        if kind == "retest.completed":
            require(data["defense_id"] in applied_defenses, "Retest before applied defense")
            require(data["result"] in {"passed", "failed", "inconclusive"}, "Unknown retest result")
            require(bool(event["evidence_refs"]), "Retest missing evidence")
            checks = data["checks"]
            if data["result"] == "passed":
                require({"unauthorized_access", "owner_access"} <= {c["id"] for c in checks},
                        "Successful retest missing access controls")
                require(all(c["passed"] is True and c["actual"] == c["expected"] for c in checks),
                        "Successful retest includes a failed check")
    require(snapshot["last_event_id"] == events[-1]["id"], "Snapshot cursor mismatch")
    require(snapshot["target_version"] == version, "Snapshot target version mismatch")
    require(set(snapshot["finding_ids"]) == seen_findings, "Snapshot findings mismatch")
    require(set(snapshot["defense_ids"]) == set(seen_defenses), "Snapshot defenses mismatch")
    require(events[-1]["type"] == "assessment.completed" and
            events[-1]["data"]["status"] == snapshot["status"], "Final state mismatch")
    for log in fixture["telemetry"]:
        fields(log, ["request_id", "timestamp", "target_id", "target_version", "actor_ref",
                     "session_ref", "resource_id", "resource_owner_ref", "action", "http_status"], "telemetry")
        require(log["target_id"] == snapshot["target_id"], "Telemetry target mismatch")
    check_no_secrets(fixture)


def self_test(contract, fixture):
    def mutate_event(kind, change):
        def apply(f):
            change(next(e for e in f["events"] if e["type"] == kind))
        return apply

    cases = {
        "duplicate event": lambda f: f["events"][1].update(id=1),
        "missing payload field": mutate_event("alert.created", lambda e: e["data"].pop("summary")),
        "unresolved evidence": mutate_event("finding.verified", lambda e: e.update(evidence_refs=["missing"])),
        "self-verification": mutate_event("finding.verified", lambda e: e.update(actor="red")),
        "external replay destination": mutate_event("finding.candidate", lambda e: e["data"]["repro"].update(path="https://example.com")),
        "false successful retest": mutate_event("retest.completed", lambda e: e["data"]["checks"][0].update(actual="allowed")),
        "stale snapshot": lambda f: f["snapshot"].update(target_version="lab-v1"),
        "raw secret": lambda f: f["evidence"][0].update(password="placeholder"),
    }
    for name, mutation in cases.items():
        invalid = copy.deepcopy(fixture)
        mutation(invalid)
        try:
            validate(contract, invalid)
        except ValueError:
            continue
        raise ValueError(f"Self-test did not reject {name}")
    print(f"PASS: {len(cases)} invalid handoffs rejected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    contract = json.loads((ROOT / "shared/contracts/v1.json").read_text())
    fixture = json.loads((ROOT / "shared/fixtures/demo-run.json").read_text())
    validate(contract, fixture)
    print(f"PASS: {len(fixture['events'])} fixture events and evidence references")
    if args.self_test:
        self_test(contract, fixture)


if __name__ == "__main__":
    main()
