# Arena Agent 2D Sprites

Clean, transparent, production-ready 2D character sprites for the RowdyHacks 2026 Arena UI.

Generated from the canonical Captain Orbit sprite pipeline (`captain-orbit-directional-lowered-v1.png`) with role-tailored action poses and team-coded palettes.

## Sprite Roster

| File | Agent Name | Team | Role | Pose / Action Description | Dimensions | Format |
|---|---|---|---|---|---|---|
| `red-scout.png` | **Red Scout** | Red | Scout | Forward scouting run stride, mobile recon | 192 × 208 px | 32-bit RGBA PNG (Transparent) |
| `red-operator.png` | **Red Operator** | Red | Operator | Head bowed, typing/hacking on cyber datapad | 192 × 208 px | 32-bit RGBA PNG (Transparent) |
| `blue-monitor.png` | **Blue Monitor** | Blue | Monitor | Head raised, monitoring telemetry on cyber datapad | 192 × 208 px | 32-bit RGBA PNG (Transparent) |
| `blue-defender.png` | **Blue Defender** | Blue | Defender | Alert forward-facing defensive guard stance | 192 × 208 px | 32-bit RGBA PNG (Transparent) |
| `arena-agent-lineup.png` | *All 4 Agents* | Both | All | Side-by-side roster preview (Scout, Operator, Monitor, Defender) | 768 × 208 px | 32-bit RGBA PNG (Transparent) |

## Specifications & Visual Design

- **Canvas Size**: 192 × 208 pixels per sprite.
- **Background**: Fully transparent alpha channel (`#00000000`).
- **Baseline Alignment**: All characters are bottom-grounded at `y = 162–166 px` with 1 px margin at the foot baseline, ensuring perfectly uniform vertical alignment across agent cards.
- **Red Team Design**:
  - Suit: Vibrant Crimson Red (`#C01010` to `#FF3030`)
  - Trim/Boots/Gloves: Tactical dark graphite/onyx (`#2C2D35`)
  - Antenna Beacon: Glowing crimson signal orb (`#FF2020`)
  - Operator Datapad: Exploitation terminal with red/amber interface readout
- **Blue Team Design**:
  - Suit: Deep Cobalt/Royal Blue (`#1A55CC` to `#3377EE`)
  - Trim/Boots/Gloves: Vibrant electric cyan (`#00D4FF`)
  - Antenna Beacon: Radiant cyan/blue beacon (`#00D4FF`)
  - Monitor Datapad: Security telemetry terminal with cyan readout

## Integration Guide for Arena UI (Codex)

Relative path from `RowdyHacks26_Project/arena/`:
```html
<!-- Example agent card snippet -->
<img class="agent-avatar"
     src="assets/agents/red-scout.png"
     alt="Red Scout"
     width="96"
     height="104" />
```

Recommended CSS:
```css
.agent-avatar {
  width: 96px;
  height: 104px;
  object-fit: contain;
  image-rendering: pixelated; /* crisp pixel art scaling */
  display: block;
  margin: 0 auto;
}
```
