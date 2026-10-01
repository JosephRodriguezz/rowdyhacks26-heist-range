"""Before-and-after snapshots of the repository around every model run.

Commit hooks only stop a bad commit; they cannot stop a model from changing a
file on disk. Every model run is bracketed by snapshots so the orchestrator can
detect, deterministically, a branch switch, a new commit or reset, ref changes,
git config or hook changes, and any file change outside what that run was
allowed to touch. Changes are reported, never reverted automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from common import ROOT, current_branch, git, model_writable, sha256_bytes, sha256_text

MISSING = "missing"


@dataclass(frozen=True)
class Snapshot:
    branch: str | None
    head: str | None
    refs: str
    git_config: str
    hooks_path: str | None
    files: dict = field(default_factory=dict)


@dataclass
class Report:
    changed: list[str]
    violations: list[str]


def ignored(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    segments = path.rstrip("/").split("/")
    for pattern in patterns:
        bare = pattern.rstrip("/")
        if "/" in bare:
            if path == bare or path.startswith(bare + "/") or path == pattern:
                return True
        elif bare in segments:
            return True
    return False


def take(config: dict) -> Snapshot:
    head = git("rev-parse", "--verify", "-q", "HEAD", check=False) or None
    refs = sha256_text(git("for-each-ref", "--format=%(refname) %(objectname)", check=False))
    config_path = ROOT / git("rev-parse", "--git-path", "config", check=False)
    git_config = sha256_bytes(config_path.read_bytes()) if config_path.is_file() else MISSING
    hooks_path = git("config", "--get", "core.hooksPath", check=False) or None
    return Snapshot(current_branch(), head, refs, git_config, hooks_path, _files(config["watch_ignore"]))


def compare(before: Snapshot, after: Snapshot, config: dict, allow_writes: bool) -> Report:
    violations = []
    if before.branch != after.branch:
        violations.append(f"branch changed from {before.branch} to {after.branch}")
    if before.head != after.head:
        violations.append(f"HEAD moved from {_short(before.head)} to {_short(after.head)} (a commit, reset, or checkout)")
    if before.refs != after.refs:
        violations.append("git refs changed (branch, tag, or remote-tracking ref created, moved, or deleted)")
    if before.git_config != after.git_config:
        violations.append("git config changed")
    if before.hooks_path != after.hooks_path:
        violations.append(f"core.hooksPath changed from {before.hooks_path} to {after.hooks_path}")
    paths = set(before.files) | set(after.files)
    changed = sorted(p for p in paths if before.files.get(p) != after.files.get(p))
    for path in changed:
        if not allow_writes:
            violations.append(f"file changed during a read-only run: {path}")
        elif not model_writable(path, config):
            violations.append(f"file changed outside the paths this run may write: {path}")
    return Report(changed, violations)


def _files(patterns: list[str]) -> dict[str, str]:
    raw = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching",
              check=False, strip=False).split("\0")
    paths, index = [], 0
    while index < len(raw):
        entry = raw[index]
        index += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            paths.append(raw[index])
            index += 1
    files = {}
    for path in paths:
        if ignored(path, patterns):
            continue
        full = ROOT / path
        if path.endswith("/") or full.is_dir():
            for walked in _walk(full, patterns):
                files[walked] = _digest(ROOT / walked)
        else:
            files[path] = _digest(full)
    return files


def _walk(directory: Path, patterns: list[str]):
    for current, dirs, names in os.walk(directory):
        rel_dir = Path(current).relative_to(ROOT).as_posix()
        dirs[:] = [d for d in dirs if not ignored(f"{rel_dir}/{d}/", patterns)]
        for name in names:
            rel = f"{rel_dir}/{name}"
            if not ignored(rel, patterns):
                yield rel


def _digest(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes()) if path.is_file() else MISSING
    except OSError:
        return "unreadable"


def _short(sha: str | None) -> str:
    return sha[:8] if sha else "none"
