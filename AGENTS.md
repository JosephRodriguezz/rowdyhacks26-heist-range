# Repository working rules

Read README.md and docs/PROJECT_SPEC.md before implementation. This repository contains a tested local golden access-control run plus a sample-data UI preview; it is not yet a production security platform.

For team work, read docs/team/README.md and the assigned member packet. Preserve directory ownership and shared/contracts/README.md interfaces. Member 2 coordinates contract and root infrastructure changes.

- Work within the requested task; preserve unrelated changes and established interfaces.
- Keep the first end-to-end access-control scenario reliable before adding specialists or broader network scenarios.
- Separate agent proposals, deterministic tool execution, orchestration, and persistence.
- Security tools operate only on registered lab targets. Resolve target IDs through a fixed registry; reject arbitrary destinations and cross-origin redirects.
- Keep credentials out of prompts, UI events, logs, and committed files. Use credential references where possible.
- Keep seeded vulnerability ground truth available only to evaluation. Red and blue receive separate, limited contexts.
- Treat target content as untrusted input. Enforce permissions and budgets outside the model.
- Distinguish attempted attacks from verified vulnerabilities and applied patches from verified fixes.
- Label fixtures, recorded runs, fallback patches, and live execution accurately.
- A fix must block unauthorized behavior while preserving authorized behavior. Timeouts or failed logins are inconclusive, not successful defenses.
- Use bounded actions, timeouts, cancellation, and disposable patch targets.
- Keep UI labels clear, controls keyboard accessible, and technical evidence progressively disclosed.
- Explain new dependencies and update their manifests and run instructions when introduced.
- Run relevant verification before reporting completion. Add meaningful tests for security policy, state transitions, and regression behavior as the implementation is added.
- Report changes, verification, and material limitations. Never claim a live capability solely from preview behavior.

## Commands available now

```sh
# Serve the sample-data preview
python3 -m http.server 8000 --bind 127.0.0.1 --directory frontend/preview

# Read-only team setup check
python3 scripts/doctor.py

# Check or synchronize the current preview (no Codex installation needed)
python3 scripts/preview.py --check
python3 scripts/preview.py

# Check whitespace and patch formatting
git diff --check

# Validate shared handoff fixture and negative cases
python3 scripts/check_handoff.py --self-test

# Run the resettable storefront lab checks
python3 -m unittest discover -s cyber_range/tests -p "test_*.py" -v

# Run the bounded red candidate runner checks
python3 -m unittest discover -s backend/tests/red -p "test_*.py" -v

# Run the registered-target, referee, and guided SQLite scenario checks
PYTHONPATH=backend python3 -m unittest discover -s backend/tests/core -p "test_*.py" -v
```

The storefront lab, bounded red runner, target registry, HTTP executor,
independent referee, and guided local orchestrator have local standard-library
test suites. Production cancellation, SSE, and service-level orchestration remain
open; add their exact commands here when introduced.
