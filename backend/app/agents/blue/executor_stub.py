"""In-memory defense executor for isolated Blue development, never a lab adapter.

Use one instance per target/run. Known session references must be injected by
the test; the default registry is empty. No credentials, network operations,
patch files, or referee verification are handled here. Event IDs are local to
this double; core owns the real persisted event sequence.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
import re

from .patches import PatchManifest, load_patch_manifest
from .proposals import APPLY_PATCH, REVOKE_SESSION

EVENT_KEYS = ("schema_version", "id", "assessment_id", "timestamp", "type", "actor", "target_id",
              "target_version", "data_source", "evidence_refs", "data")
PROPOSAL_KEYS = ("defense_id", "action_type", "summary", "reason", "parameters")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}")
FAILURE_REASONS = {
    "draft_patch": "Draft patches cannot be applied.",
    "stale_base_version": "Patch base version does not match the current target.",
    "unsupported_action": "Action or patch manifest is unsupported.",
    "unknown_session": "Session reference is not registered.",
    "already_applied": "Defense was already applied.",
}


class StandInExecutor:
    def __init__(self, current_version="lab-v1", manifest_loader=load_patch_manifest, *, known_sessions=()):
        if not _identifier(current_version):
            raise ValueError("Current version must be an identifier.")
        if isinstance(known_sessions, str):
            raise ValueError("Known sessions must be a collection of references.")
        self._known_sessions = frozenset(known_sessions)
        if not all(_identifier(session) for session in self._known_sessions):
            raise ValueError("Known sessions must contain only identifier references.")
        self.current_version = current_version
        self.manifest_loader = manifest_loader
        self.revoked_sessions = set()
        self._applied = set()
        self._event_id = 0

    def apply(self, proposal_event):
        """Simulate an approved proposal and return a full, explicitly marked event.

        Well-shaped proposals yield applied/failed events. Invalid envelopes
        raise a fixed ValueError because their routing fields cannot be trusted.
        Successful applications consume a defense ID; failed attempts may retry.
        """
        _validate_proposal(proposal_event)
        data = proposal_event["data"]
        defense_id, action = data["defense_id"], data["action_type"]
        if defense_id in self._applied:
            return self._failed(proposal_event, "already_applied")
        parameters = data["parameters"]
        original = self.current_version
        if action == REVOKE_SESSION:
            session = parameters.get("session_ref") if isinstance(parameters, Mapping) else None
            if not isinstance(session, str) or session not in self._known_sessions:
                return self._failed(proposal_event, "unknown_session")
            self.revoked_sessions.add(session)
            origin = "policy_action"
        elif action == APPLY_PATCH:
            patch_id = parameters.get("patch_id") if isinstance(parameters, Mapping) else None
            if not isinstance(patch_id, str):
                return self._failed(proposal_event, "unsupported_action")
            try:
                manifest = self.manifest_loader(patch_id)
            except (OSError, ValueError):
                return self._failed(proposal_event, "unsupported_action")
            if not isinstance(manifest, PatchManifest) or manifest.patch_id != patch_id:
                return self._failed(proposal_event, "unsupported_action")
            if manifest.status == "draft":
                return self._failed(proposal_event, "draft_patch")
            if not manifest.ready:
                return self._failed(proposal_event, "unsupported_action")
            if (parameters.get("base_version") != original or manifest.base_version != original
                    or proposal_event["target_version"] != original):
                return self._failed(proposal_event, "stale_base_version")
            origin = manifest.origin
            match = re.fullmatch(r"(.*-v)([0-9]+)", original)
            resulting = f"{match[1]}{int(match[2]) + 1}" if match else original + "-patched"
            if not _identifier(resulting):
                return self._failed(proposal_event, "unsupported_action")
            self.current_version = resulting
        else:
            return self._failed(proposal_event, "unsupported_action")
        self._applied.add(defense_id)
        return self._event(proposal_event, "defense.applied", {
            "defense_id": defense_id, "action_type": action, "origin": origin,
            "original_version": original, "resulting_version": self.current_version,
        })

    def _failed(self, proposal, code):
        # Failure action_type is omitted so unsupported actions remain consumable by observe.
        return self._event(proposal, "defense.failed", {
            "defense_id": proposal["data"]["defense_id"], "code": code, "reason": FAILURE_REASONS[code],
        })

    def _event(self, proposal, kind, data):
        self._event_id = max(self._event_id, proposal["id"]) + 1
        return {
            "schema_version": "1.0", "id": self._event_id, "assessment_id": proposal["assessment_id"],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "type": kind, "actor": "system", "target_id": proposal["target_id"],
            "target_version": self.current_version, "data_source": proposal["data_source"],
            "evidence_refs": [], "data": data, "executor": "stand-in",
        }


def _identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def _validate_proposal(event):
    if (not isinstance(event, Mapping) or not set(EVENT_KEYS) <= event.keys()
            or event["schema_version"] != "1.0" or event["type"] != "defense.proposed"
            or event["actor"] != "blue" or type(event["id"]) is not int
            or event["data_source"] not in ("fixture", "recorded", "live")
            or not all(_identifier(event[key]) for key in ("assessment_id", "target_id", "target_version"))
            or not isinstance(event["data"], Mapping) or not set(PROPOSAL_KEYS) <= event["data"].keys()
            or not _identifier(event["data"]["defense_id"])):
        raise ValueError("Expected a defense.proposed contract event.")
