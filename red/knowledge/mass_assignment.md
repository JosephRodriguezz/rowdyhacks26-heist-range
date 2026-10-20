# Mass assignment and protected properties

An update endpoint may accidentally bind client-supplied properties to a server object, including fields the user should not control. Inspect observed profile properties and the documented ordinary update behavior. Compare a permitted edit with a single protected-property change, then check whether effective permissions changed. A reflected field alone is insufficient evidence; verify persistence and a protected operation.

A repair allowlists user-editable fields, keeps authority on the server, and revokes any illicit grants already made. Retest ordinary edits and unauthorized property changes. See the [OWASP Mass Assignment Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html).
