# Heist Range (working title)

An adaptive Red Team vs. Blue Team cyber range for RowdyHacks 2026, built around a fictional bank and a protected vault.

> **Status:** This repository currently contains only this planning README. The project name, arena technology, and implementation details are still open. The team can plan and prepare before the hackathon; the integrated contest and final demo will be built during the event.

## First mission

Red explores the registered bank lab, gathers evidence, and chooses an approach during the run. Blue independently monitors permitted telemetry and responds while the contest is active. An independent referee determines whether Red reached the protected vault data.

The first mission should preserve legitimate bank access and distinguish attempted attacks, verified vulnerabilities, applied responses, and fixes that have passed a retest. A bounded availability-disruption scenario may follow as a separate mission; an outage does not count as vault access.

## Starting team shape

- **Joseph — Red Team:** Develop a Scout to explore and record evidence, then an Operator to evaluate promising paths and attempt the heist. Red adapts to Blue’s responses rather than following a fixed attack script.
- **Aaron — Blue Team:** Extend the existing Blue work. A Monitor analyzes sanitized telemetry; a Defender recommends or performs bounded responses. Blue does not receive Red’s private plans or findings.
- **Diego — Core and bank lab:** Build the control plane that starts and stops sessions, dispatches tasks, enforces target and tool limits, records events, supports pause/reset, and supplies an independent referee. Build a separate, resettable bank website/API using synthetic accounts and controlled vulnerabilities.
- **Omar — Arena:** Create the judge-facing view of agents, tasks, status, and contest events. The starting visual direction is a 3D bank with 2D agent characters; Omar can revise the component plan and pitch visual alternatives before the team commits. His framework and implementation choices remain open.

The initial roster aims for two specialist agents per team. Expand the agent count and vulnerability coverage after the first complete contest loop works.

## Safety and evidence boundaries

- Run security tools only against registered, isolated lab targets we control. Do not target arbitrary external websites or networks.
- Use synthetic data and resettable lab state.
- Keep Red, Blue, and referee contexts separate. Only the referee receives seeded vulnerability ground truth.
- Enforce permissions, budgets, timeouts, and cancellation outside the models.
- Keep automatic Blue responses narrow and reversible; review broader changes and retest fixes.
- Label fixture events and live events accurately. The arena must reflect recorded activity, not present simulated events as live.

## Preparation and event work

Before the hackathon, the team can agree on task/event contracts, inventory Aaron’s existing Blue behavior and tests, research references, and sketch or prototype ideas. During the event, the team will integrate the lab, core, agents, and arena; prove the vault mission end to end; then add the separate availability mission only if the first loop is reliable and time remains.

This README is the only file in the repository for now. Role packets, draft contracts, milestones, and evaluation plans can be added when the team is ready.
