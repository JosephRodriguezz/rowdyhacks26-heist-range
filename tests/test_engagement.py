"""Engagement/authorization model, proven against a real, non-bank-shaped mock site --
not against Diego's bank, and not against any third-party site. See
red/prototype/engagement.py and red/prototype/mocksite.py for why.
"""

from __future__ import annotations

import http.client
import json
import time
import unittest
from unittest.mock import MagicMock, patch

from red.prototype.actions import TARGET_ID, ActionExecutor, ActionRejected, FixedTargetRegistry
from red.prototype.board import BudgetLedger, RedBoard
from red.prototype.domain import ActionProposal, RunLimits
from red.prototype.engagement import (
    EngagementError,
    EngagementRegistry,
    EngagementScope,
    TargetEngagement,
    verify_ownership,
)
from red.prototype.lab import LabState
from red.prototype.mocksite import MockSiteServer, MockSiteState


class EngagementScopeTests(unittest.TestCase):
    def test_requires_at_least_one_allowed_capability(self) -> None:
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset())

    def test_ceilings_must_be_positive(self) -> None:
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset({"request_api"}), max_requests_per_window=0)
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset({"request_api"}), max_concurrency=0)
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset({"request_api"}), window_seconds=0)

    def test_ceilings_have_a_hard_upper_limit(self) -> None:
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset({"request_api"}), max_requests_per_window=10_000)
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset({"request_api"}), max_concurrency=1_000)
        with self.assertRaises(EngagementError):
            EngagementScope(allowed_capabilities=frozenset({"request_api"}), window_seconds=10_000)

    def test_path_exclusion_matches_prefix_not_substring(self) -> None:
        scope = EngagementScope(allowed_capabilities=frozenset({"request_api"}), excluded_paths=("/admin",))
        self.assertTrue(scope.path_excluded("/admin"))
        self.assertTrue(scope.path_excluded("/admin/users"))
        self.assertFalse(scope.path_excluded("/administrator"))  # prefix-of-segment, not substring
        self.assertFalse(scope.path_excluded("/public"))

    def test_path_exclusion_ignores_the_query_string(self) -> None:
        scope = EngagementScope(allowed_capabilities=frozenset({"request_api"}), excluded_paths=("/admin",))
        self.assertTrue(scope.path_excluded("/admin?x=1"))


class TargetEngagementValidationTests(unittest.TestCase):
    def _scope(self) -> EngagementScope:
        return EngagementScope(allowed_capabilities=frozenset({"request_api"}))

    def test_requires_a_target_id(self) -> None:
        with self.assertRaises(EngagementError):
            TargetEngagement(target_id="", origin="http://127.0.0.1:8080", scope=self._scope())

    def test_origin_must_be_bare_http_or_https(self) -> None:
        for bad_origin in ("ftp://127.0.0.1:80", "http://127.0.0.1:80/path", "http://127.0.0.1:80?q=1",
                           "http://127.0.0.1", "not-a-url"):
            with self.subTest(origin=bad_origin), self.assertRaises(EngagementError):
                TargetEngagement(target_id="t1", origin=bad_origin, scope=self._scope())

    def test_valid_engagement_starts_pending_with_a_fresh_token(self) -> None:
        engagement = TargetEngagement(target_id="t1", origin="http://127.0.0.1:8080", scope=self._scope())
        self.assertEqual(engagement.status, "pending_verification")
        self.assertIsNone(engagement.verified_at)
        self.assertTrue(engagement.verification_token)


class OwnershipVerificationTests(unittest.TestCase):
    """Against a real mock site over real HTTP -- never a stubbed/faked fetch."""

    def setUp(self) -> None:
        self.state = MockSiteState()
        self.server = MockSiteServer(self.state).start()

    def tearDown(self) -> None:
        self.server.close()

    def test_matching_token_at_the_well_known_path_verifies(self) -> None:
        self.state.set_authorization_token("acme-test-site", "secret-token-123")
        self.assertTrue(verify_ownership(self.server.origin, "acme-test-site", "secret-token-123"))

    def test_missing_token_does_not_verify(self) -> None:
        self.assertFalse(verify_ownership(self.server.origin, "acme-test-site", "secret-token-123"))

    def test_wrong_token_does_not_verify(self) -> None:
        self.state.set_authorization_token("acme-test-site", "a-different-token")
        self.assertFalse(verify_ownership(self.server.origin, "acme-test-site", "secret-token-123"))

    def test_a_token_registered_for_a_different_target_id_does_not_verify_this_one(self) -> None:
        self.state.set_authorization_token("someone-elses-target", "secret-token-123")
        self.assertFalse(verify_ownership(self.server.origin, "acme-test-site", "secret-token-123"))

    def test_unreachable_origin_fails_closed_rather_than_raising(self) -> None:
        self.assertFalse(verify_ownership("http://127.0.0.1:1", "acme-test-site", "secret-token-123", timeout=0.3))

    def test_malformed_origin_is_rejected_before_any_network_call(self) -> None:
        with self.assertRaises(EngagementError):
            verify_ownership("http://127.0.0.1:80/extra-path", "acme-test-site", "tok")


class EngagementRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MockSiteState()
        self.server = MockSiteServer(self.state).start()
        self.registry = EngagementRegistry()
        self.scope = EngagementScope(allowed_capabilities=frozenset({"request_api", "read_page"}),
                                      excluded_paths=("/admin",))

    def tearDown(self) -> None:
        self.server.close()

    def test_unregistered_target_cannot_be_resolved(self) -> None:
        with self.assertRaises(EngagementError):
            self.registry.resolve("no-such-target")

    def test_registered_but_unverified_target_cannot_be_resolved(self) -> None:
        self.registry.register("site-a", self.server.origin, self.scope)
        with self.assertRaises(EngagementError):
            self.registry.resolve("site-a")

    def test_cannot_register_the_same_target_id_twice(self) -> None:
        self.registry.register("site-a", self.server.origin, self.scope)
        with self.assertRaises(EngagementError):
            self.registry.register("site-a", self.server.origin, self.scope)

    def test_full_registration_and_verification_flow_resolves_once_proven(self) -> None:
        engagement = self.registry.register("site-a", self.server.origin, self.scope)
        # Before the site operator has placed the token, verification fails closed.
        self.assertEqual(self.registry.verify("site-a").status, "pending_verification")
        with self.assertRaises(EngagementError):
            self.registry.resolve("site-a")
        # The site "places" its token (standing in for a real operator doing this).
        self.state.set_authorization_token("site-a", engagement.verification_token)
        verified = self.registry.verify("site-a")
        self.assertEqual(verified.status, "verified")
        self.assertIsNotNone(verified.verified_at)
        resolved = self.registry.resolve("site-a")
        self.assertEqual(resolved.origin, self.server.origin)

    def test_verification_is_rechecked_not_permanent(self) -> None:
        engagement = self.registry.register("site-a", self.server.origin, self.scope)
        self.state.set_authorization_token("site-a", engagement.verification_token)
        self.registry.verify("site-a")
        self.assertEqual(self.registry.resolve("site-a").status, "verified")
        # The site operator removes the file (revokes control, or it was never real).
        self.state.clear_authorization_token("site-a")
        self.registry.verify("site-a")
        with self.assertRaises(EngagementError):
            self.registry.resolve("site-a")

    def test_revoked_target_can_never_be_resolved_or_reverified(self) -> None:
        engagement = self.registry.register("site-a", self.server.origin, self.scope)
        self.state.set_authorization_token("site-a", engagement.verification_token)
        self.registry.verify("site-a")
        self.registry.revoke("site-a")
        with self.assertRaises(EngagementError):
            self.registry.resolve("site-a")
        with self.assertRaises(EngagementError):
            self.registry.verify("site-a")

    def test_capability_allowed_respects_the_scope_allowlist_and_exclusions(self) -> None:
        engagement = self.registry.register("site-a", self.server.origin, self.scope)
        self.state.set_authorization_token("site-a", engagement.verification_token)
        self.registry.verify("site-a")
        self.assertTrue(self.registry.capability_allowed("site-a", "request_api", "/about"))
        self.assertFalse(self.registry.capability_allowed("site-a", "request_api", "/admin"))
        self.assertFalse(self.registry.capability_allowed("site-a", "start_account_session", "/"))

    def test_capability_check_on_an_unverified_target_is_rejected_not_silently_false(self) -> None:
        self.registry.register("site-a", self.server.origin, self.scope)
        with self.assertRaises(EngagementError):
            self.registry.capability_allowed("site-a", "request_api", "/about")

    def test_two_independently_registered_sites_do_not_cross_contaminate(self) -> None:
        other_state = MockSiteState(site_name="Other Test Co.")
        with MockSiteServer(other_state) as other_server:
            engagement_a = self.registry.register("site-a", self.server.origin, self.scope)
            engagement_b = self.registry.register("site-b", other_server.origin, self.scope)
            self.state.set_authorization_token("site-a", engagement_a.verification_token)
            other_state.set_authorization_token("site-b", engagement_b.verification_token)
            self.registry.verify("site-a")
            self.registry.verify("site-b")
            self.assertEqual(self.registry.resolve("site-a").origin, self.server.origin)
            self.assertEqual(self.registry.resolve("site-b").origin, other_server.origin)
            # site-a's token would not have verified site-b, and vice versa.
            self.assertNotEqual(engagement_a.verification_token, engagement_b.verification_token)


