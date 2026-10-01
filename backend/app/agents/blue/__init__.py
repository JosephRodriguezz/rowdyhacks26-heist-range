"""Blue team: telemetry-based detection and bounded defense proposals."""

from .detection import (
    ANONYMOUS_READ,
    CROSS_USER_READ,
    PRIVATE_ORDERS_POLICY,
    AccessPolicy,
    Alert,
    DetectionResult,
    SkippedRecord,
    detect_suspicious_access,
    parse_utc_timestamp,
)
from .incident import REPORT_SCHEMA, build_incident_report, render_markdown
from .patches import PatchManifest, PatchManifestError, load_patch_manifest, parse_patch_manifest
from .proposals import (
    APPLY_PATCH,
    CONTAINMENT,
    REMEDIATION,
    REVOKE_SESSION,
    DefenseProposal,
    propose_ownership_patch,
    propose_session_revocations,
)

__all__ = [
    "ANONYMOUS_READ",
    "APPLY_PATCH",
    "CONTAINMENT",
    "CROSS_USER_READ",
    "PRIVATE_ORDERS_POLICY",
    "REMEDIATION",
    "REPORT_SCHEMA",
    "REVOKE_SESSION",
    "AccessPolicy",
    "Alert",
    "DefenseProposal",
    "DetectionResult",
    "PatchManifest",
    "PatchManifestError",
    "SkippedRecord",
    "build_incident_report",
    "detect_suspicious_access",
    "load_patch_manifest",
    "parse_patch_manifest",
    "parse_utc_timestamp",
    "propose_ownership_patch",
    "propose_session_revocations",
    "render_markdown",
]
