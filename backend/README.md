# Backend implementation boundary

The first core slice is standard-library Python under `backend/app/core/`:

- `TargetRegistry` resolves only registered target IDs and versions.
- `BoundedHttpExecutor` resolves credential references internally, enforces a
  request budget, rejects origin/path escapes, uses bounded timeouts, and does
  not follow redirects.
- `IndependentReferee` creates fresh account sessions through a trusted adapter,
  replays a candidate, and returns `verified`, `rejected`, or `inconclusive`
  independently of red's evidence.
- `GuidedAccessControlRun` runs the local golden scenario through SQLite-backed
  events, blue containment, fresh-session adaptation, a known-good disposable
  patch target, and regression retesting.

The executor, referee, and guided run are tested against the local storefront.
The production assessment API, cancellation, and SSE remain open. Keep API
routes thin when added. Separate orchestration, agent decisions, deterministic
tools, persistence, and evaluation. Red and blue receive different contexts.

From the repository root:

```sh
python3 -m unittest discover -s backend/tests/core -p "test_*.py" -v
```
