"""Deterministic delegation rules (delegation.py), proven against real verified
engagements and real port-scan results -- never against invented/stubbed discovery
data, and never against Diego's bank or a third party.
"""

from __future__ import annotations

import unittest

from red.prototype.actions import ActionExecutor, FixedTargetRegistry
from red.prototype.board import BudgetLedger, RedBoard
from red.prototype.delegation import (
    AgentAssignment,
    delegate,
    execute_network_pentest_assignment,
    execute_plan,
    execute_web_pentest_assignment,
    scan_and_delegate,
)
from red.prototype.domain import RunLimits
from red.prototype.engagement import EngagementRegistry, EngagementScope, SiteProfile
from red.prototype.lab import LabState
from red.prototype.mocknetwork import MockNetworkHost
from red.prototype.mocksite import MockSiteServer, MockSiteState
from red.prototype.network import NetworkScanExecutor, NetworkScope, NetworkTargetRegistry, PortScanResult


class DelegateValidationTests(unittest.TestCase):
    def test_max_agents_must_be_at_least_one(self) -> None:
        with self.assertRaises(ValueError):
            delegate(max_agents=0)

    def test_network_results_without_a_registry_is_rejected(self) -> None:
        # Never delegate against scan data with nothing to confirm it was verified.
        with self.assertRaises(ValueError):
            delegate(network_results={"some-target": []})

    def test_no_discovery_data_at_all_yields_an_empty_plan(self) -> None:
        plan = delegate()
        self.assertEqual(plan.assignments, ())
        self.assertEqual(plan.deferred, ())
        self.assertEqual(plan.total_considered, 0)


class WebDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.site_state = MockSiteState()
        self.site = MockSiteServer(self.site_state).start()
        self.registry = EngagementRegistry()

    def tearDown(self) -> None:
        self.site.close()

    def _verified_engagement(self, target_id: str, capabilities: frozenset[str]):
        scope = EngagementScope(allowed_capabilities=capabilities)
        engagement = self.registry.register(target_id, self.site.origin, scope)
        self.site_state.set_authorization_token(target_id, engagement.verification_token)
        self.registry.verify(target_id)
        return engagement

    def test_one_verified_web_engagement_yields_exactly_one_assignment(self) -> None:
        self._verified_engagement("acme-web", frozenset({"request_api", "read_page"}))
        plan = delegate(engagement_registry=self.registry)
        self.assertEqual(len(plan.assignments), 1)
        assignment = plan.assignments[0]
        self.assertEqual(assignment.agent_type, "web_pentest")
        self.assertEqual(assignment.target_id, "acme-web")
        self.assertEqual(assignment.open_ports, ())

    def test_an_unverified_engagement_is_never_assigned(self) -> None:
        scope = EngagementScope(allowed_capabilities=frozenset({"request_api"}))
        self.registry.register("pending-web", self.site.origin, scope)  # never verified
        plan = delegate(engagement_registry=self.registry)
        self.assertEqual(plan.assignments, ())

    def test_a_scope_with_no_web_capability_is_never_assigned(self) -> None:
        # No real capability outside WEB_CAPABILITIES exists yet for engagements in
        # practice (the dispatch layer never allows load-test on one), so this uses
        # a capability name that exists in the codebase but is deliberately outside
        # the web set, to prove the filter itself rather than assert an unreachable
        # case can't happen for an unrelated reason.
        self._verified_engagement("non-web", frozenset({"start_load_test"}))
        plan = delegate(engagement_registry=self.registry)
        self.assertEqual(plan.assignments, ())

    def test_multiple_verified_engagements_each_get_their_own_assignment(self) -> None:
        self._verified_engagement("site-a", frozenset({"read_page"}))
        other_state = MockSiteState()
        with MockSiteServer(other_state) as other_site:
            other_scope = EngagementScope(allowed_capabilities=frozenset({"read_page"}))
            other_engagement = self.registry.register("site-b", other_site.origin, other_scope)
            other_state.set_authorization_token("site-b", other_engagement.verification_token)
            self.registry.verify("site-b")
            plan = delegate(engagement_registry=self.registry)
            self.assertEqual({a.target_id for a in plan.assignments}, {"site-a", "site-b"})
            self.assertEqual(len(plan.assignments), 2)  # never more than one per engagement


class NetworkDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verify_state = MockSiteState()
        self.verify_site = MockSiteServer(self.verify_state).start()
        self.net_host = MockNetworkHost()
        self.net_host.__enter__()
        self.registry = NetworkTargetRegistry()
        verify_host, verify_port = self.verify_site.httpd.server_address[:2]
        self.verify_host, self.verify_port = verify_host, verify_port

    def tearDown(self) -> None:
        self.verify_site.close()
        self.net_host.close()

    def _verified_target(self, target_id: str, scope: NetworkScope):
        target = self.registry.register(target_id, self.verify_host, scope, verification_port=self.verify_port)
        self.verify_state.set_authorization_token(target_id, target.verification_token)
        self.registry.verify(target_id)
        return target

    def test_a_target_with_open_ports_yields_one_assignment_carrying_every_port(self) -> None:
        port_a = self.net_host.open_port(port=28_001)
        port_b = self.net_host.open_port(port=28_002)
        scope = NetworkScope(min_port=28_000, max_port=28_010)
        self._verified_target("acme-net", scope)
        results = {"acme-net": [
            PortScanResult(port_a, "open"), PortScanResult(port_b, "open"), PortScanResult(28_003, "closed"),
        ]}
        plan = delegate(network_results=results, network_registry=self.registry)
        self.assertEqual(len(plan.assignments), 1)  # one agent, not one per port
        assignment = plan.assignments[0]
        self.assertEqual(assignment.agent_type, "network_pentest")
        self.assertEqual(set(assignment.open_ports), {port_a, port_b})

    def test_a_target_with_no_open_ports_is_never_assigned(self) -> None:
        scope = NetworkScope(min_port=28_000, max_port=28_010)
        self._verified_target("acme-net", scope)
        results = {"acme-net": [PortScanResult(28_001, "closed"), PortScanResult(28_002, "filtered")]}
        plan = delegate(network_results=results, network_registry=self.registry)
        self.assertEqual(plan.assignments, ())

    def test_results_for_an_unverified_target_are_never_assigned(self) -> None:
        scope = NetworkScope(min_port=28_000, max_port=28_010)
        self.registry.register("pending-net", self.verify_host, scope, verification_port=self.verify_port)
        results = {"pending-net": [PortScanResult(28_001, "open")]}
        plan = delegate(network_results=results, network_registry=self.registry)
        self.assertEqual(plan.assignments, ())

    def test_results_for_a_completely_unknown_target_id_are_never_assigned(self) -> None:
        results = {"never-registered": [PortScanResult(28_001, "open")]}
        plan = delegate(network_results=results, network_registry=self.registry)
        self.assertEqual(plan.assignments, ())

    def test_scan_and_delegate_runs_a_real_scan_and_delegates_from_it(self) -> None:
        open_port = self.net_host.open_port(port=28_022, banner="SSH-2.0-Mock\r\n")
        self.net_host.reserve_closed_port(port=28_023)
        scope = NetworkScope(min_port=28_020, max_port=28_030, scan_timeout_seconds=0.1)
        self._verified_target("acme-net", scope)
        executor = NetworkScanExecutor(registry=self.registry)
        plan = scan_and_delegate(network_registry=self.registry, network_executor=executor)
        self.assertEqual(len(plan.assignments), 1)
        self.assertEqual(plan.assignments[0].open_ports, (open_port,))


