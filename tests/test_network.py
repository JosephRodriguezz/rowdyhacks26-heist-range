"""Network-level reconnaissance: NetworkScope/NetworkTarget/NetworkTargetRegistry and
the stdlib TCP connect-scanner, proven against real sockets (mocknetwork.py) and the
real mock site's HTTP ownership-verification endpoint (mocksite.py) -- never against
Diego's bank, and never against any third-party host.
"""

from __future__ import annotations

import socket
import time
import unittest
from unittest.mock import patch

from red.prototype.mocknetwork import MockNetworkHost
from red.prototype.mocksite import MockSiteServer, MockSiteState
from red.prototype.network import (
    NetworkScanError,
    NetworkScanExecutor,
    NetworkScope,
    NetworkTarget,
    NetworkTargetRegistry,
    _tcp_connect_scan,
)


class NetworkScopeValidationTests(unittest.TestCase):
    def test_port_range_must_be_valid_and_ordered(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkScope(min_port=0, max_port=10)
        with self.assertRaises(NetworkScanError):
            NetworkScope(min_port=100, max_port=50)
        with self.assertRaises(NetworkScanError):
            NetworkScope(min_port=1, max_port=70_000)

    def test_port_range_has_a_hard_upper_width_limit(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkScope(min_port=1, max_port=65_535)  # width 65535, far past the 2000 ceiling

    def test_port_range_at_the_width_ceiling_is_accepted(self) -> None:
        NetworkScope(min_port=1, max_port=2_000)  # width exactly 2000

    def test_only_tcp_is_a_supported_protocol(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkScope(allowed_protocols=frozenset({"udp"}))
        with self.assertRaises(NetworkScanError):
            NetworkScope(allowed_protocols=frozenset())

    def test_rate_and_concurrency_ceilings_must_be_positive(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkScope(max_ports_per_window=0)
        with self.assertRaises(NetworkScanError):
            NetworkScope(max_concurrency=0)
        with self.assertRaises(NetworkScanError):
            NetworkScope(window_seconds=0)

    def test_rate_and_concurrency_ceilings_have_a_hard_upper_limit(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkScope(max_ports_per_window=10_000)
        with self.assertRaises(NetworkScanError):
            NetworkScope(max_concurrency=1_000)
        with self.assertRaises(NetworkScanError):
            NetworkScope(window_seconds=10_000)

    def test_scan_timeout_must_be_positive_and_bounded(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkScope(scan_timeout_seconds=0)
        with self.assertRaises(NetworkScanError):
            NetworkScope(scan_timeout_seconds=10)

    def test_port_in_scope_respects_the_declared_range(self) -> None:
        scope = NetworkScope(min_port=100, max_port=200)
        self.assertTrue(scope.port_in_scope(100))
        self.assertTrue(scope.port_in_scope(200))
        self.assertFalse(scope.port_in_scope(99))
        self.assertFalse(scope.port_in_scope(201))


class NetworkTargetValidationTests(unittest.TestCase):
    def _scope(self) -> NetworkScope:
        return NetworkScope(min_port=1, max_port=100)

    def test_requires_a_target_id(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkTarget(target_id="", host="127.0.0.1", scope=self._scope())

    def test_requires_a_host(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkTarget(target_id="t1", host="", scope=self._scope())

    def test_verification_port_must_be_valid(self) -> None:
        with self.assertRaises(NetworkScanError):
            NetworkTarget(target_id="t1", host="127.0.0.1", scope=self._scope(), verification_port=0)
        with self.assertRaises(NetworkScanError):
            NetworkTarget(target_id="t1", host="127.0.0.1", scope=self._scope(), verification_port=70_000)

    def test_valid_target_starts_pending_with_a_fresh_token(self) -> None:
        target = NetworkTarget(target_id="t1", host="127.0.0.1", scope=self._scope())
        self.assertEqual(target.status, "pending_verification")
        self.assertIsNone(target.verified_at)
        self.assertTrue(target.verification_token)


class TcpConnectScanTests(unittest.TestCase):
    """Against real sockets (mocknetwork.py), not a simulation -- except 'filtered',
    which needs a real firewall-drop condition this prototype can't construct
    reliably in a test, so that one case is proven as a classification rule instead."""

    def setUp(self) -> None:
        self.host = MockNetworkHost()
        self.host.__enter__()

    def tearDown(self) -> None:
        self.host.close()

    def test_an_actually_open_port_is_detected_as_open(self) -> None:
        port = self.host.open_port()
        result = _tcp_connect_scan("127.0.0.1", port, timeout=1.0)
        self.assertEqual(result.state, "open")

    def test_an_actually_closed_port_is_detected_as_closed(self) -> None:
        port = self.host.reserve_closed_port()
        result = _tcp_connect_scan("127.0.0.1", port, timeout=1.0)
        self.assertEqual(result.state, "closed")

    def test_a_banner_sent_by_the_target_is_captured(self) -> None:
        port = self.host.open_port(banner="SSH-2.0-MockService\r\n")
        result = _tcp_connect_scan("127.0.0.1", port, timeout=1.0)
        self.assertEqual(result.state, "open")
        self.assertIn("SSH-2.0-MockService", result.banner)

    def test_an_open_port_with_no_banner_reports_none(self) -> None:
        port = self.host.open_port()  # no banner configured
        result = _tcp_connect_scan("127.0.0.1", port, timeout=1.0)
        self.assertEqual(result.state, "open")
        self.assertIsNone(result.banner)

    def test_a_connection_timeout_is_classified_as_filtered(self) -> None:
        # A real firewall-drop condition isn't constructible reliably in a test;
        # proven as a classification rule instead, by making connect_ex itself
        # raise the exact exception a genuine timeout would raise.
        with patch("socket.socket.connect_ex", side_effect=socket.timeout):
            result = _tcp_connect_scan("127.0.0.1", 1, timeout=0.1)
        self.assertEqual(result.state, "filtered")


class NetworkTargetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.site_state = MockSiteState()
        self.verify_site = MockSiteServer(self.site_state).start()
        self.net_host = MockNetworkHost()
        self.net_host.__enter__()
        self.verify_host, self.verify_port = self.verify_site.httpd.server_address[:2]
        self.registry = NetworkTargetRegistry()
        self.scope = NetworkScope(min_port=28_760, max_port=28_770, max_concurrency=4)

    def tearDown(self) -> None:
        self.verify_site.close()
        self.net_host.close()

    def _register(self, target_id: str = "acme-network") -> NetworkTarget:
        return self.registry.register(target_id, self.verify_host, self.scope, verification_port=self.verify_port)

    def test_unregistered_target_cannot_be_resolved(self) -> None:
        with self.assertRaises(NetworkScanError):
            self.registry.resolve("no-such-target")

    def test_registered_but_unverified_target_cannot_be_resolved(self) -> None:
        self._register()
        with self.assertRaises(NetworkScanError):
            self.registry.resolve("acme-network")

    def test_cannot_register_the_same_target_id_twice(self) -> None:
        self._register()
        with self.assertRaises(NetworkScanError):
            self._register()

    def test_full_registration_and_verification_flow_resolves_once_proven(self) -> None:
        target = self._register()
        self.site_state.set_authorization_token("acme-network", target.verification_token)
        verified = self.registry.verify("acme-network")
        self.assertEqual(verified.status, "verified")
        self.assertIsNotNone(verified.verified_at)
        self.assertEqual(self.registry.resolve("acme-network").host, self.verify_host)

    def test_verification_is_rechecked_not_permanent(self) -> None:
        target = self._register()
        self.site_state.set_authorization_token("acme-network", target.verification_token)
        self.registry.verify("acme-network")
        self.assertEqual(self.registry.resolve("acme-network").status, "verified")
        self.site_state.clear_authorization_token("acme-network")
        self.registry.verify("acme-network")
        with self.assertRaises(NetworkScanError):
            self.registry.resolve("acme-network")

    def test_revoked_target_can_never_be_resolved_or_reverified(self) -> None:
        target = self._register()
        self.site_state.set_authorization_token("acme-network", target.verification_token)
        self.registry.verify("acme-network")
        self.registry.revoke("acme-network")
        with self.assertRaises(NetworkScanError):
            self.registry.resolve("acme-network")
        with self.assertRaises(NetworkScanError):
            self.registry.verify("acme-network")


class NetworkScanExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.site_state = MockSiteState()
        self.verify_site = MockSiteServer(self.site_state).start()
        self.net_host = MockNetworkHost()
        self.net_host.__enter__()
        verify_host, verify_port = self.verify_site.httpd.server_address[:2]
        self.open_port = self.net_host.open_port(port=28_765, banner="SMTP-ready\r\n")
        self.closed_port = self.net_host.reserve_closed_port(port=28_766)
        self.registry = NetworkTargetRegistry()
        # scan_timeout_seconds is short on purpose: on this platform, connecting to a
        # recently-released closed port takes the *full* timeout before returning
        # ECONNREFUSED (observed directly, not assumed), not the near-instant RST
        # some platforms give -- a short timeout keeps 4 real scans well inside the
        # window instead of racing a 0.5s-per-call default against it.
        self.scope = NetworkScope(min_port=28_760, max_port=28_770, scan_timeout_seconds=0.1,
                                   max_ports_per_window=3, window_seconds=1.0, max_concurrency=1)
        self.target = self.registry.register("acme-network", verify_host, self.scope, verification_port=verify_port)
        self.site_state.set_authorization_token("acme-network", self.target.verification_token)
        self.registry.verify("acme-network")
        self.executor = NetworkScanExecutor(registry=self.registry)

    def tearDown(self) -> None:
        self.verify_site.close()
        self.net_host.close()

    def test_scan_port_reaches_the_real_host_through_the_verified_target(self) -> None:
        result = self.executor.scan_port("acme-network", self.open_port)
        self.assertEqual(result.state, "open")
        self.assertIn("SMTP-ready", result.banner)

    def test_scan_port_detects_a_real_closed_port(self) -> None:
        result = self.executor.scan_port("acme-network", self.closed_port)
        self.assertEqual(result.state, "closed")

    def test_port_outside_the_declared_range_is_rejected(self) -> None:
        with self.assertRaises(NetworkScanError):
            self.executor.scan_port("acme-network", 1)

    def test_unverified_target_is_rejected_at_scan_time_not_only_at_resolve(self) -> None:
        self.registry.revoke("acme-network")
        with self.assertRaises(NetworkScanError):
            self.executor.scan_port("acme-network", self.open_port)

    def test_scan_ports_returns_one_result_per_port_in_order(self) -> None:
        results = self.executor.scan_ports("acme-network", [self.open_port, self.closed_port])
        self.assertEqual([r.port for r in results], [self.open_port, self.closed_port])
        self.assertEqual([r.state for r in results], ["open", "closed"])

    def test_exceeding_the_window_ceiling_sheds_the_scan(self) -> None:
        self.executor.scan_port("acme-network", self.open_port)
        self.executor.scan_port("acme-network", self.closed_port)
        self.executor.scan_port("acme-network", self.open_port)
        shed = self.executor.scan_port("acme-network", self.closed_port)
        self.assertEqual(shed.state, "shed")
        self.assertIsNotNone(shed.detail)

    def test_admission_recovers_once_the_window_elapses(self) -> None:
        self.executor.scan_port("acme-network", self.open_port)
        self.executor.scan_port("acme-network", self.closed_port)
        self.executor.scan_port("acme-network", self.open_port)
        shed = self.executor.scan_port("acme-network", self.closed_port)
        self.assertEqual(shed.state, "shed")
        time.sleep(self.scope.window_seconds + 0.15)
        recovered = self.executor.scan_port("acme-network", self.open_port)
        self.assertEqual(recovered.state, "open")

    def test_concurrency_ceiling_is_enforced(self) -> None:
        # White-box: proves the counter logic precisely and deterministically,
        # without depending on real thread scheduling for true concurrent scans.
        first = self.executor._admit("acme-network", self.scope)
        self.assertIsNone(first)
        second = self.executor._admit("acme-network", self.scope)
        self.assertIsNotNone(second)
        self.assertIn("concurrency", second)
        self.executor._release("acme-network")
        third = self.executor._admit("acme-network", self.scope)
        self.assertIsNone(third)
        self.executor._release("acme-network")

    def test_two_targets_have_independent_rate_counters(self) -> None:
        other_site_state = MockSiteState()
        with MockSiteServer(other_site_state) as other_verify_site:
            other_host, other_port = other_verify_site.httpd.server_address[:2]
            other_target = self.registry.register("other-network", other_host, self.scope,
                                                    verification_port=other_port)
            other_site_state.set_authorization_token("other-network", other_target.verification_token)
            self.registry.verify("other-network")
            self.executor.scan_port("acme-network", self.open_port)
            self.executor.scan_port("acme-network", self.closed_port)
            self.executor.scan_port("acme-network", self.open_port)
            shed = self.executor.scan_port("acme-network", self.closed_port)
            self.assertEqual(shed.state, "shed")
            # The other target's own window is untouched by the first's exhaustion.
            fresh = self.executor.scan_port("other-network", self.open_port)
            self.assertEqual(fresh.state, "open")

    def test_scan_events_are_recorded_on_a_board_when_one_is_supplied(self) -> None:
        from red.prototype.board import RedBoard
        board = RedBoard()
        executor = NetworkScanExecutor(registry=self.registry, board=board)
        executor.scan_port("acme-network", self.open_port)
        events = [e for e in board.events() if e["event_type"] == "network.port_scanned"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["port"], self.open_port)
        self.assertEqual(events[0]["state"], "open")


if __name__ == "__main__":
    unittest.main()
