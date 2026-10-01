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
)
from .proposals import CONTAINMENT, REVOKE_SESSION, DefenseProposal, propose_session_revocations

__all__ = [
    "ANONYMOUS_READ",
    "CONTAINMENT",
    "CROSS_USER_READ",
    "PRIVATE_ORDERS_POLICY",
    "REVOKE_SESSION",
    "AccessPolicy",
    "Alert",
    "DefenseProposal",
    "DetectionResult",
    "SkippedRecord",
    "detect_suspicious_access",
    "propose_session_revocations",
]
