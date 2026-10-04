"""Shared builders and paths for blue tests."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SECRET_KEYS = {"password", "token", "api_key", "authorization", "cookie"}


def load_shared(relative_path):
    return json.loads((ROOT / relative_path).read_text())


def log(request_id, actor, owner, status=200, *, session=None, second=0, version="lab-v1",
        action="read_private_order", resource="order-204"):
    return {
        "request_id": request_id,
        "timestamp": f"2026-09-30T15:00:{second:02d}Z",
        "target_id": "storefront-lab",
        "target_version": version,
        "actor_ref": actor,
        "session_ref": session or (f"{actor}-session-1" if actor else None),
        "resource_id": resource,
        "resource_owner_ref": owner,
        "action": action,
        "http_status": status,
    }


def secret_keys(value):
    if isinstance(value, dict):
        found = SECRET_KEYS & {key.lower() for key in value}
        return found.union(*(secret_keys(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(secret_keys(child) for child in value))
    return set()