class DelegationCeilingTests(unittest.TestCase):
    """Mixed web + network surfaces, proving the max_agents ceiling defers rather
    than silently drops excess work, and that priority is deterministic (web
    candidates are always considered before network ones)."""

    def setUp(self) -> None:
        self.web_state = MockSiteState()
        self.web_site = MockSiteServer(self.web_state).start()
        self.verify_state = MockSiteState()
        self.verify_site = MockSiteServer(self.verify_state).start()
        self.net_host = MockNetworkHost()
        self.net_host.__enter__()

        self.eng_registry = EngagementRegistry()
        eng_scope = EngagementScope(allowed_capabilities=frozenset({"read_page"}))
        engagement = self.eng_registry.register("acme-web", self.web_site.origin, eng_scope)
        self.web_state.set_authorization_token("acme-web", engagement.verification_token)
        self.eng_registry.verify("acme-web")

        verify_host, verify_port = self.verify_site.httpd.server_address[:2]
        self.open_port = self.net_host.open_port(port=28_040)
        self.net_registry = NetworkTargetRegistry()
        net_scope = NetworkScope(min_port=28_030, max_port=28_050, scan_timeout_seconds=0.1)
        net_target = self.net_registry.register("acme-net", verify_host, net_scope, verification_port=verify_port)
        self.verify_state.set_authorization_token("acme-net", net_target.verification_token)
        self.net_registry.verify("acme-net")
        self.executor = NetworkScanExecutor(registry=self.net_registry)

    def tearDown(self) -> None:
        self.web_site.close()
        self.verify_site.close()
        self.net_host.close()

    def test_both_surfaces_get_their_own_assignment_when_the_ceiling_allows(self) -> None:
        plan = scan_and_delegate(engagement_registry=self.eng_registry, network_registry=self.net_registry,
                                  network_executor=self.executor, max_agents=10)
        self.assertEqual(len(plan.assignments), 2)
        self.assertEqual(plan.deferred, ())
        self.assertEqual({a.agent_type for a in plan.assignments}, {"web_pentest", "network_pentest"})

    def test_a_tight_ceiling_defers_rather_than_drops_the_excess(self) -> None:
        plan = scan_and_delegate(engagement_registry=self.eng_registry, network_registry=self.net_registry,
                                  network_executor=self.executor, max_agents=1)
        self.assertEqual(len(plan.assignments), 1)
        self.assertEqual(len(plan.deferred), 1)
        self.assertEqual(plan.total_considered, 2)
        # Deterministic priority: web is considered before network when the ceiling bites.
        self.assertEqual(plan.assignments[0].agent_type, "web_pentest")
        self.assertEqual(plan.deferred[0].agent_type, "network_pentest")


