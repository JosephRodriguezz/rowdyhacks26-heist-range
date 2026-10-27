# Red team module

This module implements the first bounded, candidate-only red pass described in
the [shared contract](../../../../shared/contracts/README.md). It performs route
discovery from a public entry point, lists records through permitted account
references, and compares an owner baseline with a cross-user detail response.

The public entry point and HTTP executor are supplied by the caller. The runner
never chooses a host, constructs credentials, reads source or telemetry, or
writes persistence. It returns a candidate with a replay recipe and evidence
references; only the independent referee may assign `verified`, `rejected`, or
`inconclusive`.

## Interface

```python
await execute(context, tools, decision_provider=None, decision_policy=None)
```

`context` contains target/version IDs, an entry path, account references,
`policy_id`, `data_source`, and bounded budgets (`max_steps`, `max_requests`,
`timeout_seconds`). After containment, core may add `fresh_account_refs` for
the same logical accounts. `tools.http_request(request)` is the core-owned adapter.
The request contains only a registered target ID, relative path, credential
reference, and correlation ID. An optional decision provider selects from
observed test options; the default is deterministic. `decision_policy` is an
alias retained for the provider-neutral handoff.

The result identifies `decision_source`, request/step counts, discovered
endpoints, evidence references, and `candidates`. Candidate status is always
`candidate`; this module never emits a verifier verdict. When fresh references
are supplied, `adaptation` records the bounded post-revocation observation as
`still_exposed`, `blocked`, or `inconclusive`; it does not call that observation
a fix or a verification result.

## Verification

From the repository root:

```sh
python3 -m unittest discover -s backend/tests/red -p "test_*.py" -v
python3 -m unittest discover -s cyber_range/tests -p "test_*.py" -v
```

The red tests use synthetic adapters and one loopback integration adapter for
the local storefront. They cover budget enforcement, privileged-context
rejection, protected-control false positives, candidate shape, and discovery
against the resettable lab. The lab tests separately cover reset, revocation,
fresh sessions, access policy, and telemetry sanitization.

Full assignment: [Member 3](../../../../docs/team/03-red-team-lab.md).
