# Input handling and query behavior

Observe how accepted input changes the returned result, and compare it with ordinary expected behavior. A generic validation error, unusual response code, or reflected string is not by itself proof of an injection flaw. Use only the bounded fields and local routes exposed by the action interface; do not run scanners, shell commands, or requests outside the registered lab.

For a finding, preserve the input category, response, and independently verified protected data effect. For a repair, use parameterized data access and server-side input constraints, then retest both an ordinary query and the rejected or non-authorized case. See the [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) and the [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/).
