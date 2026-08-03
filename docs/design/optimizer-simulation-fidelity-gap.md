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
| lesser/normal/greater essence | ✅ | ✅ | Magic→Rare + 1 guaranteed |
| perfect essence | ✅ | ✅ | Swap mechanic |
| artificer (sockets) | ✅ | ❌ | Terminal step — not needed |
| armourer's scrap / whetstone | ✅ | ❌ | Terminal step — not needed |
| architect (double corrupt) | ✅ | ❌ | Terminal step — not needed |

### Mod Pools: DB Has 17, Optimizer Uses 2

| Pool | DB Entries | In Optimizer | What It Is |
|------|-----------|--------------|------------|
| **normal** | 8,580 | ✅ | Standard crafting pool |
| **desecrated** | 694 | ✅ (simplified) | Abyss/Well of Souls mods |
| **essence** | 1,935 | ❌ | Essence-specific guaranteed mods |
| **perfect_essence** | 516 | ❌ | Perfect essence swap mods |
| **corrupted** | 576 | ❌ | Vaal Orb corruption pool |
| **corruption_upgrade** | 935 | ❌ | Architect's Orb pool |
| **bonded** | 3,907 | ❌ | Rune-bonded mods (Aldur's Legacy) |
| **socketable** | 4,971 | ❌ | Rune/Soul Core socket effects |
| **chronomancy** | 102 | ❌ | Chronomancy rune pool (Boots) |
| **destruction** | 162 | ❌ | Destruction rune pool (Weapons) |
| **decay** | 138 | ❌ | Decay rune pool (Gloves) — Kolr's Hunt |
| **marksman** | 168 | ❌ | Marksman rune pool (Gloves) — Kolr's Hunt |
| **berserking** | 180 | ❌ | Berserking rune pool (Helmets) |
| **breach_caster** | 89 | ❌ | Breach Ring caster mods |
| **breach_minion** | 74 | ❌ | Breach Ring minion mods |
| **breach_otherworldly** | 36 | ❌ | Breach amulet/belt/ring otherworldly |
| **soul** | 147 | ❌ | Soul Core effects |

### The Rune Pool Gap (Critical for 0.5 League)

In Runes of Aldur (0.5), players can apply **Rune Alloys** that add mods from
faction-specific pools. These are SEPARATE mod pools that provide unique stats
not available in the normal pool:

- **Decay** (Gloves): Ignite/Bleed/Poison magnitude — builds needing ailment scaling
- **Marksman** (Gloves): Projectile Damage — bow/crossbow/wand builds
- **Destruction** (Weapons): Explicit modifier magnitudes — endgame scaling
- **Chronomancy** (Boots): Skill Effect Duration — DoT/channel builds
- **Berserking** (Helmets): Maximum Rage, Warcry Damage — melee builds
- **Bonded** (Body Armour): Rune-specific bonded mods (Aldur's Legacy extraction)

These occupy the SAME "crafted modifier" slot as essences/alloys. A player
chooses between:
- Essence (guaranteed stat from essence pool)
- Alloy (guaranteed stat from rune faction pool)

The optimizer currently always uses `ESSENCE_UPGRADE` which targets from the
normal pool families. It should also be able to target from these faction pools.

### Omens: Craft Sim vs Optimizer

| Omen | Craft Sim | Optimizer | Effect |
|------|-----------|-----------|--------|
| Sinistral/Dextral Exaltation | ✅ | ✅ | Force prefix/suffix |
| Greater Exaltation | ✅ | ✅ (enum, not modeled) | Add 2 mods |
| Sinistral/Dextral Annulment | ✅ | ✅ | Remove prefix/suffix |
| Sinistral/Dextral Coronation | ✅ | ✅ | Regal targets side |
| Whittling | ✅ | ✅ (approximated) | Remove lowest-req mod |
| Abyssal Echoes | ✅ | ✅ (enum only) | Re-roll reveal options |
| Sinistral/Dextral Necromancy | ✅ | ❌ | Desecration targets side |
| Corruption | ✅ | ❌ | Remove "nothing" Vaal outcome |
| Sanctification | ✅ | ❌ | Remove negative Vaal outcomes |
| Light | ✅ | ❌ | Annul targets desecrated mod only |
| Catalysing Exaltation | ✅ | ❌ | Bias exalt toward catalyst tag |
| Homogenising Exaltation | ✅ | ❌ | Exalt matching type cluster |

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
| desecrated state | ✅ | ✅ (flag) | |
| divined state | N/A | ✅ (flag) | Pre-fracture step |
| mod values (numeric) | ✅ | ❌ | Only families/tiers tracked |
| implicits | ✅ | ❌ | Corruption only |
| reforge stock | ✅ | ❌ | Simplified to flat cost |

---

## Priority Gaps to Close

### P0: Sub-Goal Decomposition (Path A from shortcomings doc)
The biggest impact for hard crafts. Independent of simulation fidelity.

### P1: Rune/Alloy Pools
Add faction pool support so `ESSENCE_UPGRADE` can target from decay/marksman/etc.
The data is already in the DB. Need: pool parameter on the action, preflight
to encode multiple pools, Rust to select from the right pool based on action.

### P2: Essence Pool (not normal pool)
Currently `add_specific_mod` picks from the normal pool. Real essences guarantee
a mod from the ESSENCE pool (different weights/tiers). Should query `pool='essence'`
for the guaranteed mod.

### P3: Greater Exaltation Omen
Adds 2 mods in one exalt. Potentially very powerful for multi-target crafts
(2× chance per attempt). Currently enum-only, not modeled in Rust actions.

### P4: Omen of Light
Annul ONLY the desecrated mod. Allows retry of desecration without affecting
normal mods. Critical for targeting specific abyss mods.

### P5: Catalysing Exaltation
Bias exalt toward a specific mod tag family. Used on rings/amulets to improve
odds of hitting resistance or attribute mods. Significant probability improvement.
