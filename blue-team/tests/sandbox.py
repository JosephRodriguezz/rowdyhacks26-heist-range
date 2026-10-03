"""Throwaway repositories and a fake model CLI for framework tests.

The fake imitates each vendor's output format (Claude's JSON envelope, Codex's
--output-last-message file, Antigravity's JSON envelope), so the real adapters run
against it. Behaviour is chosen per model with FAKE_<NAME>=a,b,c environment flags.
No test calls a real model.
"""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "bin"))

FAKE_MODEL = r'''
import json, os, pathlib, re, subprocess, sys
name, args = sys.argv[1], sys.argv[2:]
flags = set(filter(None, os.environ.get("FAKE_" + name.upper(), "").split(",")))
if args[:1] == ["--version"]:
    sys.exit(1 if "noversion" in flags else print(name + "-fake 9.9.9") or 0)
if args[:1] == ["auth-status"]:
    sys.exit(1 if "signed-out" in flags else 0)
if "--help" in args:
    print(" ".join(["--print", "--permission-mode", "--allowedTools", "--disallowedTools", "--output-format", "--sandbox",
                    "--cd", "--output-schema", "--output-last-message", "--mode", "--json-schema", "--print-timeout"]))
    sys.exit(0)
joined = " ".join(args)
path = re.search(r"Read the file (\S+)", joined).group(1)
phase = pathlib.Path(path).name.removesuffix(".prompt.md").split("-")[-2]
write = any(a in ("acceptEdits", "workspace-write", "accept-edits") for a in args)
prompt = pathlib.Path(path).read_text(encoding="utf-8")
log = os.environ.get("FAKE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(f"{name} {phase} {'write' if write else 'read'}\n")
role = "blue-team/roles/" + name + ".md"
if "blue-team/AGENTS.md" not in prompt or role not in prompt:
    sys.exit(3)
if phase in ("implement", "revise", "review") and "blue-team/decisions/" not in prompt:
    sys.exit(4)
task = re.search(r"^# Blue-team \S+: (\S+)", prompt, re.M).group(1)
if "flaky" in flags:
    counter = pathlib.Path(os.environ["FAKE_COUNTER"])
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    if count == 0:
        sys.exit(1)
if "oauth" in flags:
    counter = pathlib.Path(os.environ["FAKE_COUNTER"])
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    if count < int(os.environ.get("FAKE_OAUTH_FAILS", "2")):
        print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "result":
                          "Failed to refresh OAuth token: another Claude Code process is refreshing it or exited "
                          "mid-refresh. This is usually transient; retry in a minute"}))
        sys.exit(1)
if "fail" in flags:
    print("simulated failure", file=sys.stderr)
    sys.exit(1)
def git(*a):
    subprocess.run(["git", *a], check=True, capture_output=True)
recommended = next((f.split(":")[1] for f in flags if f.startswith("rec:")), "codex")
if phase == "propose":
    reply = {"task": task, "summary": name + " plan", "security": "keep blue on telemetry only", "approach": "small change",
             "tests": "owner and cross-user reads", "efficiency": "reuse fixtures", "files": ["backend/app/agents/blue/feature.py"],
             "recommended_implementer": recommended, "concerns": []}
elif phase == "draft":
    reply = {"task": task, "summary": "Most proposals agree on a small change.", "approach": "Add feature.py.",
             "security_handling": "Telemetry only.", "test_plan": "Negative controls.", "rejected_alternatives": "None."}
elif phase == "vote":
    stance = next((s for s in ("security-objection", "object", "abstain") if s.split("-")[0] in flags), "agree")
    reply = {"task": task, "stance": stance, "reason": name + " says " + stance}
elif phase in ("implement", "revise"):
    blue = pathlib.Path("backend/app/agents/blue")
    if "outside" in flags:
        pathlib.Path("README.md").write_text("changed by " + name + "\n", encoding="utf-8")
    if "protected" in flags:
        (blue / "AGENTS.md").write_text("rewritten\n", encoding="utf-8")
    if "orchestrator-file" in flags:
        pathlib.Path("blue-team/roles/" + name + ".md").write_text("I decide everything\n", encoding="utf-8")
    if "other" in flags:
        (blue / "other.py").write_text("# " + name + chr(10), encoding="utf-8")
    if "nochange" not in flags:
        (blue / "feature.py").write_text("# " + name + " " + phase + "\n", encoding="utf-8")
    if "switch" in flags:
        git("switch", "-q", "-c", "rogue")
    if "commit" in flags:
        git("add", "backend/app/agents/blue")
        git("commit", "-q", "-m", "model commit")
    reply = {"task": task, "summary": "done", "files_changed": ["backend/app/agents/blue/feature.py"],
             "tests_run": ["blue tests"], "tests_passed": True, "remaining": ""}
elif phase == "review":
    if "reviewer-write" in flags:
        pathlib.Path("backend/app/agents/blue/feature.py").write_text("# fixed by reviewer\n", encoding="utf-8")
    verdict = "security-objection" if "review-security" in flags else "changes-requested" if "changes" in flags else "approve"
    reply = {"task": task, "verdict": verdict, "summary": name + " reviewed",
             "findings": [{"file": "backend/app/agents/blue/feature.py", "line": 1, "severity": "low", "issue": "naming"}]}
elif phase == "probe":
    if "probe-write" in flags:
        pathlib.Path("backend/app/agents/blue/.doctor-probe").write_text("probe", encoding="utf-8")
    reply = {"task": task, "stance": "abstain", "reason": "write blocked"}
elif phase == "strategy":
    reply = {"proposals": [{"lens": "security", "problem": "p", "change": "c", "owner": "blue", "file": "f"}]}
else:
    reply = {"task": task, "answer": name + " answers", "stance": "agree"}
if "wrongtask" in flags:
    reply["task"] = "B-00"
text = "I think this is fine." if "malformed" in flags else json.dumps(reply)
if name == "claude":
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text}))
elif name == "codex":
    out = args[args.index("--output-last-message") + 1]
    pathlib.Path(out).write_text(text, encoding="utf-8")
    print("codex log line")
elif "denied" in flags:
    print(json.dumps({"conversation_id": "c1", "status": "SUCCESS", "response": "",
                      "denied_actions": [{"action": "command", "display_name": "RunCommand"}]}))
    print("jetski: no output produced - a tool required the command permission that headless mode cannot prompt for, so it was auto-denied.", file=sys.stderr)
else:
    envelope = {"conversation_id": "c1", "status": "SUCCESS", "response": text + chr(10) + text, "num_turns": 2}
    if "malformed" not in flags and "no-structured" not in flags:
        envelope["structured_output"] = reply
    print(json.dumps(envelope))
'''


