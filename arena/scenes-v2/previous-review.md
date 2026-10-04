# Scene review — RowdyHacks26 arena

Reviewed: 2026-10-03. All six concept PNGs and four existing preview PNGs were opened and visually inspected.

**These are Codex technical recommendations, not Omar's approval. Omar's approval is pending for every asset.** No runtime HTML, CSS, JavaScript, fixture, or image has been changed by this review. `scene-review.html` is a static approval gallery only.

## Recommendation

Use the glossy toy-like concept direction, with `01_driver_start.png` as the art baseline. Preserve the existing battle-room composition and bring it into that direction. Two assets are technically APPROVED (one concept and one standalone fallback), six NEED REVISION, and two should be REMOVED/REPLACED in the new sequence. Preserve every original file.

The robber's beret, mask, striped vest, and red sleeves; the officer's white cap, pale blue uniform, and badge; and the auditor's glasses, shirt, tie, and tablet are generally consistent. The main continuity failures are the bank entrance, Red's car, and mixing glossy concepts with matte previews. Standardize on the columned bank with BANK LAB signage and the arrival scene's red hatchback. Keep the auditor visually separate from both teams.

All ten scenes are stylized, fictional, and non-graphic. No readable credentials, actual target address, private agent plan, referee answer key, or actionable attack instructions were observed. This is a visual assessment of pixels, not a provenance, metadata, or complete security audit. Abstract code-like bars and dashboard maps must remain decorative and never be populated with private team records.

## Review table

| Asset | Intended role | Technical recommendation | Main reason |
|---|---|---|---|
| Concept: [01_driver_start.png](concept-scenes/01_driver_start.png) | Driver / ready to start | **APPROVED** | Clear opening; use as concept baseline. |
| Concept: [02_bank_arrival.png](concept-scenes/02_bank_arrival.png) | Red arrival | **NEEDS REVISION** | Collision distracts from arrival; establish consistent bank/car. |
| Concept: [03_blue_dispatch.png](concept-scenes/03_blue_dispatch.png) | Blue incident alert / dispatch | **NEEDS REVISION** | Different bank entrance; alert needs event-backed HTML explanation. |
| Concept: [04_vault_keypad.png](concept-scenes/04_vault_keypad.png) | Red vault attempt | **NEEDS REVISION** | Open vault and fixed alarm imply premature access and incident. |
| Concept: [05_blue_pursuit.png](concept-scenes/05_blue_pursuit.png) | Blue response / pursuit | **NEEDS REVISION** | Car changes; green check implies premature verified recovery. |
| Concept: [06_auditor_arrest_result.png](concept-scenes/06_auditor_arrest_result.png) | Auditor / optional Blue outcome | **NEEDS REVISION** | Checks and arrest predetermine a Blue outcome. |
| Existing preview: [01_exterior_start.png](../Heist_Blender_Designs/arena_previews/01_exterior_start.png) | Fallback exterior / reference | **APPROVED** | Readable standalone fallback; style differs from concepts. |
| Existing preview: [02_battle.png](../Heist_Blender_Designs/arena_previews/02_battle.png) | Battle-room activity | **NEEDS REVISION** | Useful layout; mixed style and baked FIXTURE PREVIEW. |
| Existing preview: [03_red_vault.png](../Heist_Blender_Designs/arena_previews/03_red_vault.png) | Legacy Red victory | **REMOVE/REPLACE** | Unconditional winner text and outcome pose. |
| Existing preview: [04_blue_arrest.png](../Heist_Blender_Designs/arena_previews/04_blue_arrest.png) | Legacy Blue victory | **REMOVE/REPLACE** | Unconditional winner text and outcome pose. |

## Per-scene findings and required changes

### Concept: 01_driver_start.png — APPROVED

**Readability, continuity, workflow, screens, and safety:** Strong opening composition: Red, the route, and bank are clear. Beret, mask, red sleeves, striped vest, warm bank lighting, and toy proportions establish the visual direction. No secret, target address, credential, or security result is legible. The background police car can be treated as static scenery, not a dispatch event.

**Before integration:** Keep as proposed art baseline. Implement a real, keyboard-accessible Start button in HTML; the pictured START label is decorative. Add persistent FIXTURE / RECORDED / LIVE telemetry labeling plus a separate illustrative-art caption. Omar approval still pending.

### Concept: 02_bank_arrival.png — NEEDS REVISION

