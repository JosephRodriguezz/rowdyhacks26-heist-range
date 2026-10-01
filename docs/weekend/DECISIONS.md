# Kickoff decisions and fallback plan

## Fixed for the first slice

- One isolated website/API, one active assessment, two ordinary lab users, one ownership flaw, one protected control.
- Cops and robbers are role labels; auditor is independent verification. Scenery is not extra assessed infrastructure.
- Preserve the existing storefront target/record/endpoint contract for the weekend's first working cycle. A bank skin is already implemented; financial transfers and account-money mechanics are not part of this MVP.
- React + TypeScript frontend; Python + FastAPI core; SQLite; ordered SSE events; separate lab process/container. These remain planned until owners bootstrap them.
- Model agents propose actions; bounded tools execute; the referee checks policy deterministically. Root infrastructure belongs to Aaron.
- Freeze shared interfaces after H0:30 except coordinated changes with consumers and fixture updates.

## Decide together at H0

| Decision | Owner | Record choice here |
| --- | --- | --- |
| Confirm/swap roles | All | Provisional roster in START_HERE.md |
| Official prebuild/AI/submission rules | Joseph | Pending organizer check |
| Integration/demo laptop | Aaron | Pending |
| Provider/model and model-call timeout | Aaron + Diego + Omar | Pending; no keys in this document |
| Total spend and per-assessment token/request/step budgets | All, enforced by Aaron | Pending |
| Runtime versions and lockfile tooling | Aaron (Python), Joseph (frontend) | Pending bootstrapping |
| Scoped lab handler and patch format | Diego + Omar + Aaron | Pending RED-01 handoff |
| Judge presentation length and required submission fields | Joseph | Pending organizer details |

## Failure response

| Failure | Response |
| --- | --- |
| Provider unavailable / quota exhausted | Retry only within budget; mark run partial or failed. Use a labeled recorded run for explanation, or labeled deterministic demo. Never imply that scripted actions came from a live model. |
| Blue revokes a session but retry still works | Expected story beat: containment differs from fixing ownership. Continue to patch and retest. |
| Generated patch fails | Use a reviewed known-good patch only if supported, labeled `known_good_fallback`. Still run independent checks. |
| Lab offline, bad session, or timeout | Inconclusive; restore/reset and rerun. Do not count a denial caused by outage as protection. |
| Frontend fails during demo | Show backend evidence using a documented command; retain the city sample as a clearly labeled UI demonstration. |
| Behind schedule at H14 | Drop autonomous mode, more vulnerabilities, extra characters, camera controls, and generated patching. Keep the complete guided scenario. |
| Network/CDN fails | Core demo should run locally. Text, characters, and controls survive missing preview icons; cache/package production assets when the frontend is built. |

## Before merging live infrastructure

The receiving member checks exact startup ports and origin handling, scoped target registry, model egress separation, ignored environment files, and disposable reset behavior. Add runnable commands to AGENTS.md and README.md as each real service lands. Do not leave speculative commands appearing to work.
