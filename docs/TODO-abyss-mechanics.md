# TODO: Abyss/Desecration Mechanics Gap in Optimizer

## Context
The Rust optimizer's REVEAL action is heavily simplified compared to the real
game mechanics (modeled correctly in `desecration.py`). The GP can discover
desecrate+reveal strategies now, but the simulation fidelity is low — it
doesn't model affix type determination, omens, or pool sizes, so it can't
discover or evaluate important real strategies like "fill prefixes then
desecrate for guaranteed suffix".

## How Desecration Actually Works (verified Aug 2025)

### Flow
1. **Apply bone** to a Rare item → adds a blank "desecrated" slot
2. **Go to Well of Souls** → blank mod resolves into 3 options (pick 1)
3. **Player chooses** one of the 3 revealed options

### Lich omens (Blackblooded, Liege, Sovereign)
- **Consumed at bone application** (desecrate step), not at reveal
- **Affect what appears at reveal** — restrict the 3 options to one faction
- **Weapon or Jewellery ONLY** — do not work on armour, jewels, or waystones
- Consumed even if no faction mods can roll (wrong ilvl, blocked group, etc.)

| Omen | Faction | Slot Restriction |
|------|---------|-----------------|
| Blackblooded | Kurgal | Weapon or Jewellery |
| Liege | Amanamu | Weapon or Jewellery |
| Sovereign | Ulaman | Weapon or Jewellery |

### Other desecration omens (no slot restriction)
Consumed at bone application (desecrate step):
- **Sinistral Necromancy** — force prefix on reveal
- **Dextral Necromancy** — force suffix on reveal
- **Putrefaction** — replace all mods + corrupt item

Consumed at reveal step (Well of Souls):
- **Abyssal Echoes** — reroll 3 fresh options once (3+3, not 6 picks)

Consumed on annulment:
- **Omen of Light** — annulment targets only the abyss mod

### Bone slot categories
- **Jawbone** → weapons + quivers
- **Rib** → armour (body, gloves, boots, helmets, shields)
- **Collarbone** → jewellery (rings, amulets, belts)
- **Cranium** → jewels
- **Vertebrae** → waystones

## What the simulator models (desecration.py) vs what Rust models

| Mechanic | Simulator | Rust Optimizer |
|----------|-----------|----------------|
| Desecrate requires Rare | YES | YES |
| Re-desecration after annul | YES | YES |
| Reveal requires desecrated state | YES | YES |
| Affix type from open slots | YES | NO (always suffix) |
| Necromancy omen forces affix | YES | NO |
| Lich omens (weapon/jewellery only) | YES | NO |
| Lich omen slot validation | YES | N/A |
| Abyssal Echoes (3+3 reroll) | YES | NO |
| Pool size affects hit probability | YES | NO (hardcoded 20%) |
| Omen of Light annuls abyss mod | YES | YES |
| Pick-from-N without replacement | YES | NO (flat 20%) |

## Tasks (priority order)

### 1. Affix type determination in REVEAL
Currently REVEAL always tries to place a suffix. Should determine prefix vs
suffix based on open slots (matching `determine_affix_type` in desecration.py):
- All prefixes full + suffix open → suffix (guaranteed)
- All suffixes full + prefix open → prefix (guaranteed)
- Both open → random 50/50
- Neither open → skip (no room)

This is the most impactful fix — it enables the "fill prefixes → desecrate →
guaranteed suffix target" strategy that experienced players use.

### 2. Dynamic hit probability based on pool size
Replace hardcoded 20% with actual calculation:
- P(hit) = 1 - C(pool_size - target_count, draws) / C(pool_size, draws)
- Need to pass desecrated pool size per item_class to Rust
- For Gloves_int suffixes: 14 families, 3 draws → P = 19.7% (close to 20%)
- For items with fewer desecrated mods, probability differs significantly

### 3. Omen of Abyssal Echoes support
Echoes is consumed at reveal (not bone application). It allows ONE reroll
of 3 fresh options, replacing the first 3 (not 6 total picks).

Correct probability model: P(hit) = 1 - P(miss)^2
- P(miss single draw) = C(pool-1, 3) / C(pool, 3)
- P(hit with echoes) = 1 - P(miss)^2
- For Gloves_int (pool=14, target=1): 1 - (11/14 * 10/13 * 9/12)^2 ≈ 38.3%
- (Previously modeled as 6-draw: 42.9% — was wrong)
- Gene.py already has ABYSSAL_ECHOES = 9
- Simulator already corrected to 3+3 model

### 4. Necromancy omen support (prefix/suffix forcing)
- Omen of Sinistral Necromancy (gentype_only=1) → force prefix
- Omen of Dextral Necromancy (gentype_only=2) → force suffix
- Already defined in simulator OMENS dict
- Useful when you can't or don't want to fill all prefix slots first

### 5. Lich omen support (faction pool narrowing) — WEAPON/JEWELLERY ONLY
- Omen of Blackblooded → only Kurgal faction mods in reveal
- Omen of Liege → only Amanamu faction mods
- Omen of Sovereign → only Ulaman faction mods
- **Only applies to weapons and jewellery** — skip for armour targets
- Consumed at bone step, affects the 3 reveal options
- Much smaller pool = much higher hit rate for faction-specific mods
- Need faction tags in the desecrated pool data passed to Rust
- Optimizer should never suggest lich omens for armour item targets

### 6. Desecrated pool data in Rust
To support tasks 2-5, need to pass desecrated pool metadata to Rust:
- Pool size per affix type (prefix count, suffix count)
- Faction breakdown (how many mods per faction)
- Item slot category (weapon/jewellery/armour) for lich omen validation
- Could add to ModPool struct or as separate arrays in batch.rs

## Files to modify
- `crates/poe2-optimizer/src/actions.rs` — REVEAL action logic
- `crates/poe2-optimizer/src/pool.rs` — desecrated pool metadata in ModPool
- `crates/poe2-optimizer/src/batch.rs` — new optional params for desecrated data
- `poe2_crafting_mcp/crafting/optimizer/bridge.py` — serialize desecrated pool info
- `poe2_crafting_mcp/crafting/optimizer/preflight.py` — query desecrated pool stats

## Reference
- Simulator implementation: `poe2_crafting_mcp/crafting/desecration.py`
- Desecration probability: `desecration_hit_probability()` uses combinatorial formula
- Craft CLI already handles full desecration flow with omens
- Lich omen slot restriction: weapon/jewellery only (poe2wiki, poe2db confirmed)