def run(args, cwd, env=None, stdin=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, **(env or {})}, input=stdin)


class Sandbox:
    """A throwaway repository on branch Mayo with the guard installed and fake model CLIs."""

    def __init__(self, models=("claude", "codex", "antigravity")):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.log = self.base / "calls.log"
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("config", "core.autocrlf", "false")
        shutil.copytree(SOURCE, self.root / "blue-team", ignore=shutil.ignore_patterns(
            "runs", "__pycache__", ".board.lock", "tests", "comms", "decisions", "state", "STATUS.md", ".obsidian"))
        for hook in (self.root / "blue-team" / "hooks").iterdir():
            hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
        fake = self.base / "fake_model.py"
        fake.write_text(FAKE_MODEL, encoding="utf-8")
        config = json.loads((self.root / "blue-team/config.json").read_text(encoding="utf-8"))
        config["checks"] = [{"name": "ok", "cwd": ".", "command": [
            "{python}", "-c", "import os, sys; sys.exit(1 if os.environ.get('FAKE_CHECK_FAIL') else 0)"]}]
        for name in list(config["models"]):
            if name not in models:
                del config["models"][name]
                continue
            spec = config["models"][name]
            spec["executable"] = [sys.executable]
            spec["prefix"] = [str(fake), name]
            spec["auth_command"] = ["auth-status"]
            spec["timeout_seconds"] = {"read": 60, "write": 60}
        config["policy"]["implementer_tiebreak"] = [m for m in config["policy"]["implementer_tiebreak"] if m in models]
        config["policy"]["min_reviewers"] = min(config["policy"]["min_reviewers"], max(len(models) - 1, 1))
        self.config = config
        self.save_config()
        tasks = [{"id": "B-90", "title": "Sample task", "milestone": "M1", "status": "todo", "owner": None,
                  "reviewers": [], "notes": "", "commits": [], "context": [], "updated": "2026-01-01T00:00:00Z"}]
        (self.root / "blue-team/tasks.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
        blue = self.root / "backend/app/agents/blue"
        blue.mkdir(parents=True)
        (blue / "__init__.py").write_text("", encoding="utf-8")
        (blue / "AGENTS.md").write_text("Read blue-team/AGENTS.md first.\n", encoding="utf-8")
        (self.root / "README.md").write_text("shared file\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        self.git("switch", "-q", "-c", "Mayo")
        assert self.script("guard.py", "install").returncode == 0

    def save_config(self):
        (self.root / "blue-team/config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")

    def git(self, *args, check=True):
        result = run(["git", *args], self.root)
        if check and result.returncode != 0:
            raise AssertionError(f"git {args} failed: {result.stderr}")
        return result

    def script(self, name, *args, env=None, stdin=""):
        env = {"FAKE_LOG": str(self.log), "FAKE_COUNTER": str(self.base / "counter"), **(env or {})}
        return run([sys.executable, str(self.root / "blue-team/bin" / name), *args], self.root, env, stdin)

    def orchestrate(self, *args, **env):
        return self.script("orchestrate.py", *args, env=env)

    def write(self, relative, text="x\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def state(self, task="B-90"):
        path = self.root / f"blue-team/state/{task}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def tasks(self):
        return {t["id"]: t for t in json.loads((self.root / "blue-team/tasks.json").read_text(encoding="utf-8"))["tasks"]}

    def thread(self, name="B-90"):
        path = self.root / f"blue-team/comms/threads/{name}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def close(self):
        self.tmp.cleanup()
