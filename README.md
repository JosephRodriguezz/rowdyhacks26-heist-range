# RANGE — AI Red Team vs. Blue Team

An interactive cyber range for RowdyHacks: AI agents attack and defend an isolated lab website while a neutral referee verifies the results.

**Status:** project foundation and interactive UI preview. The preview uses sample data; live agents, the vulnerable application, defensive tools, and evaluation are not implemented yet.

## Project experience

1. Launch an assessment against a registered lab target.
2. Watch red discover and test an access-control weakness.
3. Inspect the request, response, and independent verification.
4. Watch blue detect the activity and apply a supported defense.
5. Retest the attack and legitimate access against the corrected application.
6. Review evidence, the event timeline, and scenario-scoped results.

Both teams act on different observations: red sees application behavior; blue sees telemetry and defensive controls. Only the evaluator sees seeded vulnerability ground truth.

## Explore the UI preview

Requires Python 3. No package installation is needed.

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory frontend/preview
```

Open <http://127.0.0.1:8000>. Select **Launch round**, **Apply defense**, and **Run retest**. Click services and activity entries to inspect details. The preview loads decorative icons from a CDN; core controls and text work without those icons.

The preview does not execute security tools, modify a target, or call a model provider.

## Repository map

```text
frontend/preview/         Standalone interactive dashboard preview
backend/                 Backend scope and implementation starting point
cyber_range/             Lab scope and isolation requirements
docs/PROJECT_SPEC.md      Current agreed direction and acceptance criteria
docs/ROADMAP.md           Implementation order and completion gates
docs/UI_DESIGN.md         Visual and interaction requirements
docs/design/             Editable dashboard design source
docs/reference/          Original supplied specification and review
AGENTS.md                Contributor and coding-agent working rules
```

## Planned implementation

- Frontend: React + TypeScript, live events via Server-Sent Events.
- Backend: Python + FastAPI, a bounded assessment runner, SQLite.
- Lab: one website/API with seeded private records and access-control challenges.
- Packaging: Docker Compose once the live services exist.

These are planned choices, not installed dependencies. There is no working Compose stack or live assessment API yet.

## MVP success criteria

From a clean reset, a judge can launch a round, inspect a reproducible vulnerability, apply a supported defense, and verify that unauthorized access fails while legitimate access succeeds. Results must identify the exact target version and distinguish live execution from recorded or sample data.

See [the current specification](docs/PROJECT_SPEC.md) and [roadmap](docs/ROADMAP.md). The original supplied documents are retained as references; the current specification takes precedence where they differ.
