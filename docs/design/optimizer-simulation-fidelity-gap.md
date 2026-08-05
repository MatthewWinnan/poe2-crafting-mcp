# Optimizer Simulation Fidelity Gap

## What the Craft Sim Models vs What the Rust Optimizer Models

### Currencies: Craft Sim (32) vs Rust Optimizer (22 modeled, 10 missing/simplified)

| Currency | Craft Sim | Rust Optimizer | Notes |
|----------|-----------|----------------|-------|
| transmute / greater / perfect | ✅ | ✅ | |
| augment / greater / perfect | ✅ | ✅ | |
| regal / greater / perfect | ✅ | ✅ | |
| exalted / greater / perfect | ✅ | ✅ | |
| chaos / greater / perfect | ✅ | ✅ | |
| annulment | ✅ | ✅ | |
| alteration | ✅ | ✅ | |
| alchemy | ✅ | ✅ | |
| divine | ✅ | ✅ (flag only) | |
| fracturing | ✅ | ✅ | Random mod locked |
| vaal | ✅ | ✅ (no-op) | Terminal — not modeled |
| scour | ✅ | ✅ | |
| reforge | ✅ | ✅ | 3-to-1 recycling |
| lesser/normal/greater essence | ✅ | ✅ | Magic→Rare + 1 guaranteed (essence pool tiers) |
| perfect essence | ✅ | ✅ | Swap mechanic |
| artificer (sockets) | ✅ | ❌ | Terminal step — not needed |
| armourer's scrap / whetstone | ✅ | ❌ | Terminal step — not needed |
| architect (double corrupt) | ✅ | ❌ | Terminal step — not needed |

### Mod Pools: DB Has 17, Optimizer Uses 3+

