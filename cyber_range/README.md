# Storefront lab

`cyber_range.storefront` is the first live, resettable **local lab target**. It
uses only Python's standard library. Its seed data has Alice's private order
101 and Bob's private order 204. `GET /api/orders/{id}` has an intentional
ownership flaw; `GET /api/secure-orders/{id}` is the protected control. This
is lab behavior, not a verified finding by itself.

## HTTP contract

| Route | Response |
| --- | --- |
| `GET /health` | `{"status":"ok"}` |
| `GET /` | Public JSON link to `/api/orders` |
| `POST /api/session` | Login with runtime `username` and `password`; response contains a raw token and session reference for **core only** |
| `GET /api/orders` | Authenticated user's own records, each with `href` and `secure_href` |
| `GET /api/orders/{id}` | Private order detail; intentionally missing owner check |
| `GET /api/secure-orders/{id}` | Private detail only for the owner |

Pass the token as `Authorization: Bearer <token>` on authenticated requests.
The core HTTP tool must resolve its `credential_ref` internally and sanitize
session responses before any red observation, event, or UI payload. Never put
the login response, token, or seed password in a prompt or log. The server
does not expose telemetry, reset, or revocation over HTTP.

## Startup and trusted integration

Start the target within the trusted backend process for this first slice:

```python
from threading import Thread
from cyber_range.storefront import LabState, create_server

lab = LabState()  # random runtime login secrets; none committed
server = create_server("127.0.0.1", 0, lab)
Thread(target=server.serve_forever, daemon=True).start()
origin = f"http://127.0.0.1:{server.server_address[1]}"
# Register origin under target_id="storefront-lab", version="lab-v1".
# Shut down with server.shutdown() and server.server_close().
```

The target registry and HTTP executor are core-owned. They must allow only
this registered origin and relative paths, block external redirects, and keep
model-provider egress separate. The current target binds to loopback but does
not provide a separate network namespace or container; add that isolation
when the core runtime is packaged. The in-process controller is a temporary
trusted integration seam and must never be injected into a red/blue agent
context.

Core can use `lab.trusted_new_session("alice")` to issue a session. Its
`SessionGrant` has `session_ref`, `account_ref`, and a secret `token`. Store the
token in core's credential vault, expose only the reference to red, and
resolve it only inside the HTTP executor. To exercise the HTTP login route,
core may obtain `lab.trusted_seed_credential("alice")` and submit its username
and password internally. Both accounts work the same way. Credentials default
to random values each reset; `LabState(credentials={"alice": ..., "bob": ...})`
allows trusted runtime injection from environment or a secret manager.

`lab.trusted_revoke_session(session_ref)` revokes one token. A later call to
`trusted_new_session(account_ref)` issues a fresh one; the flaw remains.
`lab.trusted_reset()` revokes all tokens, clears telemetry, restores the seed
scenario, and returns `{"target_id":"storefront-lab","target_version":"lab-v1"}`.
The target version is the base-version pin for disposable patch copies; reset
generation is deliberately separate from the version. A patched disposable
process can set `LabState(target_version="<new-registered-version>")`; core
must pin that version to the reviewed artifact and register it separately.

`lab.trusted_telemetry()` returns sanitized records for blue/core. Each has
`request_id`, UTC `timestamp`, `target_id`, `target_version`, `actor_ref`,
`session_ref`, `resource_id`, `resource_owner_ref`, `action`, and `http_status`.
Private detail reads use `action="read_private_order"`, matching blue's
`private-orders-owner-only` policy; protected reads use `read_secure_order`.
Non-resource actions use `resource_id="-"`.
The caller supplies `X-Request-ID` for correlation. No raw token, password,
request body, or authentication header is stored. Do not pass ownership
telemetry into red's observations.

## Defense patch surface and tests

Patch only `cyber_range/storefront/policy.py` in a **disposable copy** pinned
to `lab-v1`. Changing `may_read_detail` to compare actor and owner should
deny cross-user detail while keeping owner access. The protected control's
`may_read_secure_detail` is a regression reference. Restart the disposable
target to load a patched module; do not mutate a running target or equate a
patch application with a verified fix. The referee must retest unauthorized
and authorized access independently.

From the repository root:

```sh
python -m unittest discover -s cyber_range/tests -v
```

The tests cover the seeded flaw, both owners' access, anonymous denial,
protected control, reset, revocation, fresh-session adaptation, telemetry,
and HTTP login secrecy.
