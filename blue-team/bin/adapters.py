"""Model CLI adapters.

Each adapter wraps one vendor CLI: finding the executable, checking version and
sign-in, building read-only or write commands from config.json, running with a
timeout and bounded retries, and normalizing the reply text. The orchestrator
never builds vendor commands itself, so a CLI change is a config edit.

Prompts always travel in a file. The command line carries only a short sentence
with the file path, because npm installs claude and codex as .cmd launchers on
Windows, and cmd.exe can mangle quotes and braces in arguments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from common import ROOT, sha256_text, validate_model
from replies import redact

PROBE_TIMEOUT = 30
READY, WARNING, NOT_INSTALLED, MISCONFIGURED = "READY", "WARNING", "NOT INSTALLED", "MISCONFIGURED"


@dataclass
class Availability:
    model: str
    status: str
    detail: str
    version: str | None = None
    executable: str | None = None

    @property
    def usable(self) -> bool:
        return self.status in (READY, WARNING)


@dataclass
class ModelResult:
    model: str
    mode: str
    ok: bool
    text: str = ""
    error: str | None = None
    exit_code: int | None = None
    attempts: int = 0
    seconds: float = 0.0
    reply_sha256: str | None = None
    logs: list[str] = field(default_factory=list)


class ModelAdapter:
    """Base adapter: plain stdout is the reply."""

    def __init__(self, name: str, spec: dict, root: Path = ROOT):
        self.name, self.spec, self.root = name, spec, root

    def executable(self) -> str | None:
        for candidate in self.spec["executable"]:
            expanded = os.path.expanduser(os.path.expandvars(candidate))
            if "/" in expanded or "\\" in expanded:
                if Path(expanded).is_file():
                    return str(Path(expanded))
            else:
                found = shutil.which(expanded)
                if found:
                    return found
        return None

    def _call(self, args: list[str], timeout: int) -> subprocess.CompletedProcess | None:
        executable = self.executable()
        if not executable:
            return None
        try:
            return subprocess.run([executable, *self.spec.get("prefix", []), *args], cwd=self.root,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=timeout, stdin=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError):
            return None

    def version(self) -> str | None:
        result = self._call(self.spec["version_command"], PROBE_TIMEOUT)
        if result is None or result.returncode != 0:
            return None
        lines = (result.stdout or result.stderr).strip().splitlines()
        return lines[0].strip() if lines else ""

    def signed_in(self) -> bool | None:
        """True or False from the CLI's own status command; None when there is none. Output is never kept."""
        if not self.spec.get("auth_command"):
            return None
        result = self._call(self.spec["auth_command"], PROBE_TIMEOUT)
        return result is not None and result.returncode == 0

    def missing_flags(self) -> list[str]:
        result = self._call(self.spec["help_command"], PROBE_TIMEOUT)
        text = "" if result is None else result.stdout + result.stderr
        return [flag for flag in self.spec["expected_flags"] if flag not in text]

    def availability(self, check_flags: bool = False) -> Availability:
        problems = validate_model(self.spec)
        if problems:
            return Availability(self.name, MISCONFIGURED, "; ".join(problems))
        executable = self.executable()
        if not executable:
            return Availability(self.name, NOT_INSTALLED, f"not found. {self.spec.get('install', '')}".strip())
        version = self.version()
        if version is None:
            return Availability(self.name, MISCONFIGURED, "version check failed", None, executable)
        signed_in = self.signed_in()
        if signed_in is False:
            return Availability(self.name, MISCONFIGURED, "not signed in; sign in with the CLI", version, executable)
        if check_flags:
            missing = self.missing_flags()
            if missing:
                return Availability(self.name, MISCONFIGURED, "help output lacks " + ", ".join(missing)
                                    + "; update its commands in config.json", version, executable)
        if signed_in is None:
            return Availability(self.name, WARNING, "sign-in state not checked (the CLI has no status command)",
                                version, executable)
        return Availability(self.name, READY, "signed in", version, executable)

    def command(self, mode: str, prompt: str, schema: Path, output_file: Path, timeout: int) -> list[str]:
        values = {"{prompt}": prompt, "{schema}": str(schema), "{output_file}": str(output_file),
                  "{root}": str(self.root), "{timeout}": str(timeout)}
        parts = []
        for part in self.spec[mode]:
            for placeholder, value in values.items():
                part = part.replace(placeholder, value)
            parts.append(part)
        return parts

    def extract_text(self, stdout: str, output_file: Path) -> str:
        return stdout

    def run(self, mode: str, prompt: str, schema: Path, run_dir: Path, label: str, retries: int) -> ModelResult:
        result = ModelResult(self.name, mode, ok=False)
        executable = self.executable()
        if not executable:
            result.error = "CLI not installed"
            return result
        timeout = self.spec["timeout_seconds"][mode]
        output_file = run_dir / f"{label}.reply.txt"
        started = time.monotonic()
        for attempt in range(1, retries + 2):
            result.attempts = attempt
            output_file.unlink(missing_ok=True)
            args = self.command(mode, prompt, schema, output_file, timeout)
            try:
                proc = subprocess.run([executable, *self.spec.get("prefix", []), *args], cwd=self.root,
                                      capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      timeout=timeout + 30, stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                result.error, result.exit_code = f"timed out after {timeout + 30}s", None
                continue
            except OSError as error:
                result.error = f"could not start: {error}"
                break
            log = run_dir / f"{label}.attempt{attempt}.log"
            log.write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8")
            result.logs.append(log.name)
            result.exit_code = proc.returncode
            text = self.extract_text(proc.stdout, output_file)
            if proc.returncode == 0 and text.strip():
                result.ok, result.text, result.error = True, text, None
                result.reply_sha256 = sha256_text(text)
                break
            tail = redact((proc.stderr or proc.stdout).strip()[-400:]) or "no output"
            result.error = f"exit {proc.returncode}: {tail}"
        result.seconds = round(time.monotonic() - started, 1)
        return result


class ClaudeAdapter(ModelAdapter):
    """claude -p --output-format json prints an envelope whose `result` holds the reply."""

    def extract_text(self, stdout: str, output_file: Path) -> str:
        try:
            envelope = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return stdout
        if isinstance(envelope, dict) and "result" in envelope:
            return "" if envelope.get("is_error") else str(envelope["result"])
        return stdout


class CodexAdapter(ModelAdapter):
    """codex exec writes the final message to the --output-last-message file."""

    def extract_text(self, stdout: str, output_file: Path) -> str:
        if output_file.is_file():
            text = output_file.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                return text
        return stdout


class AntigravityAdapter(ModelAdapter):
    """agy --print --output-format json prints {"conversation_id", "status", "response", "structured_output", ...}.

    Observed with agy 1.2.14: with --json-schema, `structured_output` holds the
    schema-checked reply, while `response` may hold several JSON objects in a row.
    When headless mode auto-denies a tool permission, the run ends with status
    SUCCESS and an empty response, so an empty response is a failed call.
    """

    def extract_text(self, stdout: str, output_file: Path) -> str:
        try:
            envelope = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return stdout
        if not isinstance(envelope, dict) or "response" not in envelope:
            return stdout
        if str(envelope.get("status", "SUCCESS")).upper() != "SUCCESS":
            return ""
        if isinstance(envelope.get("structured_output"), dict):
            return json.dumps(envelope["structured_output"])
        response = envelope["response"]
        if isinstance(response, dict):
            return json.dumps(response)
        return response if isinstance(response, str) else ""


ADAPTERS = {"claude": ClaudeAdapter, "codex": CodexAdapter, "antigravity": AntigravityAdapter}


def adapter_for(name: str, config: dict) -> ModelAdapter:
    spec = config["models"][name]
    return ADAPTERS.get(spec.get("adapter"), ModelAdapter)(name, spec)