| Pool | DB Entries | In Optimizer | What It Is |
|------|-----------|--------------|------------|
| **normal** | 8,580 | ✅ | Standard crafting pool |
| **desecrated** | 694 | ✅ | Abyss/Well of Souls mods (pool sizes, affix type, omens) |
| **essence** | 1,935 | ✅ | Essence-specific guaranteed mods |
| **perfect_essence** | 516 | ❌ | Perfect essence swap mods |
| **corrupted** | 576 | ❌ | Vaal Orb corruption pool |
| **corruption_upgrade** | 935 | ❌ | Architect's Orb pool |
| **bonded** | 3,907 | ❌ | Rune-bonded mods (Aldur's Legacy) |
| **socketable** | 4,971 | ❌ | Rune/Soul Core socket effects |
| **chronomancy** | 102 | ✅ | Chronomancy rune pool (Boots) — merged via --runes |
| **destruction** | 162 | ✅ | Destruction rune pool (Weapons) — merged via --runes |
| **decay** | 138 | ✅ | Decay rune pool (Gloves) — merged via --runes |
| **marksman** | 168 | ✅ | Marksman rune pool (Gloves) — merged via --runes |
| **berserking** | 180 | ✅ | Berserking rune pool (Helmets) — merged via --runes |
| **breach_caster** | 89 | ❌ | Breach Ring caster mods |
| **breach_minion** | 74 | ❌ | Breach Ring minion mods |
| **breach_otherworldly** | 36 | ❌ | Breach amulet/belt/ring otherworldly |
| **soul** | 147 | ❌ | Soul Core effects |

### Rune Pools ✅

Rune pools (decay, marksman, destruction, chronomancy, berserking, soul) are
merged into the normal crafting pool in preflight when `--runes` is specified.
This correctly expands the mod pool so the optimizer accounts for the larger
pool size when calculating probabilities.

### Omens: Craft Sim vs Optimizer

| Omen | Craft Sim | Optimizer | Effect |
|------|-----------|-----------|--------|
| Sinistral/Dextral Exaltation | ✅ | ✅ | Force prefix/suffix |
| Greater Exaltation | ✅ | ✅ | Add 2 mods per exalt |
| Sinistral/Dextral Annulment | ✅ | ✅ | Remove prefix/suffix |
| Sinistral/Dextral Coronation | ✅ | ✅ | Regal targets side |
| Whittling | ✅ | ✅ (approximated) | Remove lowest-req mod |
| Abyssal Echoes | ✅ | ✅ | Re-roll reveal (3+3 model), stored at desecrate |
| Sinistral/Dextral Necromancy | ✅ | ✅ | Force prefix/suffix on reveal, stored at desecrate |
| Corruption | ✅ | ❌ | Remove "nothing" Vaal outcome |
| Sanctification | ✅ | ❌ | Remove negative Vaal outcomes |
| Light | ✅ | ✅ | Annul targets desecrated mod only |
| Catalysing Exaltation | ✅ (flag only) | ❌ | Weight multiplier toward catalyst tag |
| Homogenising Exaltation | ✅ (REMOVE) | ❌ | **REMOVED in 0.4.0** — delete from sim |
| Homogenising Coronation | ✅ (REMOVE) | ❌ | **REMOVED in 0.4.0** — delete from sim |

### Item State: Craft Sim vs Optimizer

| Field | Craft Sim | Optimizer (Rust) | Notes |
|-------|-----------|-----------------|-------|
| rarity | ✅ | ✅ | Normal/Magic/Rare |
| mods (family, tier, stat_text) | ✅ (full) | ✅ (family+tier only) | Sufficient for strategy |
| fractured mods | ✅ | ✅ (bitmask) | |
| corrupted | ✅ | ❌ (not needed) | Terminal |
| quality | ✅ | ❌ (not needed) | Terminal |
| sockets | ✅ | ❌ (not needed) | Terminal |
| essence_mod_family | ✅ | ✅ (flag only) | One per item |
| desecrated state | ✅ | ✅ (flag + omen bits 4-5) | Stores omen from bone step |
| divined state | N/A | ✅ (flag) | Pre-fracture step |
| mod values (numeric) | ✅ | ❌ | Only families/tiers tracked |
| implicits | ✅ | ❌ | Corruption only |
| reforge stock | ✅ | ❌ | Simplified to flat cost |

---

## Priority Gaps to Close

### P0: Sub-Goal Decomposition ✅
Sequential decomposition (N-target → N single-target phases) and cooperative
coevolution. WSJF ordering, initial state encoding, free-hit detection.

### P1: Rune/Alloy Pools ✅
Rune pools merged into normal pool in preflight (flat arrays). CLI `--runes` flag.

### P2: Essence Pool (not normal pool) ✅
Essences use separate tier data from `pool='essence'`. Three tiers (Lesser/Normal/Greater)
with distinct prices and Rust TierRank enum.

### P3: Greater Exaltation Omen ✅
Adds 2 mods in one exalt via `qty = if omen == GREATER_EXALTATION { 2 } else { 1 }`.

### P4: Omen of Light ✅
Annul removes ONLY the desecrated (abyss) mod and clears `has_been_desecrated_ever`
flag to allow re-desecration.

### P5: Desecration Fidelity ✅
REVEAL: affix type determination (open slots + necromancy omen), dynamic
P(hit) = 3/pool_size from desecrated pool metadata, Abyssal Echoes 3+3 reroll.
Omens consumed at DESECRATE (bone step), stored in item state bits 4-5, read
at REVEAL. GP discovers omen-enhanced strategies (e.g. `desecrate + dextral_necromancy`).
Simulator blocks multiple abyss mods per item.

### P6: Catalysing Exaltation + Tag System
Catalysing Exaltation (still obtainable): weight multiplier (5x at 20% quality)
toward catalyst-tagged mods. Requires tag bitmasks in Rust ModPool, catalyst state
in ItemState. Jewellery only. Homogenising omens were REMOVED in patch 0.4.0 — need
cleanup from simulator + scraper blacklist. See `docs/design/module-type-clusters.md`.

### P7: Lich Omens (Blackblooded/Liege/Sovereign)
Faction pool narrowing for weapons/jewellery only. Need faction tags in
desecrated pool data passed to Rust. Low priority — niche use case.

### P8: Alloy & Perfect Essence (Swap Currencies)
Swap on Rare: remove 1 mod, add 1 guaranteed. Alloys (13) and Perfect Essences (19)
share the `essence_swap` mechanic but have different mod pools. Currently lumped
together under `perfect_essence`. Need separate pools, optimizer actions, price
resolution, and GP seeds. Crystallisation omens (sinistral/dextral) apply to both.
See `docs/design/module-alloy-support.md`.

### P9: Catalysing Exaltation
Bias exalt toward a specific mod tag family. Used on rings/amulets to improve
odds of hitting resistance or attribute mods. Significant probability improvement.
