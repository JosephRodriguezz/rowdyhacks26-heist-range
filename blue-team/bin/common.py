"""Shared paths, config, git, and file helpers for the blue-team framework scripts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

FRAMEWORK = Path(__file__).resolve().parents[1]
ROOT = FRAMEWORK.parent
SPECIAL_PARTICIPANTS = ("human", "orchestrator")
ADAPTER_KINDS = ("claude", "codex", "antigravity")
MIN_PYTHON = (3, 10)


def load_config() -> dict:
    return json.loads((FRAMEWORK / "config.json").read_text(encoding="utf-8"))


def model_names(config: dict | None = None) -> tuple[str, ...]:
    return tuple((config or load_config())["models"])


def voters(config: dict | None = None) -> tuple[str, ...]:
    return model_names(config) + ("human",)


def participants(config: dict | None = None) -> tuple[str, ...]:
    return model_names(config) + SPECIAL_PARTICIPANTS


def commit_paths(config: dict) -> list[str]:
    """Paths that may be committed on the work branch: model paths plus orchestrator records."""
    return list(config["model_write_paths"]) + list(config["orchestrator_paths"])


def model_writable(path: str, config: dict) -> bool:
    """True when a write-capable model run may change this path."""
    return (in_paths(path, config["model_write_paths"]) and not in_paths(path, config.get("protected_paths", []))
            and not in_paths(path, config["orchestrator_paths"]))


def in_paths(path: str, paths: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(path == allowed or (allowed.endswith("/") and path.startswith(allowed)) for allowed in paths)


in_write_paths = in_paths


def validate_config(config: dict) -> list[str]:
    """Return every problem found in config.json; an empty list means valid."""
    problems = []
    if not isinstance(config, dict):
        return ["config.json must be an object"]
    if config.get("version") != 2:
        problems.append("version must be 2")
    for key in ("branch", "remote"):
        if not isinstance(config.get(key), str) or not config.get(key):
            problems.append(f"{key} must be a non-empty string")
    for key in ("model_write_paths", "orchestrator_paths", "protected_paths", "watch_ignore", "default_context"):
        value = config.get(key)
        if not isinstance(value, list) or not all(isinstance(p, str) and p for p in value):
            problems.append(f"{key} must be a list of non-empty strings")
    if not problems:
        for path in config["model_write_paths"]:
            if path.startswith(("/", "..")) or ":" in path or in_paths(path, config["orchestrator_paths"]):
                problems.append(f"model write path {path} must be relative and outside the orchestrator paths")
    checks = config.get("checks")
    if not isinstance(checks, list) or not checks:
        problems.append("checks must be a non-empty list")
    else:
        for check in checks:
            if not (isinstance(check, dict) and isinstance(check.get("name"), str) and isinstance(check.get("cwd"), str)
                    and isinstance(check.get("command"), list) and check["command"]):
                problems.append(f"check {check!r} needs name, cwd, and a command list")
    models = config.get("models")
    if not isinstance(models, dict) or not models:
        problems.append("models must be a non-empty object")
        models = {}
    for name, spec in models.items():
        problems += [f"models.{name}: {p}" for p in validate_model(spec)]
    policy = config.get("policy")
    if not isinstance(policy, dict):
        problems.append("policy must be an object")
    else:
        count = len(models)
        for key in ("quorum", "min_reviewers", "max_revisions", "retries"):
            if not isinstance(policy.get(key), int) or policy[key] < 0:
                problems.append(f"policy.{key} must be a non-negative integer")
        if isinstance(policy.get("quorum"), int) and not 1 <= policy["quorum"] <= max(count, 1):
            problems.append("policy.quorum must be between 1 and the number of models")
        if isinstance(policy.get("min_reviewers"), int) and not 1 <= policy["min_reviewers"] <= max(count - 1, 1):
            problems.append("policy.min_reviewers must be between 1 and the number of models minus one")
        if policy.get("facilitator") not in models:
            problems.append("policy.facilitator must name a configured model")
        tiebreak = policy.get("implementer_tiebreak")
        if not isinstance(tiebreak, list) or set(tiebreak) != set(models):
            problems.append("policy.implementer_tiebreak must list every configured model once")
    return problems


def validate_model(spec: dict) -> list[str]:
    problems = []
    if not isinstance(spec, dict):
        return ["must be an object"]
    if spec.get("adapter") not in ADAPTER_KINDS:
        problems.append(f"adapter must be one of {', '.join(ADAPTER_KINDS)}")
    executable = spec.get("executable")
    if not isinstance(executable, list) or not executable or not all(isinstance(e, str) and e for e in executable):
        problems.append("executable must be a non-empty list of names or paths")
    if not isinstance(spec.get("prefix", []), list):
        problems.append("prefix must be a list")
    for mode in ("read", "write"):
        command = spec.get(mode)
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            problems.append(f"{mode} must be a list of strings")
        elif sum("{prompt}" in part for part in command) != 1:
            problems.append(f"{mode} must contain {{prompt}} exactly once")
    if not isinstance(spec.get("role"), str) or not (ROOT / spec["role"]).is_file():
        problems.append(f"role file {spec.get('role')} not found")
    timeouts = spec.get("timeout_seconds")
    if not isinstance(timeouts, dict) or not all(isinstance(timeouts.get(m), int) and timeouts[m] > 0 for m in ("read", "write")):
        problems.append("timeout_seconds needs positive read and write values")
    for key in ("version_command", "help_command"):
        if not isinstance(spec.get(key), list):
            problems.append(f"{key} must be a list")
    if spec.get("auth_command") is not None and not isinstance(spec.get("auth_command"), list):
        problems.append("auth_command must be a list or null")
    if not isinstance(spec.get("expected_flags"), list):
        problems.append("expected_flags must be a list")
    notes = spec.get("prompt_notes", {})
    if not isinstance(notes, dict) or not all(isinstance(notes.get(m, ""), str) for m in ("read", "write")):
        problems.append("prompt_notes must map read and write to strings")
    return problems


def git(*args: str, check: bool = True, cwd: Path = ROOT, strip: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip() if strip else result.stdout


def changed_paths() -> list[str]:
    """Every modified, staged, deleted, or untracked path, including both sides of a rename."""
    entries = git("status", "--porcelain=v1", "-z", "--untracked-files=all", check=False, strip=False).split("\0")
    paths, index = [], 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            paths.append(entries[index])
            index += 1
    return paths


def current_branch() -> str | None:
    name = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    return name or None


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def python() -> str:
    return sys.executable or "python"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def atomic_write(path: Path, text: str) -> None:
    """Write UTF-8 text with LF endings so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(text.encode("utf-8"))
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()