class ExecuteAssignmentTests(unittest.TestCase):
    """Closing the loop: a web_pentest assignment actually runs the available
    vulnerability tests against the real mock site; a network_pentest assignment
    honestly yields nothing yet, rather than fabricated coverage."""

    def setUp(self) -> None:
        self.mock_state = MockSiteState()
        self.mock_state.add_account("alice@example.com", "correct-horse")
        self.mocksite = MockSiteServer(self.mock_state).start()
        self.profile = SiteProfile(
            login_path="/login", session_cookie_name="acme_session", logout_path="/logout",
            identities={"alice": {"email": "alice@example.com", "password": "correct-horse"}},
        )
        self.scope = EngagementScope(allowed_capabilities=frozenset({
            "request_api", "read_page", "start_account_session", "end_account_session",
        }))
        self.registry = EngagementRegistry()
        self.engagement = self.registry.register("acme-web", self.mocksite.origin, self.scope, profile=self.profile)
        self.mock_state.set_authorization_token("acme-web", self.engagement.verification_token)
        self.registry.verify("acme-web")
        self.state = LabState("clean")
        self.board = RedBoard()
        self.limits = RunLimits()
        self.budget = BudgetLedger(self.limits)
        self.executor = ActionExecutor(
            registry=FixedTargetRegistry("http://127.0.0.1:1"), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, engagement_registry=self.registry,
        )

    def tearDown(self) -> None:
        self.executor.close()
        self.mocksite.close()
        self.state.close()

    def _task_id(self) -> str:
        task = self.board.add_task("scout", "test")
        self.board.claim_task(task.task_id, "test")
        return task.task_id

    def test_web_pentest_assignment_runs_the_real_test_against_the_real_site(self) -> None:
        self.mock_state.session_fixation_vulnerable = True
        assignment = AgentAssignment(agent_type="web_pentest", target_id="acme-web", reason="test")
        findings = execute_web_pentest_assignment(
            assignment, executor=self.executor, engagement_registry=self.registry,
            board=self.board, task_id=self._task_id(),
        )
        self.assertEqual(len(findings), 1)  # one identity (alice) declared in the profile
        self.assertEqual(findings[0].verdict, "vulnerable")

    def test_web_pentest_assignment_runs_one_test_per_declared_identity(self) -> None:
        self.mock_state.add_account("bob@example.com", "another-horse")
        registry = EngagementRegistry()
        profile = SiteProfile(
            login_path="/login", session_cookie_name="acme_session", logout_path="/logout",
            identities={
                "alice": {"email": "alice@example.com", "password": "correct-horse"},
                "bob": {"email": "bob@example.com", "password": "another-horse"},
            },
        )
        engagement = registry.register("acme-web", self.mocksite.origin, self.scope, profile=profile)
        self.mock_state.set_authorization_token("acme-web", engagement.verification_token)
        registry.verify("acme-web")
        executor = ActionExecutor(
            registry=FixedTargetRegistry("http://127.0.0.1:1"), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, engagement_registry=registry,
        )
        try:
            assignment = AgentAssignment(agent_type="web_pentest", target_id="acme-web", reason="test")
            findings = execute_web_pentest_assignment(
                assignment, executor=executor, engagement_registry=registry,
                board=self.board, task_id=self._task_id(),
            )
            self.assertEqual(len(findings), 2)
        finally:
            executor.close()

    def test_web_pentest_assignment_with_no_profile_yields_no_findings_not_an_error(self) -> None:
        registry = EngagementRegistry()
        engagement = registry.register("no-profile-site", self.mocksite.origin, self.scope)  # no profile=
        self.mock_state.set_authorization_token("no-profile-site", engagement.verification_token)
        registry.verify("no-profile-site")
        assignment = AgentAssignment(agent_type="web_pentest", target_id="no-profile-site", reason="test")
        findings = execute_web_pentest_assignment(
            assignment, executor=self.executor, engagement_registry=registry,
            board=self.board, task_id=self._task_id(),
        )
        self.assertEqual(findings, [])

    def test_web_pentest_executor_rejects_a_network_pentest_assignment(self) -> None:
        assignment = AgentAssignment(agent_type="network_pentest", target_id="acme-net", reason="test",
                                      open_ports=(22,))
        with self.assertRaises(ValueError):
            execute_web_pentest_assignment(
                assignment, executor=self.executor, engagement_registry=self.registry,
                board=self.board, task_id=self._task_id(),
            )

    def test_network_pentest_assignment_always_yields_an_empty_list_today(self) -> None:
        assignment = AgentAssignment(agent_type="network_pentest", target_id="acme-net", reason="test",
                                      open_ports=(22, 80))
        self.assertEqual(execute_network_pentest_assignment(assignment), [])

    def test_network_pentest_executor_rejects_a_web_pentest_assignment(self) -> None:
        assignment = AgentAssignment(agent_type="web_pentest", target_id="acme-web", reason="test")
        with self.assertRaises(ValueError):
            execute_network_pentest_assignment(assignment)

    def test_execute_plan_runs_one_task_per_assignment_and_reports_per_target(self) -> None:
        self.mock_state.session_fixation_vulnerable = True
        plan = delegate(engagement_registry=self.registry)
        tasks_before = len(self.board.tasks())
        results = execute_plan(plan, executor=self.executor, board=self.board, engagement_registry=self.registry)
        self.assertEqual(set(results), {"acme-web"})
        self.assertEqual(results["acme-web"][0].verdict, "vulnerable")
        self.assertEqual(len(self.board.tasks()), tasks_before + 1)  # one task for the one assignment
        self.assertTrue(all(t["status"] == "completed" for t in self.board.tasks()[tasks_before:]))

    def test_execute_plan_never_acts_on_deferred_assignments(self) -> None:
        # Force a second candidate so something is deferred, to prove it is never run.
        other_state = MockSiteState()
        other_state.add_account("carol@example.com", "pw")
        with MockSiteServer(other_state) as other_site:
            other_profile = SiteProfile(
                login_path="/login", session_cookie_name="acme_session", logout_path="/logout",
                identities={"carol": {"email": "carol@example.com", "password": "pw"}},
            )
            other_engagement = self.registry.register("acme-web-2", other_site.origin, self.scope,
                                                        profile=other_profile)
            other_state.set_authorization_token("acme-web-2", other_engagement.verification_token)
            self.registry.verify("acme-web-2")
            plan = delegate(engagement_registry=self.registry, max_agents=1)
            self.assertEqual(len(plan.deferred), 1)
            results = execute_plan(plan, executor=self.executor, board=self.board, engagement_registry=self.registry)
            self.assertEqual(len(results), 1)  # only the one assignment, never the deferred one

    def test_execute_plan_requires_engagement_registry_for_a_web_pentest_assignment(self) -> None:
        plan = delegate(engagement_registry=self.registry)
        with self.assertRaises(ValueError):
            execute_plan(plan, executor=self.executor, board=self.board, engagement_registry=None)


if __name__ == "__main__":
    unittest.main()