class MockSiteShapeTests(unittest.TestCase):
    """The mock site is deliberately not bank-shaped -- proving the engagement model
    against something other than lab.py's synthetic bank API."""

    def test_mock_site_exposes_a_different_shape_than_the_bank(self) -> None:
        state = MockSiteState(site_name="Acme Test Co.")
        with MockSiteServer(state) as server:
            conn = http.client.HTTPConnection(*server.httpd.server_address[:2], timeout=2.0)
            try:
                conn.request("GET", "/about")
                response = conn.getresponse()
                body = json.loads(response.read())
            finally:
                conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("generic test site, not a bank", body["about"])


class ActionExecutorEngagementDispatchTests(unittest.TestCase):
    """ActionExecutor actually dispatching to a verified engagement -- not just the
    registry in isolation. Proves the wiring, not only the model."""

    def setUp(self) -> None:
        self.mock_state = MockSiteState(site_name="Acme Test Co.")
        self.mocksite = MockSiteServer(self.mock_state).start()
        self.engagement_registry = EngagementRegistry()
        self.scope = EngagementScope(allowed_capabilities=frozenset({"request_api", "read_page"}),
                                      excluded_paths=("/admin",))
        self.engagement = self.engagement_registry.register("acme-test-site", self.mocksite.origin, self.scope)
        self.mock_state.set_authorization_token("acme-test-site", self.engagement.verification_token)
        self.engagement_registry.verify("acme-test-site")
        self.state = LabState("clean")
        self.board = RedBoard()
        self.limits = RunLimits()
        self.budget = BudgetLedger(self.limits)
        self.executor = ActionExecutor(
            # Bank-local is never touched by these tests; a placeholder origin on an
            # unused port proves that -- nothing here ever dispatches to it.
            registry=FixedTargetRegistry("http://127.0.0.1:1"),
            state=self.state, limits=self.limits, budget=self.budget, board=self.board,
            engagement_registry=self.engagement_registry,
        )
        self.task = self.board.add_task("scout", "engagement dispatch test")
        self.board.claim_task(self.task.task_id, "scout-test")

    def tearDown(self) -> None:
        self.executor.close()
        self.mocksite.close()
        self.state.close()

    def act(self, capability: str, **kwargs):
        return self.executor.execute(
            ActionProposal(capability, target_id="acme-test-site",
                            path=kwargs.get("path", "/"), method=kwargs.get("method", "GET")),
            role="scout", task_id=self.task.task_id,
        )

    def test_request_api_reaches_the_real_mock_site_through_the_verified_engagement(self) -> None:
        result = self.act("request_api", path="/about")
        self.assertEqual(result.evidence.status, 200)
        self.assertIn("generic test site, not a bank", result.evidence.body)
        self.assertIn("/about", self.mock_state.requests_seen)

    def test_read_page_also_reaches_the_verified_engagement(self) -> None:
        result = self.act("read_page", path="/")
        self.assertEqual(result.evidence.status, 200)

    def test_excluded_path_is_rejected_even_though_the_capability_is_allowed(self) -> None:
        with self.assertRaises(ActionRejected):
            self.act("request_api", path="/admin")

    def test_capability_outside_the_engagement_allowlist_is_rejected(self) -> None:
        with self.assertRaises(ActionRejected):
            self.executor.execute(
                ActionProposal("start_account_session", target_id="acme-test-site", identity_ref="account_a"),
                role="scout", task_id=self.task.task_id,
            )

    def test_unverified_engagement_is_rejected_at_dispatch_not_only_at_the_registry(self) -> None:
        self.engagement_registry.revoke("acme-test-site")
        with self.assertRaises(ActionRejected):
            self.act("request_api", path="/about")

    def test_bank_local_requests_are_unaffected_by_an_engagement_registry_being_configured(self) -> None:
        # Bank-local's own path never consults the engagement registry at all: the
        # request validates fine (scope is None for bank-local, exactly as before an
        # engagement registry ever existed) and only fails at the transport layer,
        # because nothing real listens at the placeholder bank-local port used in
        # this test -- not because of anything related to the engagement registry.
        result = self.executor.execute(
            ActionProposal("request_api", target_id=TARGET_ID, path="/api/catalog"),
            role="scout", task_id=self.task.task_id,
        )
        self.assertEqual(result.evidence.failure_kind, "target_transport")

    def test_https_scheme_selects_an_https_connection_class_not_http(self) -> None:
        # Mocked at the http.client level, not inferred from connection-failure
        # behavior: both connection classes would equally fail to reach a real
        # mock site over the wrong scheme, so only directly observing which class
        # was constructed actually proves the selection logic, not just that *some*
        # connection was attempted.
        https_registry = EngagementRegistry()
        https_scope = EngagementScope(allowed_capabilities=frozenset({"request_api"}))
        https_registry.register("https-site", "https://127.0.0.1:1", https_scope)
        # Force-verified for this unit check: bypasses the real ownership fetch, since
        # the point here is connection-class selection, not verification again.
        engagement = https_registry._engagements["https-site"]  # test-only introspection
        engagement.status = "verified"
        executor = ActionExecutor(
            registry=FixedTargetRegistry("http://127.0.0.1:1"), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, engagement_registry=https_registry,
        )
        fake_response = MagicMock()
        fake_response.status = 200
        fake_response.read.return_value = b'{"ok": true}'
        fake_response.getheader.return_value = None
        try:
            with patch("http.client.HTTPSConnection") as mock_https_cls, \
                    patch("http.client.HTTPConnection") as mock_http_cls:
                mock_https_cls.return_value.getresponse.return_value = fake_response
                result = executor.execute(
                    ActionProposal("request_api", target_id="https-site", path="/"),
                    role="scout", task_id=self.task.task_id,
                )
            mock_https_cls.assert_called_once()
            mock_http_cls.assert_not_called()
            self.assertEqual(result.evidence.status, 200)
        finally:
            executor.close()


