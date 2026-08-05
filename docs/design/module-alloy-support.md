# Module Card: Alloy & Perfect Essence (Swap Currencies)

## Overview

Alloys and Perfect Essences are **swap currencies** — they operate on Rare items
by removing one existing mod and adding one guaranteed mod. This is fundamentally
different from Lesser/Normal/Greater Essences, which upgrade Magic → Rare.

The codebase currently lumps alloys into `perfect_essence` via a CLI mapping.
This works mechanically but lacks first-class support in the optimizer and
prevents proper price tracking, seed strategies, and alloy-specific actions.

## Mechanics

### Three Distinct Essence-Family Operations

```
Lesser/Normal/Greater Essence (essence_upgrade)
  Input:  Magic item
  Output: Rare item with guaranteed essence mod + random fill to 4-6 mods
  Use:    Cheap Magic→Rare with one anchored mod

Perfect Essence (essence_swap)
  Input:  Rare item
  Output: Same Rare, 1 random mod removed, 1 guaranteed mod added
  Use:    Targeted mod replacement on finished Rare items

Alloy (essence_swap — same mechanic as Perfect Essence)
  Input:  Rare item
  Output: Same Rare, 1 random mod removed, 1 guaranteed mod added
  Use:    Targeted mod replacement, different mod pool (Runic Ward, etc.)
```

### Alloy List (13 alloys, Runes of Aldur league)

| Alloy | Base Name | Example Effect |
|-------|-----------|----------------|
| Runic Alloy | Runic | +Runic Ward / Runic Ward Regen |
| Adaptive Alloy | Adaptive | Varies by slot |
| Celestial Alloy | Celestial | Varies by slot |
| Cyclonic Alloy | Cyclonic | Varies by slot |
| Expansive Alloy | Expansive | Varies by slot |
| Mystic Alloy | Mystic | Varies by slot |
| Prismatic Alloy | Prismatic | Varies by slot |
| Protective Alloy | Protective | Varies by slot |
| Sovereign Alloy | Sovereign | Varies by slot |
| Swift Alloy | Swift | Varies by slot |
| The Runebinder's Alloy | The Runebinder's | Varies by slot |
| The Runefather's Alloy | The Runefather's | Varies by slot |
| Transcendent Alloy | Transcendent | Varies by slot |

### Perfect Essence List (19 perfect essences)

Same swap mechanic, different mod pools (Body, Mind, Flames, Ice, etc.).

### Omen Interactions

| Omen | Effect | Consumed At |
|------|--------|-------------|
| Sinistral Crystallisation | Force removal to target prefix only | Application |
| Dextral Crystallisation | Force removal to target suffix only | Application |

Crystallisation omens work with **both** Perfect Essences and Alloys despite
wiki descriptions only mentioning essences.

### Key Constraints

- Item must be **Rare** (not Normal, not Magic)
- Removes 1 random existing mod (non-fractured)
- Adds 1 guaranteed mod from the essence/alloy's pool
- Guaranteed mod varies by item slot (e.g. Runic Alloy gives +Runic Ward on Ring, %Regen on Belt)
- Cannot remove the only mod on a Rare
- Family blocking: cannot use if the guaranteed family already exists on the item

## Current State

### What Works

| Layer | Status | Details |
|-------|--------|---------|
| DB/ETL | OK | 13 alloys stored with `tier='Alloy'`, `effect_type='swap'` in essences table |
| mod_weights | OK | Alloy mods in `pool='perfect_essence'` (516 entries total, shared with perfect essences) |
| Essence resolver | Partial | Resolves by name+slot, but `get_currency_key("Alloy")` returns `""` |
| Craft CLI | Works | Maps `"Alloy"` → `"perfect_essence"` currency key → `essence_swap` op |
| Simulator | Partial | `essence_swap` op works, but no dedicated `"alloy"` currency key |
| Optimizer | Missing | No alloy actions, no prices, no seeds |

### What's Missing

1. **No distinction between perfect essence and alloy mod pools**
   - Both share `pool='perfect_essence'` in mod_weights
   - Cannot tell which mods come from alloys vs perfect essences
   - Optimizer can't select "use Runic Alloy specifically"

2. **No alloy price resolution**
   - `_resolve_essence_prices()` in preflight.py handles lesser/normal/greater/perfect only
   - No `alloy` price alias in the currencies table

3. **No optimizer actions for alloys**
   - Rust evaluator has no ALLOY or PERFECT_ESSENCE action
   - GP cannot discover swap strategies

4. **Essence resolver gap**
   - `get_currency_key("Alloy")` returns `""` (empty string)
   - Test explicitly asserts this empty return

