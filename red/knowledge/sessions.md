# Authentication and session lifecycle

Treat login, active use, logout, expiry, and subsequent requests as separate observations. A successful logout message is not proof that the server invalidated the session. Use only the opaque session reference issued by the tool boundary; never request or reproduce its cookie value.

When testing a session lifecycle hypothesis, record the pre-logout authorized request, the logout response, and a follow-up request through the same tool-owned session. Distinguish a denied follow-up from a transport failure. Do not infer privilege escalation from ordinary login alone.

For a fix, revoke server-side session state and verify that a subsequent protected request fails while a newly authenticated, authorized request still works. See the [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) and [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
