# Authorization and object access

Authentication establishes an identity. Authorization must be checked for each requested object and operation using the authenticated principal and the object's current policy. An identifier being visible or difficult to guess does not grant access.

For a bounded investigation, compare a normal owner's access with a second supplied ordinary identity using an object reference actually observed from the application. Record the identity reference, object reference, request, response status, and returned content evidence. Separate an attempted request from an unauthorized read verified by the response and evaluator. A `403`, a missing record, or a timeout alone does not establish that the control is effective.

For defense and regression, enforce ownership or an explicit permission at the server-side resource boundary, deny by default, and retest both the disallowed cross-owner request and the legitimate owner's request. This is consistent with the [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).
