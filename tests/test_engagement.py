"""Engagement/authorization model, proven against a real, non-bank-shaped mock site --
not against Diego's bank, and not against any third-party site. See
red/prototype/engagement.py and red/prototype/mocksite.py for why.
"""

from __future__ import annotations

import http.client
import json
import unittest

from red.prototype.engagement import (
    EngagementError,
    EngagementRegistry,
    EngagementScope,
    TargetEngagement,
    verify_ownership,
)
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


if __name__ == "__main__":
    unittest.main()
