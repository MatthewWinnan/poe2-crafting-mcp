# Module Card: Mod Tags & Catalysing Exaltation

## Overview

Mods in PoE2 have tags (e.g. `damage`, `attack`, `elemental`, `fire`). These tags
are used by certain omens to filter or bias the mod pool during crafting.

### Removed Omens (patch 0.4.0)

**Homogenising Coronation** and **Homogenising Exaltation** were removed from the
game in patch 0.4.0. They filtered regal/exalt pools to only mods sharing tags with
existing mods. These need to be removed from the simulator, blacklisted from scraping,
and cleaned from documentation.

### Active Omen: Catalysing Exaltation

**Catalysing Exaltation** is still obtainable (Ritual reward, drop level 75). It
consumes all catalyst quality from the item and applies a **weight multiplier** to
mods matching the catalyst's tag category:
- 20% quality → 5x weight multiplier
- 40% quality → 7.5x weight multiplier (Breach Rings only)

This is a weight bias, not a pool filter — non-matching mods can still roll, just
at much lower relative probability.

## Tag System

Every mod in the DB has a `tags` JSON array in `mod_weights`. There are 58 distinct
tags across all pools:

**Damage:** `damage`, `physical_damage`, `elemental_damage`, `chaos_damage`, `caster_damage`
**Element:** `physical`, `elemental`, `fire`, `cold`, `lightning`, `chaos`
**Defence:** `defences`, `armour`, `evasion`, `energy_shield`, `runic_ward`, `block`
**Resistance:** `resistance`, `elemental_resistance`, `fire_resistance`, `cold_resistance`,
`lightning_resistance`, `chaos_resistance`
**Resource:** `resource`, `life`, `mana`, `flat_life_regen`
**Offense:** `attack`, `caster`, `critical`, `caster_critical`, `caster_speed`
**Speed:** `speed`
**Ailment:** `ailment`, `bleed`, `poison`
**Attribute:** `attribute`
**Minion:** `minion`, `minion_damage`, `minion_resistance`, `minion_speed`
**Charge:** `endurance_charge`, `frenzy_charge`, `power_charge`
**Other:** `drop`, `gem`, `aura`, `flask`, `life_flask`, `charm`, `curse`, `has_attack_mod`
**Faction/Special:** `amanamu_mod`, `ulaman_mod`, `kurgal_mod`, `unveiled_mod`,
`chaos_warband`, `blue_herring`, `upgraded_corruption_mod`

### Catalyst → Tag Mapping

| Catalyst | Tags Boosted |
|----------|-------------|
| Turbulent | `elemental_damage`, `elemental` |
| Imbued | `caster`, `caster_damage`, `caster_speed`, `caster_critical` |
| Fertile | `life`, `mana`, `resource` |
| Prismatic | `resistance`, `elemental_resistance`, `fire_resistance`, etc. |
| Intrinsic | `attribute` |
| Tempering | `defences`, `armour`, `evasion`, `energy_shield` |
| Abrasive | `critical`, `caster_critical` |
| Noxious | `ailment`, `bleed`, `poison` |

## Cleanup TODO: Remove Homogenising Omens

### Files to modify:

1. **`poe2_crafting_mcp/crafting/simulator.py`**
   - Remove `homogenising_exaltation` and `homogenising_coronation` from OMENS dict
   - Remove `homogenise` parameter from `roll_mod()`
   - Remove homogenise filter logic (lines 1128-1138)
   - Remove `homogenise` variable from `apply_currency()` (lines 1215, 1230-1231)

2. **`poe2_crafting_mcp/craft_cli.py`**
   - Remove `homogenising_exaltation` from omen display dict (line 680)
   - Remove homogenise check (line 996)

3. **`poe2_crafting_mcp/data/lookup_cli.py`**
   - Remove homogenise check (line 2224)

4. **`tests/test_simulator.py`**
   - Remove/update test asserting homogenising_exaltation exists (line 718)

5. **Scraper blacklist** — add to poe2db_client.py or wiki_client.py:
   - `"Omen of Homogenising Coronation"` — removed in 0.4.0
   - `"Omen of Homogenising Exaltation"` — removed in 0.4.0

6. **Docs** — already updated in this file. Also update:
   - `docs/design/optimizer-simulation-fidelity-gap.md` — remove from omen table
   - `docs/research/omens-and-abyss.md` — mark as removed
   - `docs/research/phase3-crafting-strategies.md` — mark as removed

## Implementation Plan: Catalysing Exaltation

### Phase 1: Tag Data in Rust ModPool

Pass tag bitmasks from preflight → bridge → Rust:
- Each mod gets a `u64` tag bitmask (58 tags fit in 64 bits)
- `ModPool` stores `prefix_tags: Vec<u64>` and `suffix_tags: Vec<u64>`
- Bridge encodes tags with a stable tag→bit mapping

### Phase 2: Catalyst State in ItemState

```rust
pub catalyst_type: u8,    // 0=none, 1=turbulent, 2=imbued, ...
pub catalyst_quality: u8, // 0-40 (percentage)
```

### Phase 3: Catalysing Roll in Rust

When `omen == CATALYSING_EXALTATION`:
1. Look up catalyst_type → tag bitmask
2. For each mod in pool: if `mod_tags & catalyst_tags != 0`, multiply weight by
   `1 + (quality / 20) * 4` (linear: 5x at 20%, 7.5x at 30%, 9x at 40%)
3. Consume catalyst quality (set to 0)
4. Roll from reweighted pool

### Phase 4: GP Operators & Seeds

- Add `CATALYSING_EXALTATION` omen ID to Rust and gene.py
- Add to `_OMEN_COMPATIBLE_CURRENCIES` for exalt variants
- Seed: "Apply catalyst → catalysing exalt → targeted suffix slam"
- Only relevant for jewellery (rings, amulets, belts) — validate in operators

### Phase 5: Catalyst Currency in Simulator

Add catalyst application as a currency (sets catalyst_type + quality on item).
May need `--catalyst` CLI flag to specify catalyst type on the item.

## Priority

**P6** in fidelity gap (replacing the removed homogenising omens slot).
Catalysing Exaltation is still obtainable and used for endgame jewellery crafting.
Lower priority than desecration fidelity and alloys since it only applies to
jewellery with catalysts.

## Reference

- Python simulator OMENS: `simulator.py` lines 389-390 (to be removed for homogenising)
- Catalysing omen: `simulator.py` line 390 (`"catalyse": True` — no weight logic yet)
- Mod tags: `mod_weights.tags` column (JSON array, 58 distinct tags)
- Patch notes: 0.4.0 removed Homogenising Coronation + Exaltation