class EngagementRateLimitTests(unittest.TestCase):
    """EngagementScope's rate/concurrency ceilings, actually enforced at dispatch --
    not only declared. Independent per target_id; never touched for bank-local."""

    def setUp(self) -> None:
        self.mock_state = MockSiteState(site_name="Acme Test Co.")
        self.mocksite = MockSiteServer(self.mock_state).start()
        self.engagement_registry = EngagementRegistry()
        self.scope = EngagementScope(
            allowed_capabilities=frozenset({"request_api"}),
            max_requests_per_window=2, window_seconds=0.3, max_concurrency=1,
        )
        self.engagement = self.engagement_registry.register("acme-test-site", self.mocksite.origin, self.scope)
        self.mock_state.set_authorization_token("acme-test-site", self.engagement.verification_token)
        self.engagement_registry.verify("acme-test-site")
        self.state = LabState("clean")
        self.board = RedBoard()
        self.limits = RunLimits()
        self.budget = BudgetLedger(self.limits)
        self.executor = ActionExecutor(
            registry=FixedTargetRegistry("http://127.0.0.1:1"), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, engagement_registry=self.engagement_registry,
        )
        self.task = self.board.add_task("scout", "rate limit test")
        self.board.claim_task(self.task.task_id, "scout-test")

    def tearDown(self) -> None:
        self.executor.close()
        self.mocksite.close()
        self.state.close()

    def act(self, *, target_id: str = "acme-test-site", path: str = "/about"):
        return self.executor.execute(
            ActionProposal("request_api", target_id=target_id, path=path),
            role="scout", task_id=self.task.task_id,
        )

    def test_requests_within_the_window_ceiling_are_admitted(self) -> None:
        first = self.act(path="/about?x=1")
        second = self.act(path="/about?x=2")  # distinct path: dodges the dedup fingerprint, not the rate limit
        self.assertEqual(first.evidence.status, 200)
        self.assertEqual(second.evidence.status, 200)

    def test_exceeding_the_window_ceiling_sheds_the_request(self) -> None:
        self.act(path="/about?x=1")
        self.act(path="/about?x=2")
        third = self.act(path="/about?x=3")
        self.assertEqual(third.evidence.failure_kind, "engagement_rate_limited")
        self.assertFalse(third.dispatched)

    def test_admission_recovers_once_the_window_elapses(self) -> None:
        self.act(path="/about?x=1")
        self.act(path="/about?x=2")
        shed = self.act(path="/about?x=3")
        self.assertEqual(shed.evidence.failure_kind, "engagement_rate_limited")
        time.sleep(self.scope.window_seconds + 0.15)
        recovered = self.act(path="/about?x=4")
        self.assertEqual(recovered.evidence.status, 200)

    def test_two_engagements_have_independent_rate_counters(self) -> None:
        other_state = MockSiteState(site_name="Other Test Co.")
        with MockSiteServer(other_state) as other_site:
            other_engagement = self.engagement_registry.register("other-test-site", other_site.origin, self.scope)
            other_state.set_authorization_token("other-test-site", other_engagement.verification_token)
            self.engagement_registry.verify("other-test-site")
            self.act(path="/about?x=1")
            self.act(path="/about?x=2")
            shed = self.act(path="/about?x=3")
            self.assertEqual(shed.evidence.failure_kind, "engagement_rate_limited")
            # The second engagement's own window is untouched by the first's exhaustion.
            fresh = self.act(target_id="other-test-site", path="/about")
            self.assertEqual(fresh.evidence.status, 200)

    def test_concurrency_ceiling_is_enforced(self) -> None:
        # White-box: proves the counter logic precisely and deterministically, without
        # depending on real thread scheduling to land two requests truly concurrently.
        first = self.executor._admit_engagement_request("acme-test-site", self.scope)
        self.assertIsNone(first)  # admitted; concurrency now 1 == max_concurrency
        second = self.executor._admit_engagement_request("acme-test-site", self.scope)
        self.assertIsNotNone(second)
        self.assertIn("concurrency", second)
        self.executor._release_engagement_concurrency("acme-test-site")
        third = self.executor._admit_engagement_request("acme-test-site", self.scope)
        self.assertIsNone(third)
        self.executor._release_engagement_concurrency("acme-test-site")

    def test_concurrency_is_released_even_when_the_request_fails(self) -> None:
        # A transport failure (not a validation rejection) must still release its slot,
        # or one failed request would permanently occupy the concurrency ceiling.
        bad_registry = EngagementRegistry()
        bad_engagement = bad_registry.register("unreachable-site", "http://127.0.0.1:1", self.scope)
        bad_engagement.status = "verified"  # force-verified: this test is about release-on-failure, not verification
        executor = ActionExecutor(
            registry=FixedTargetRegistry("http://127.0.0.1:1"), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, engagement_registry=bad_registry,
        )
        try:
            result = executor.execute(
                ActionProposal("request_api", target_id="unreachable-site", path="/"),
                role="scout", task_id=self.task.task_id,
            )
            self.assertEqual(result.evidence.failure_kind, "target_transport")
            self.assertEqual(executor._engagement_concurrency.get("unreachable-site", 0), 0)
        finally:
            executor.close()

    def test_bank_local_is_never_subject_to_engagement_rate_limiting(self) -> None:
        # Bank-local resolves with scope=None, so _admit_engagement_request is never
        # even consulted for it -- proven here by exhausting acme-test-site's window
        # and confirming a bank-local attempt is unaffected (it only fails on the
        # unrelated placeholder-port transport, exactly as without any engagement
        # registry configured at all).
        self.act(path="/about?x=1")
        self.act(path="/about?x=2")
        shed = self.act(path="/about?x=3")
        self.assertEqual(shed.evidence.failure_kind, "engagement_rate_limited")
        bank_local_result = self.executor.execute(
            ActionProposal("request_api", target_id=TARGET_ID, path="/api/catalog"),
            role="scout", task_id=self.task.task_id,
        )
        self.assertEqual(bank_local_result.evidence.failure_kind, "target_transport")


if __name__ == "__main__":
    unittest.main()
