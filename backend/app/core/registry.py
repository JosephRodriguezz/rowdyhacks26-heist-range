"""Server-owned registry for the small set of permitted lab targets."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


class TargetScopeError(ValueError):
    """Raised when a caller tries to address an unregistered target or origin."""


@dataclass(frozen=True)
class TargetSpec:
    target_id: str
    version: str
    origin: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("target origin must be an absolute HTTP origin")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("target origin cannot include a path or query")
        if parsed.username or parsed.password:
            raise ValueError("target origin cannot include userinfo")


class TargetRegistry:
    """Resolve IDs to fixed origins; callers never supply a destination URL."""

    def __init__(self, targets: tuple[TargetSpec, ...] | list[TargetSpec]):
        if not targets:
            raise ValueError("at least one registered target is required")
        self._targets = {(target.target_id, target.version): target for target in targets}
        if len(self._targets) != len(targets):
            raise ValueError("duplicate target ID/version")

    def resolve(self, target_id: str, version: str) -> TargetSpec:
        try:
            return self._targets[(target_id, version)]
        except KeyError as error:
            raise TargetScopeError("target ID/version is not registered") from error

    def resolve_path(self, target_id: str, version: str, path: str) -> tuple[TargetSpec, str]:
        target = self.resolve(target_id, version)
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
            raise TargetScopeError("request path must be origin-relative")
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise TargetScopeError("request path cannot override the registered origin")
        if "\\" in path or ".." in parsed.path or not parsed.path:
            raise TargetScopeError("request path is not permitted")
        return target, parsed.path
