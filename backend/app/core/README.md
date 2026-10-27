# Core target and referee slice

This package is the first server-owned integration boundary. `guided.py` also
provides a local acceptance runner with an append-only SQLite event trail.

`TargetRegistry` is constructed by trusted core with fixed target origins.
Callers pass a target ID/version and an origin-relative path; arbitrary URLs,
cross-origin paths, and unsupported methods are rejected.

`BoundedHttpExecutor` receives credential references and keeps their raw tokens
inside the core-owned in-memory vault. Results contain status, sanitized JSON,
request/evidence IDs, and bounded errors. It never returns a token or follows a
redirect.

`IndependentReferee.verify()` does not trust a candidate's status or evidence.
It gets fresh owner and actor sessions through a trusted adapter, establishes an
owner baseline, and then replays the candidate. It returns a referee verdict;
red never writes or receives that verdict.

`GuidedAccessControlRun` sequences the local golden scenario: red discovery,
independent verification, blue containment, fresh-session adaptation, a named
known-good fallback on a disposable patched target, and independent regression
retesting. This is a local acceptance slice, not a production assessment API;
service orchestration, cancellation, SSE, and UI wiring remain open.
