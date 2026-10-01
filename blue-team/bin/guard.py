"""Branch, path, and history guardrails for every model and person using this clone.

Git hooks call this script. Commits happen only on the work branch and only inside
the commit paths (model paths plus orchestrator records). Threads are append-only,
committed decision records never change, and each task's state history only grows.
Pushes go only to the work branch, never forced, never deleting it. These hooks are
one layer of several: the orchestrator, CLI sandboxes, run snapshots, and tests are
the others, because client-side hooks can be bypassed.

    python blue-team/bin/guard.py install     # enable the hooks in this clone
    python blue-team/bin/guard.py check       # confirm it is safe to start work
    python blue-team/bin/guard.py verify      # check records against HEAD
    python blue-team/bin/guard.py uninstall   # disable the hooks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from common import ROOT, commit_paths, current_branch, git, in_paths, load_config

HOOKS_PATH = "blue-team/hooks"
ZERO = "0" * 40
THREADS = "blue-team/comms/threads/"
DECISIONS = "blue-team/decisions/"
STATE = "blue-team/state/"


def problems(config: dict) -> list[str]:
    found = []
    branch = current_branch()
    if branch != config["branch"]:
        found.append(f"Current branch is {branch or 'a detached HEAD'}, not {config['branch']}. "
                     f"Other branches are read-only: inspect them with git show or git log, never check them out to work.")
    if git("config", "--get", "core.hooksPath", check=False) != HOOKS_PATH:
        found.append("Guard hooks are not enabled. Run: python blue-team/bin/guard.py install")
    return found


def history_problem(path: str, old: str | None, new: str | None) -> str | None:
    """Rule for one record file. `old` is the committed text, `new` the proposed text (None = deleted)."""
    if not (path.startswith((THREADS, DECISIONS, STATE)) and not path.startswith(STATE + ".locks/")):
        return None
    if old is None:
        return None
    if new is None:
        return f"{path} is a shared record and cannot be deleted."
    if path.startswith(THREADS):
        return None if new.startswith(old) else f"{path} is append-only; earlier messages were changed."
    if path.startswith(DECISIONS):
        return None if new == old else f"{path} is a committed decision record and cannot change. Add a new decision."
    try:
        old_history, new_history = json.loads(old)["history"], json.loads(new)["history"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return f"{path} is not a valid state file."
    if new_history[:len(old_history)] != old_history:
        return f"{path} rewrites recorded state history; history is append-only."
    return None


def pre_commit(config: dict) -> int:
    branch = current_branch()
    if branch != config["branch"]:
        return _block(f"commits are only allowed on {config['branch']} (current: {branch or 'detached HEAD'}).")
    merging = bool(git("rev-parse", "-q", "--verify", "MERGE_HEAD", check=False))
    staged = [p for p in git("diff", "--cached", "--name-only", "--no-renames", "-z").split("\0") if p]
    if merging:
        print(f"blue-team guard: merge in progress on {branch}; path limits are not applied to merged files.",
              file=sys.stderr)
    else:
        outside = [p for p in staged if not in_paths(p, commit_paths(config))]
        if outside:
            listing = "\n  ".join(outside)
            return _block(f"these staged paths are outside the blue-team write paths:\n  {listing}\n"
                          f"Allowed: {', '.join(commit_paths(config))}. Ask the owning teammate to change other files.")
    found = [p for p in (history_problem(path, _blob("HEAD", path), _blob("", path)) for path in staged) if p]
    if found:
        return _block("\n  ".join(["record history must not be rewritten:"] + found))
    return 0


def verify(config: dict) -> list[str]:
    """Compare working-tree records with HEAD using the same rules as the pre-commit hook."""
    tracked = git("ls-files", "-z", "--", THREADS, DECISIONS, STATE, check=False).split("\0")
    found = []
    for path in (p for p in tracked if p):
        current = ROOT / path
        new = current.read_text(encoding="utf-8") if current.is_file() else None
        problem = history_problem(path, _blob("HEAD", path), new)
        if problem:
            found.append(problem)
    return found


def pre_push(config: dict, remote_name: str, lines: list[str]) -> int:
    if remote_name != config["remote"]:
        return _block(f"pushes may only go to the {config['remote']} remote (got {remote_name}).")
    allowed_ref = f"refs/heads/{config['branch']}"
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, remote_sha = parts
        if remote_ref != allowed_ref or local_ref != allowed_ref:
            return _block(f"only {config['branch']} may be pushed, to {config['branch']} (got {local_ref} -> {remote_ref}).")
        if local_sha == ZERO:
            return _block(f"deleting the remote {config['branch']} branch is not allowed.")
        if remote_sha != ZERO:
            ancestor = _is_ancestor(remote_sha, local_sha)
            if ancestor is None:
                return _block("the remote has commits this clone does not have. Fetch and merge them first.")
            if not ancestor:
                return _block("force pushes and rewritten history are not allowed.")
    return 0


def post_checkout(config: dict, flag: str) -> int:
    branch = current_branch()
    if flag == "1" and branch != config["branch"]:
        print(f"blue-team guard: you are on {branch or 'a detached HEAD'}. It is read-only for agents; "
              f"commits are blocked. Return with: git switch {config['branch']}", file=sys.stderr)
    return 0


def install() -> int:
    git("config", "core.hooksPath", HOOKS_PATH)
    print(f"Guard hooks enabled ({HOOKS_PATH}). Commits are limited to the configured branch and paths.")
    return 0


def uninstall() -> int:
    if git("config", "--get", "core.hooksPath", check=False) == HOOKS_PATH:
        git("config", "--unset", "core.hooksPath")
        print("Guard hooks disabled.")
    else:
        print("Guard hooks were not enabled; nothing changed.")
    return 0


def check(config: dict) -> int:
    print(f"Repository: {ROOT}")
    print(f"Branch:     {current_branch() or 'detached HEAD'} (work branch: {config['branch']})")
    found = problems(config) + verify(config)
    for problem in found:
        print(f"BLOCKED: {problem}")
    if not found:
        print("OK: safe to work. Run python blue-team/bin/orchestrate.py doctor for model status.")
    return 1 if found else 0


def _blob(ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _is_ancestor(older: str, newer: str) -> bool | None:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=ROOT,
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _block(message: str) -> int:
    print(f"blue-team guard: BLOCKED: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blue-team branch, path, and history guardrails.")
    parser.add_argument("command", choices=("check", "install", "uninstall", "verify", "pre-commit", "pre-push",
                                            "post-checkout"))
    parser.add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    config = load_config()
    if args.command == "check":
        return check(config)
    if args.command == "install":
        return install()
    if args.command == "uninstall":
        return uninstall()
    if args.command == "verify":
        found = verify(config)
        print("\n".join(found) or "Records match HEAD history rules.")
        return 1 if found else 0
    if args.command == "pre-commit":
        return pre_commit(config)
    if args.command == "pre-push":
        return pre_push(config, args.args[0] if args.args else "", sys.stdin.read().splitlines())
    return post_checkout(config, args.args[2] if len(args.args) > 2 else "")


if __name__ == "__main__":
    raise SystemExit(main())
