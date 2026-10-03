# Workflow and approval bypass

An application may describe an approval sequence while allowing a later operation before its prerequisites are satisfied. Learn the intended steps and ordinary successful behavior from responses. Compare a valid workflow with one deliberately omitted transition, using only the current requester's references. Check the server's state and resulting protected operation; a successful request submission alone proves no bypass.

A repair enforces transitions and approvals on the server, binds each operation to its requester, and rejects completed-step replay while preserving authorized workflows. See the [OWASP Business Logic Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Business_Logic_Security_Cheat_Sheet.html).
