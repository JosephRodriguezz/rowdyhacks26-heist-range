# Thread handoffs: Requests for other team members

### 2026-10-01T04:52:20Z | claude | handoff

Open requests from blue:

- Member 3 (cyber_range/): which file handles GET /api/orders/{id}? ownership-fix-001 stays a draft until we know (B-13).
- Member 2 (backend core, shared/): (a) the executor must refuse patches whose manifest status is draft; (b) the shape of previous_defenses passed to blue; (c) an endpoint to fetch the incident report, such as GET /api/assessments/{id}/incident-report (B-12).
- Member 1 (frontend/): a report download in the evidence panel once (c) exists.

### 2026-10-01T23:21:52Z | claude | handoff

For Member 2 (scripts/): scripts/doctor.py crashes on Windows. shutil.which('npm') finds npm.CMD, but subprocess.run(['npm', '--version']) raises FileNotFoundError, which probe() does not catch (it catches only TimeoutExpired and IndexError). Suggested fix: run the resolved path from shutil.which, and catch OSError as OPTIONAL NOT READY. Found after merging codex/team-frameworks into Mayo (52d2a05).
