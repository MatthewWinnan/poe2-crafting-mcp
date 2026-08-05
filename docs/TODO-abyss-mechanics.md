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
| Affix type from open slots | YES | YES |
| Necromancy omen forces affix | YES | YES |
| Lich omens (weapon/jewellery only) | YES | NO |
| Lich omen slot validation | YES | N/A |
| Abyssal Echoes (3+3 reroll) | YES | YES |
| Pool size affects hit probability | YES | YES |
| Omen of Light annuls abyss mod | YES | YES |
| Pick-from-N without replacement | YES | NO (flat 20%) |

## Tasks (priority order)

### 1. ~~Affix type determination in REVEAL~~ DONE
Rust REVEAL now determines prefix vs suffix from open slots:
- All prefixes full + suffix open → suffix (guaranteed)
- All suffixes full + prefix open → prefix (guaranteed)
- Both open → random 50/50
- Neither open → skip (no room)
Enables "fill prefixes → desecrate → guaranteed suffix" strategy.

### 2. ~~Dynamic hit probability based on pool size~~ DONE
Replaced hardcoded 20% with P(hit) = 3/pool_size (for 1 target, 3 draws).
Desecrated pool sizes passed from preflight → bridge → batch → Rust ModPool.
For Gloves_int suffixes: 14 families → P = 3/14 = 21.4%.

### 3. ~~Omen of Abyssal Echoes support~~ DONE
Echoes on REVEAL uses 3+3 model: P(hit) = 1 - ((pool-3)/pool)^2.
Rust checks omen == ABYSSAL_ECHOES and squares the miss probability.
For Gloves_int: 38.3% (vs 21.4% without).

### 4. ~~Necromancy omen support~~ DONE
Rust checks omen == SINISTRAL_NECROMANCY (force prefix) or
DEXTRAL_NECROMANCY (force suffix) on REVEAL action.
Seeds added for both variants + fill-prefix-then-desecrate strategy.

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
