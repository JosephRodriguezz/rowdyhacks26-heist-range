# Learning and reference material

Use these sources to build the scenario, study the weakness families, and design defensive verification. They are educational and design references; they do not authorize testing systems outside our registered lab. The contest target will be our purpose-built bank lab, not a public training application.

## Core application security references

- [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/) — testing methodology for web applications and web services. When an evaluation case cites a specific test, record its version and test identifier so the reference remains reproducible.
- [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/) — requirements that help define secure controls and verification checks. Pin the ASVS version used by each evaluation case.
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) — concise implementation and defensive guidance. Start with the sheets below for the first target families.

## Initial vulnerability-family lessons

- [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) — authorization is distinct from authentication; use it to design both a controlled access-control flaw and a regression check for legitimate permissions.
- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) — authentication design and monitoring lessons for the lab’s account flows.
- [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — session lifecycle and protections for the authentication/session scenario.
- [Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) — input handling and validation guidance for a controlled lab scenario.
- [Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — event collection and redaction principles for Blue telemetry and evaluation records.

## Training application reference

- [OWASP WebGoat](https://github.com/WebGoat/WebGoat) — a deliberately vulnerable educational application with lessons. Use it to study lesson structure and vulnerability concepts only; it is not the target for this project. If anyone runs it locally for learning, follow its official isolation guidance and never expose it to an untrusted network.

## How we use references

- Map each target weakness to a specific lesson or test reference, a safe synthetic behavior, detection evidence, a corrective change, and a regression check.
- Keep Red’s learning material separate from the scenario answer key. References teach classes of problems; they should not disclose the current hidden lab path.
- Do not treat a reference as proof that our lab behaves the same way. Validate every scenario and repair in our own resettable target.
- Record title, URL, version/date accessed, relevant section/test ID, and the evaluation case that uses it.