## Implementation Plan

### Phase 1: Separate Alloy Pool in DB (ETL)

- Add `pool='alloy'` to mod_weights for alloy-sourced mods (currently all in `perfect_essence`)
- Keep `perfect_essence` for actual perfect essence mods only
- ETL: `poe2db_client.py` already detects `tier='Alloy'` — route to `pool='alloy'` in mod_weights
- Migrate existing data: UPDATE mod_weights SET pool='alloy' WHERE source is alloy

**Decision needed**: Can we distinguish alloy vs perfect essence mods in the existing
mod_weights data? They share families (e.g. both may provide IncreasedLife). May need
to track the source essence/alloy name alongside the mod entry, or accept that the
pools overlap and use a union for swap operations.

### Phase 2: Simulator Currency Keys

Add to `CURRENCIES` dict in simulator.py:
```python
"alloy":            {"op": "essence_swap", "min_lv": 0, "from_rarity": ["Rare"]},
```

Update `_apply_essence_swap` to accept alloy pool mods. The operation is identical
to perfect essence — only the mod pool differs.

Update Crystallisation omen `applies_to` to include `"alloy"`:
```python
"sinistral_crystallisation": {"applies_to": ["perfect_essence", "alloy"], "del_gentype_only": 1},
"dextral_crystallisation":   {"applies_to": ["perfect_essence", "alloy"], "del_gentype_only": 2},
```

### Phase 3: Essence Resolver

- `get_currency_key("Alloy")` → return `"alloy"` instead of `""`
- Update test assertion in `test_essence_resolver.py:168`

### Phase 4: Price Resolution

Add alloy price aliases to preflight.py `_resolve_essence_prices()` or a new
`_resolve_alloy_prices()`:
- Generic `alloy` price (average or cheapest alloy)
- Per-alloy prices if we want fine-grained: `runic_alloy`, `celestial_alloy`, etc.
- Craft CLI: add alloy price keys to `_PRICE_NAMES`

### Phase 5: Optimizer Support

**5a. Rust action**:
- Add `ALLOY` (or `PERFECT_ESSENCE`) action to Rust evaluator
- Mechanic: remove 1 random mod (respect fractured), add 1 from alloy/perfect pool
- Crystallisation omen support: restrict removal to prefix/suffix

**5b. Preflight**:
- Query `pool='alloy'` and `pool='perfect_essence'` separately
- Pass alloy pool families/sizes to Rust via ModPool
- Detect `ModTarget.pool_source = "alloy"` or `"perfect_essence"` for swap targets

**5c. Seeds**:
- Add swap-based seed strategies:
  - "Fill prefixes → alloy swap suffix" (with dextral crystallisation)
  - "Essence upgrade → perfect essence swap unwanted mod"
- Add to `ALL_SEEDS` and `PHASE_SEEDS` variants

**5d. GP operators**:
- Add `Currency.ALLOY` / `Currency.PERFECT_ESSENCE` to gene.py
- Add to `_OMEN_COMPATIBLE_CURRENCIES` with crystallisation omens
- `random_action()` / `mutate_action()` support

### Phase 6: Craft CLI Polish

- `pool` command: add alloy section (like essence section)
- `use` command: accept alloy names directly (already partially works)
- Show alloy mods with slot-specific descriptions

## Priority

**P3** — below desecration fidelity (done) and lich omens, but above catalysing
exaltation. Swap currencies are a real crafting strategy for endgame items where
you want to replace a bad mod without rerolling everything.

## Dependencies

- Essence resolver must distinguish alloy from perfect essence
- DB may need schema change or at least re-ETL to separate pools
- Rust evaluator needs new action type (similar complexity to REVEAL)

## Test Plan

- Unit: essence_swap with alloy pool mods produces correct results
- Unit: crystallisation omens target correct affix type on alloy swap
- Unit: family blocking prevents alloy when guaranteed family exists
- Integration: optimizer discovers alloy swap strategy for alloy-pool target
- Regression: existing perfect essence behavior unchanged

## Reference

- Simulator: `poe2_crafting_mcp/crafting/simulator.py` (lines 308-311, 1327-1330, 1547-1600)
- Essence resolver: `poe2_crafting_mcp/crafting/essence_resolver.py`
- Craft CLI alloy mapping: `poe2_crafting_mcp/craft_cli.py` (line 1084)
- ETL alloy detection: `poe2_crafting_mcp/data/poe2db_client.py` (lines 480-498)
- Fidelity gap doc: `docs/design/optimizer-simulation-fidelity-gap.md`
