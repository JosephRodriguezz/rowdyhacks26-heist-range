"""Load and validate blue's patch artifacts under defenses/patches/.

A manifest describes one bounded patch: which lab files it may touch, which
target version it applies to, where it came from, and which checks the referee
must run afterwards. Validation here is blue's own gate; the executor still
verifies base version and file scope before applying anything.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

PATCHES_DIR = Path(__file__).resolve().parents[4] / "defenses" / "patches"
ORIGINS = {"generated", "known_good_fallback"}
STATUSES = {"draft", "ready"}
EXPECTATIONS = {"allowed", "denied", "unchanged"}
REQUIRED_CHECKS = {"unauthorized_access", "owner_access"}
FIELDS = ("patch_id", "title", "status", "origin", "base_version", "policy_id", "target_route",
          "allowed_files", "diff_file", "change", "explanation", "regression_checks")
PATCH_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class PatchManifestError(ValueError):
    pass


@dataclass(frozen=True)
class RegressionCheck:
    id: str
    description: str
    expected: str


@dataclass(frozen=True)
class PatchManifest:
    patch_id: str
    title: str
    status: str
    origin: str
    base_version: str
    policy_id: str
    target_route: str
    allowed_files: tuple[str, ...]
    diff_file: str | None
    change: str
    explanation: str
    regression_checks: tuple[RegressionCheck, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def load_patch_manifest(patch_id: str, patches_dir: Path = PATCHES_DIR) -> PatchManifest:
    if not PATCH_ID.fullmatch(patch_id):
        raise PatchManifestError("patch_id must be lowercase letters, digits, and hyphens")
    path = patches_dir / patch_id / "manifest.json"
    manifest = parse_patch_manifest(json.loads(path.read_text(encoding="utf-8")))
    if manifest.patch_id != patch_id:
        raise PatchManifestError("manifest patch_id does not match its folder")
    if manifest.diff_file and not (path.parent / manifest.diff_file).is_file():
        raise PatchManifestError(f"diff file {manifest.diff_file} is missing")
    return manifest


def parse_patch_manifest(data: Any) -> PatchManifest:
    _require(isinstance(data, dict), "manifest must be an object")
    missing = [name for name in FIELDS if name not in data]
    _require(not missing, "manifest missing " + ", ".join(missing))
    for name in ("patch_id", "title", "base_version", "policy_id", "target_route", "change", "explanation"):
        _require(isinstance(data[name], str) and data[name].strip(), f"{name} must be a non-empty string")
    _require(PATCH_ID.fullmatch(data["patch_id"]) is not None, "patch_id must be lowercase letters, digits, and hyphens")
    _require(data["status"] in STATUSES, "status must be draft or ready")
    _require(data["origin"] in ORIGINS, "origin must be generated or known_good_fallback")

    files = data["allowed_files"]
    _require(isinstance(files, list) and all(isinstance(f, str) for f in files), "allowed_files must be a list of paths")
    for name in files:
        _require(_safe_relative(name), f"allowed file {name!r} must be a relative path inside the repository")
    diff_file = data["diff_file"]
    _require(diff_file is None or (isinstance(diff_file, str) and _plain_filename(diff_file)),
             "diff_file must be null or a file name in the patch folder")
    if data["status"] == "ready":
        _require(bool(files) and bool(diff_file), "a ready patch needs allowed_files and a diff_file")

    checks = data["regression_checks"]
    _require(isinstance(checks, list) and checks, "regression_checks must be a non-empty list")
    parsed = []
    for check in checks:
        _require(isinstance(check, dict) and {"id", "description", "expected"} <= check.keys(),
                 "each regression check needs id, description, expected")
        _require(check["expected"] in EXPECTATIONS, f"check {check.get('id')!r} has an unknown expectation")
        parsed.append(RegressionCheck(str(check["id"]), str(check["description"]), check["expected"]))
    ids = [check.id for check in parsed]
    _require(len(ids) == len(set(ids)), "regression check IDs must be unique")
    _require(REQUIRED_CHECKS <= set(ids), "regression checks must cover unauthorized_access and owner_access")

    return PatchManifest(
        patch_id=data["patch_id"], title=data["title"], status=data["status"], origin=data["origin"],
        base_version=data["base_version"], policy_id=data["policy_id"], target_route=data["target_route"],
        allowed_files=tuple(files), diff_file=diff_file, change=data["change"],
        explanation=data["explanation"], regression_checks=tuple(parsed),
    )


def _safe_relative(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and "\\" not in name and not path.is_absolute() and ".." not in path.parts and ":" not in name


def _plain_filename(name: str) -> bool:
    return bool(name) and _safe_relative(name) and len(PurePosixPath(name).parts) == 1


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PatchManifestError(message)