**Readability, continuity, workflow, screens, and safety:** Bank façade matches the driver shot; Red remains recognizable. The hatchback clearly establishes a vehicle reference. Broken barriers, dust, and tipped cones read as a collision rather than simple arrival. Police are already present before the intended dispatch. There is no graphic injury, private plan, or legible result.

**Before integration:** Use this red hatchback consistently in pursuit. Make arrival a parked or stopping vehicle with intact barriers; remove or de-emphasize early police lights if dispatch should first appear later. Add the same BANK LAB identity to the columned façade. This is a visual arrival metaphor, not evidence of target access.

### Concept: 03_blue_dispatch.png — NEEDS REVISION

**Readability, continuity, workflow, screens, and safety:** Officer's pale blue uniform, white cap, badge, and toy proportions match the final scene. Alarm and bank icons read well, but checklist strokes do not explain what was detected. The flat BANK LAB entrance with a wheel-shaped door differs substantially from the columned bank in driver and arrival views. No Red board or actionable private intelligence is legible.

**Before integration:** Restore the same columned façade and BANK LAB signage. Keep the dashboard generic; remove ambiguous completed-check marks or clearly label the screen as illustrative. Supply 'Simulated incident detected' and a sanitized Blue handoff as HTML text from events. Detection alone must not mean verified vault access.

### Concept: 04_vault_keypad.png — NEEDS REVISION

**Readability, continuity, workflow, screens, and safety:** Character continuity is strong and the keypad is immediately readable. BANK LAB and System Status are legible; abstract red activity bars do not expose actual code, credentials, or private plans. The vault is already open and Red carries a money bag, implying success before the attempted action has been verified. Red database warnings and an alarm are already baked into this pre-alarm phase.

**Before integration:** Close the vault for the attempt scene. Use a protected synthetic-data symbol instead of exposed gold or acquired loot. Neutralize the fixed alarm/warning state so events can control it, or explicitly reserve a separate alarm variant. Display attempt, evidence, service availability, and referee verdict independently in HTML. Never infer data access from the status screen.

### Concept: 05_blue_pursuit.png — NEEDS REVISION

**Readability, continuity, workflow, screens, and safety:** Blue and Red silhouettes remain recognizable and the pursuit reads clearly. Red's vehicle changes from a red enclosed hatchback to a gray open convertible. The bank returns to a columned façade but signage and surrounding street differ. A full bar and green check hard-code recovery or success while the intended phase is still response. No injury, weapon, secret, or private plan is visible.

**Before integration:** Reuse the arrival hatchback and canonical bank. Replace the full bar/check with a neutral response icon or pending indicator. Drive applied-action and independently verified-fix states through event data. Bank availability must remain separate from the vault-data mission outcome.

### Concept: 06_auditor_arrest_result.png — NEEDS REVISION

**Readability, continuity, workflow, screens, and safety:** Best concept match to the existing battle room: split Red/Blue desks, central vault, ceiling lights, banners, auditor glasses/tie/tablet, and recognizable team characters. Escort is restrained and non-graphic. Blank screen strokes do not leak team records, but checks on both the tablet and jumbotron imply a completed verified defense. Arrest selects a Blue ending and cannot stand for every possible result.

**Before integration:** Provide neutral tablet/jumbotron art and a pending-audit pose for the shared final phase. Keep an escort variant only for a Blue result authorized by the independent referee; also support Red, inconclusive, and stopped outcomes without showing arrest. Put the exact result, evidence status, and source mode in HTML. Fixture referee examples must still say FIXTURE, never live verification.

### Existing preview: 01_exterior_start.png — APPROVED

**Readability, continuity, workflow, screens, and safety:** Readable overview of team roles and auditor independence; columned bank and character designs connect to the concepts. START is decorative and the small background signs are hard to read at presentation distance. Matte lighting, simpler geometry, and lower resolution differ noticeably from the glossy concepts. No private record or explicit winner is shown.

**Before integration:** Approve technically as a standalone fallback and continuity reference, pending Omar. Avoid alternating it with glossy concept art in a final seamless sequence. Repeat role labels and a real Start control in HTML; keep an explicit illustrative-art and telemetry-source label.

### Existing preview: 02_battle.png — NEEDS REVISION

**Readability, continuity, workflow, screens, and safety:** Excellent role layout and clear separation of team stations. The auditor has a neutral tablet; no victory is declared. FIXTURE PREVIEW is honest but tiny. Small screen text cannot replace accessible HTML panels. Character shapes and room arrangement match concept 06, while materials, lighting, and resolution do not.

