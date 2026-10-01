"""Parse, validate, and redact model replies.

Model output is evidence for the state machine, never the state itself. A reply
that cannot be parsed or does not match its schema is rejected, and the caller
stops the task for human review instead of guessing.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

from common import FRAMEWORK

SCHEMAS = FRAMEWORK / "schemas"
FENCED = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
SECRET_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("google-key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer-token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{20,}=*")),
]


class ReplyError(ValueError):
    pass


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.json").read_text(encoding="utf-8"))


def schema_path(name: str) -> Path:
    return SCHEMAS / f"{name}.json"


def extract_json(text: str) -> dict:
    """Find the reply object: the whole text, a fenced json block, or the outermost braces."""
    text = (text or "").strip()
    candidates = [text]
    candidates += FENCED.findall(text)
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"): text.rindex("}") + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    if "{" in text:
        try:
            value, _ = json.JSONDecoder().raw_decode(text[text.index("{"):])
        except (json.JSONDecodeError, ValueError):
            value = None
        if isinstance(value, dict):
            return value
    raise ReplyError("no JSON object found in the reply")


def validate(value, schema: dict, where: str = "reply") -> list[str]:
    """Validate the JSON Schema subset the reply schemas use."""
    errors = []
    kind = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "boolean": bool}
    if kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return [f"{where} must be an integer"]
    elif kind in checks and not isinstance(value, checks[kind]):
        return [f"{where} must be a {kind}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where} must be one of {', '.join(map(str, schema['enum']))}")
    if kind == "object":
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}.{key} is missing")
        if schema.get("additionalProperties") is False:
            errors += [f"{where}.{key} is not allowed" for key in value if key not in properties]
        for key, sub in properties.items():
            if key in value:
                errors += validate(value[key], sub, f"{where}.{key}")
    if kind == "array" and "items" in schema:
        for index, item in enumerate(value):
            errors += validate(item, schema["items"], f"{where}[{index}]")
    return errors


def parse_reply(text: str, schema_name: str, task: str, models: tuple[str, ...]) -> dict:
    """Return the validated, redacted reply or raise ReplyError."""
    value = extract_json(text)
    errors = validate(value, load_schema(schema_name))
    if "task" in value and value.get("task") != task:
        errors.append(f"reply.task is {value.get('task')!r}, expected {task!r}")
    if "recommended_implementer" in value and value["recommended_implementer"] not in models:
        errors.append(f"reply.recommended_implementer must be one of {', '.join(models)}")
    if errors:
        raise ReplyError("; ".join(errors[:5]))
    return redact(value)


def redact(value):
    if isinstance(value, str):
        for label, pattern in SECRET_PATTERNS:
            value = pattern.sub(f"[REDACTED:{label}]", value)
        return value
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value
