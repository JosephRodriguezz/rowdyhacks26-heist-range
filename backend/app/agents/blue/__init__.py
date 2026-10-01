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

__all__ = [
    "ANONYMOUS_READ",
    "CROSS_USER_READ",
    "PRIVATE_ORDERS_POLICY",
    "AccessPolicy",
    "Alert",
    "DetectionResult",
    "SkippedRecord",
    "detect_suspicious_access",
]
