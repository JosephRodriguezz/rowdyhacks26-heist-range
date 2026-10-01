# Defense artifacts

Owned by Member 4. Store scoped lab patch artifacts and their metadata here. Each patch needs an ID, allowed file list, expected base version, origin, explanation, and regression checks.

Member 2's executor controls application to disposable targets; Member 3 owns the source lab. Do not directly patch another member's checkout during development. See [Member 4's assignment](../docs/team/04-blue-team-defense.md).

## Patch layout

Each patch has its own folder, named by its ID:

```text
defenses/patches/<patch_id>/
  manifest.json   metadata, file scope, and regression checks
  <diff file>     the change itself, named in the manifest
```

| Field | Meaning |
| --- | --- |
| `patch_id` | Lowercase letters, digits, and hyphens; matches the folder name |
| `status` | `draft` or `ready`. The executor must refuse a draft. |
| `origin` | `known_good_fallback` (written by a person) or `generated` |
| `base_version` | The only lab version the patch applies to |
| `policy_id` | The access policy the patch enforces |
| `target_route` | The route the patch changes |
| `allowed_files` | Repository-relative paths the patch may touch. Required when ready. |
| `diff_file` | File name of the diff in this folder. Required when ready. |
| `change`, `explanation` | What changes and why, in plain language |
| `regression_checks` | Checks the referee must run. Must include `unauthorized_access` and `owner_access`. |

`backend/app/agents/blue/patches.py` validates every manifest. It rejects absolute paths, `..`, and paths outside the patch folder.

## Current patches

- [ownership-fix-001](patches/ownership-fix-001/manifest.json): checks order ownership on `GET /api/orders/{id}`. **Draft** until Member 3 publishes the lab's order handler. Then fill in `allowed_files`, add the diff, and set `status` to `ready`.
