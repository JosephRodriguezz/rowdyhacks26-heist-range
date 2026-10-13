"""Deterministic rules mapping a discovered surface to an agent assignment, optimized
for the minimum number of agents the discovered surface actually needs -- never one
assignment per path, per form, or per port. This consumes real data (verified
engagements, real port-scan results); it does not discover anything itself.

Why web and network surfaces are discovered differently: an engagement's own
declared scope (engagement.py) already *is* the web surface -- there is no generic
crawler in this codebase (the only existing survey, baseline.py's run_surface_survey,
is entirely Diego's-bank-specific exploit logic, not reusable recon), and nothing
here invents one. A network target's open ports are genuinely unknown until scanned
(network.py), so that side of delegation only has something to decide once a real
scan has run.

Deliberately rule-based, not live-model: this project's pattern throughout has been
to prove a deterministic mechanism before ever reaching for a live model, and "one
agent per distinct surface, capped at a ceiling" is itself more tractable as a fixed
rule than as something to trust a model's judgment on for cost/efficiency reasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .actions import ActionExecutor
from .board import RedBoard
from .engagement import EngagementRegistry
from .network import NetworkScanError, NetworkScanExecutor, NetworkTargetRegistry, PortScanResult
from .vulnerability import (
    VulnerabilityFinding,
    test_session_reuse_after_logout,
    test_unauthenticated_network_access,
)

AgentType = Literal["web_pentest", "network_pentest"]

# The capabilities that make an engagement "web" work for delegation purposes --
# matches exactly what actions.py's engagement-backed dispatch path can reach.
WEB_CAPABILITIES = frozenset({
    "request_api", "read_page", "start_account_session", "end_account_session", "submit_form",
})


@dataclass(frozen=True)
class AgentAssignment:
    """One agent's worth of work: a single distinct surface, never a sub-slice of
    one. A network assignment carries every open port found on that one host, not
    one assignment per port -- that is the actual optimization this module exists
    for, not a detail of it."""

    agent_type: AgentType
    target_id: str
    reason: str
    open_ports: tuple[int, ...] = ()  # populated only for network_pentest


@dataclass(frozen=True)
class DelegationPlan:
    """assignments is what to actually act on; deferred is what would have been
    assigned if max_agents were higher -- surfaced, not silently dropped, since
    this plan is meant to inform whoever (human or future system) decides whether
    to raise the ceiling, not to hide that work exists."""

    assignments: tuple[AgentAssignment, ...]
    deferred: tuple[AgentAssignment, ...]

    @property
    def total_considered(self) -> int:
        return len(self.assignments) + len(self.deferred)


def delegate(
    *,
    engagement_registry: EngagementRegistry | None = None,
    network_results: dict[str, list[PortScanResult]] | None = None,
    network_registry: NetworkTargetRegistry | None = None,
    max_agents: int = 10,
) -> DelegationPlan:
    """Build a delegation plan from real, already-gathered discovery data.

    One assignment per distinct surface, in registration order (the same
    deterministic ordering engagement_registry.engagements()/
    network_registry.targets() already give): one per verified engagement with at
    least one web capability in its scope, one per verified network target with at
    least one open port actually found in network_results. Never one per path, per
    form, or per port -- and never for anything that isn't verified, regardless of
    what network_results claims, since a result for an unverified or unknown target
    id is not something this function will act on.
    """
    if max_agents < 1:
        raise ValueError("max_agents must be at least 1")
    if network_results and network_registry is None:
        raise ValueError("network_results requires network_registry to confirm verification; "
                          "never delegate against scan data with nothing to verify it")

    candidates: list[AgentAssignment] = []

    if engagement_registry is not None:
        for engagement in engagement_registry.engagements():
            if engagement.status != "verified":
                continue
            web_caps = engagement.scope.allowed_capabilities & WEB_CAPABILITIES
            if not web_caps:
                continue
            candidates.append(AgentAssignment(
                agent_type="web_pentest", target_id=engagement.target_id,
                reason=f"verified engagement with {len(web_caps)} web capability(ies) in scope",
            ))

    if network_results:
        for target_id, results in network_results.items():
            open_ports = tuple(sorted(r.port for r in results if r.state == "open"))
            if not open_ports:
                continue
            try:
                network_registry.resolve(target_id)  # raises if unregistered or not verified
            except NetworkScanError:
                continue
            candidates.append(AgentAssignment(
                agent_type="network_pentest", target_id=target_id,
                reason=f"{len(open_ports)} open port(s) discovered",
                open_ports=open_ports,
            ))

    assignments = tuple(candidates[:max_agents])
    deferred = tuple(candidates[max_agents:])
    return DelegationPlan(assignments=assignments, deferred=deferred)


def scan_and_delegate(
    *,
    engagement_registry: EngagementRegistry | None = None,
    network_registry: NetworkTargetRegistry | None = None,
    network_executor: NetworkScanExecutor | None = None,
    max_agents: int = 10,
) -> DelegationPlan:
    """Convenience: actually runs each verified network target's own declared port
    range through network_executor (respecting its scope's own rate/concurrency
    ceiling, same as any other use of the executor -- a wide range at a tight
    ceiling will genuinely take as long as that implies, which is correct, not a
    bug), then calls delegate() with the real results. Still never discovers the
    web surface itself -- an engagement's own declared scope already is that
    discovery, by design; see delegate()'s own docstring for why.
    """
    network_results: dict[str, list[PortScanResult]] = {}
    if network_registry is not None and network_executor is not None:
        for target in network_registry.targets():
            if target.status != "verified":
                continue
            ports = list(range(target.scope.min_port, target.scope.max_port + 1))
            network_results[target.target_id] = network_executor.scan_ports(target.target_id, ports)
    return delegate(
        engagement_registry=engagement_registry, network_results=network_results,
        network_registry=network_registry, max_agents=max_agents,
    )


def execute_web_pentest_assignment(
    assignment: AgentAssignment,
    *,
    executor: ActionExecutor,
    engagement_registry: EngagementRegistry,
    board: RedBoard,
    task_id: str,
) -> list[VulnerabilityFinding]:
    """Runs every web vulnerability test this project currently has, against every
    identity the engagement's own SiteProfile declares. Today that is exactly one
    test (session reuse after logout); as more web vulnerability tests are added,
    this is the one place that wires a new one into every web_pentest assignment,
    not something each caller has to remember to add separately. An engagement with
    no profile, or no declared identities, correctly yields no findings -- there is
    nothing this test can log in with, not an error."""
    if assignment.agent_type != "web_pentest":
        raise ValueError(f"execute_web_pentest_assignment only handles web_pentest assignments, got {assignment.agent_type!r}")
    engagement = engagement_registry.resolve(assignment.target_id)  # raises if no longer verified
    findings: list[VulnerabilityFinding] = []
    if engagement.profile is None:
        return findings
    for identity_ref in engagement.profile.identities:
        findings.append(test_session_reuse_after_logout(
            executor=executor, board=board, task_id=task_id,
            target_id=assignment.target_id, identity_ref=identity_ref,
        ))
    return findings


def execute_network_pentest_assignment(
    assignment: AgentAssignment,
    *,
    network_executor: NetworkScanExecutor | None = None,
    board: RedBoard | None = None,
) -> list[VulnerabilityFinding]:
    """Runs the unauthenticated-access test against every open port the assignment
    carries. network_executor is optional so a caller with no network executor
    wired up still gets an honest empty list, never a fabricated finding or a
    crash -- same posture execute_web_pentest_assignment has for an engagement
    with no profile."""
    if assignment.agent_type != "network_pentest":
        raise ValueError(f"execute_network_pentest_assignment only handles network_pentest assignments, got {assignment.agent_type!r}")
    if network_executor is None or board is None:
        return []
    return [
        test_unauthenticated_network_access(
            network_executor=network_executor, board=board,
            target_id=assignment.target_id, port=port,
        )
        for port in assignment.open_ports
    ]


def execute_plan(
    plan: DelegationPlan,
    *,
    executor: ActionExecutor,
    board: RedBoard,
    engagement_registry: EngagementRegistry | None = None,
    network_executor: NetworkScanExecutor | None = None,
) -> dict[str, list[VulnerabilityFinding]]:
    """Runs whatever vulnerability tests exist for each assignment in plan.assignments
    -- never plan.deferred, which was explicitly not assigned and is not this
    function's to act on. One claimed task per assignment, matching the one-agent-
    per-surface model delegate() already enforces: this is that one agent's own
    unit of work, not everything lumped under one shared task. Returns a mapping of
    target_id -> findings; a network_pentest assignment yields an empty list for
    that target, not an error, when network_executor is not supplied.
    """
    results: dict[str, list[VulnerabilityFinding]] = {}
    for assignment in plan.assignments:
        task = board.add_task("scout", f"{assignment.agent_type} assignment for {assignment.target_id}")
        if not board.claim_task(task.task_id, f"{assignment.agent_type}-agent"):
            raise RuntimeError(f"could not claim the task for {assignment.target_id}")
        if assignment.agent_type == "web_pentest":
            if engagement_registry is None:
                raise ValueError("web_pentest assignments require engagement_registry")
            findings = execute_web_pentest_assignment(
                assignment, executor=executor, engagement_registry=engagement_registry,
                board=board, task_id=task.task_id,
            )
        elif assignment.agent_type == "network_pentest":
            findings = execute_network_pentest_assignment(
                assignment, network_executor=network_executor, board=board,
            )
        else:
            raise ValueError(f"unknown agent_type: {assignment.agent_type!r}")
        results[assignment.target_id] = findings
        board.finish_task(task.task_id, "completed")
    return results