**Before integration:** Bring this composition into the chosen glossy concept style, or choose the older matte style for the whole sequence. Keep stations as abstract sanitized summaries. A baked FIXTURE PREVIEW label means this exact asset should remain fixture-only unless that screen is replaced; a LIVE badge elsewhere would not resolve contradictory image text.

### Existing preview: 03_red_vault.png — REMOVE/REPLACE

**Readability, continuity, workflow, screens, and safety:** Red identity is consistent with the older renders and the scene is fictional/non-graphic. Open vault, falling cash, and RED TEAM WINS hard-code a verdict and frame success as stolen money. It lacks an auditor or independent verification state and does not show legitimate bank access remaining available. No credential or answer key is visible.

**Before integration:** Exclude from the new mission-one sequence. Preserve the original file. Replace with neutral protected-data art plus a separate optional Red result variant shown only on an appropriate independent referee event. The result text must be DOM text, and successful website availability alone cannot award Red a win.

### Existing preview: 04_blue_arrest.png — REMOVE/REPLACE

**Readability, continuity, workflow, screens, and safety:** The same battle room, team stations, and characters preserve older-style continuity. Red and Blue overlap enough to weaken the escort silhouette. BLUE TEAM WINS is unconditional while the jumbotron still says FIXTURE PREVIEW and shows a welcome/health screen. Neither the pose nor availability display establishes a verified protected-data result.

**Before integration:** Exclude from the new default final phase; preserve the file. Prefer a revised concept 06 with neutral screens and a referee-gated escort variant. Support pending, inconclusive, Red, Blue, and stopped results explicitly; do not use a winning plaque as the source of truth.

## Proposed event sequence after approval and revisions

1. Ready: driver art, real HTML Start control, explicit source mode.
2. Arrival: revised parked hatchback; sanitized Red activity only.
3. Battle room: matching-style room with distinct Red and Blue panels and neutral auditor.
4. Vault attempt: closed vault/protected synthetic data; attempted access, no victory.
5. Incident/alarm: event changes alarm and jumbotron; artwork does not assert access or outage.
6. Dispatch: revised Blue dashboard; detection and handoff are distinct from verified findings.
7. Response/pursuit: matching hatchback; action applied is distinct from a verified fix.
8. Audit: neutral pending scene first; optional ending only from independent referee data. Red, Blue, inconclusive, or stopped all remain possible.

An alarm phase can reuse the revised attempt or battle image with a DOM alarm; eight phases do not require eight unique images. Timeline highlighting, scene captions, active-agent state, source mode, and auditor result must come from events. Decorative screen strokes cannot serve as evidence.

## Runtime truth rules for the next step

- Keep the telemetry source label FIXTURE / RECORDED / LIVE persistently visible, including during transitions. The illustration is separately labeled as illustrative scene art; pre-created art is not recorded telemetry.
- Judge panels receive only sanitized summaries. Blue must not receive Red plans, boards, route intelligence, or findings that are private to Red. The pictured route is only a fictional prop.
- Independent referee output determines a result. It must identify which mission was verified; an alarm, website status, green check, escort, open vault, or animation timer is insufficient.
- Distinguish attempt, evidence-backed finding, proposed defense, applied action, and independently verified fix. Failed logins, unavailable targets, and timeouts remain inconclusive.
- Mission one is protected synthetic vault-data access while legitimate bank access remains available. Availability is measured separately and never substitutes for vault-data evidence.
- A fixture may illustrate a referee message, but remains FIXTURE and does not establish live verification. Missing referee data leaves the audit pending/inconclusive.
- Use only registered isolated lab targets; do not add arbitrary target inputs. No live adapter is implemented until a team-owned contract is supplied.

## Existing prototype gap (observed, unchanged)

`fixtures/session.json` currently describes **service availability disruption**, not mission one. Its final event correctly says the referee is not connected. After scene approval, the fixture needs a protected-data narrative with legitimate service availability tracked separately, and explicit auditor/referee state. `index.html` currently labels the art RECORDED ENVIRONMENT ART, which should become illustrative art to avoid confusing art with RECORDED telemetry.

## Approval checkpoint

Omar must approve the chosen visual direction/assets before website integration. This is explicit in the pasted request: “Do not build the final website around scenes that Omar has not approved.” `NEW_CHAT_HANDOFF.md` also says: “Do not set up MCP, Unreal, Blender automation, or website integration until Omar approves the scene direction.”

Requested decision: approve the glossy concept direction and the listed revisions, or supply different per-image choices. No images have been regenerated or edited, and no runtime integration has begun.
