"""Deterministic delegation rules (delegation.py), proven against real verified
engagements and real port-scan results -- never against invented/stubbed discovery
data, and never against Diego's bank or a third party.
"""

from __future__ import annotations

import unittest

from red.prototype.delegation import delegate, scan_and_delegate
from red.prototype.engagement import EngagementRegistry, EngagementScope
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


if __name__ == "__main__":
    unittest.main()
