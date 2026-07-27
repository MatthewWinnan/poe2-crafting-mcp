# Crafting Simulator Design — Sprint 5c

## Key Insight: One Pool, Many Operations

All crafting currencies use the **same `normal` mod pool**. The difference is the
**operation** performed, not a different set of mods. Chaos/Annul/Exalted all draw from
the same pool — the pool just shrinks dynamically based on what's already on the item.

## Currency Operations (from poe2db ModsView JS)

| Currency | Operation | Effect | Pool | Min Mod Lv |
|----------|-----------|--------|------|------------|
| Transmutation | `add` × 1 | Normal → Magic (1 mod) | normal | 0 |
| Greater Transmutation | `add` × 1 | Normal → Magic (1 mod) | normal | 44 |
| Perfect Transmutation | `add` × 1 | Normal → Magic (1 mod) | normal | 70 |
| Augmentation | `add` × 1 | Magic → Magic (add 1 mod) | normal | 0 |
| Greater Augmentation | `add` × 1 | Magic → add 1 | normal | 44 |
| Perfect Augmentation | `add` × 1 | Magic → add 1 | normal | 70 |
| Regal Orb | `add` × 1 | Magic → Rare (add 1 mod) | normal | 0 |
| Greater Regal | `add` × 1 | Magic → Rare (add 1) | normal | 35 |
| Perfect Regal | `add` × 1 | Magic → Rare (add 1) | normal | 50 |
| Alchemy | `reroll` × 4 | Normal → Rare (4 mods) | normal | 0 |
| Chaos Orb | `del_add` × 1 | Remove 1, add 1 | normal | 0 |
| Greater Chaos | `del_add` × 1 | Remove 1, add 1 | normal | 35 |
| Perfect Chaos | `del_add` × 1 | Remove 1, add 1 | normal | 50 |
| Exalted Orb | `add` × 1 | Rare → add 1 mod | normal | 0 |
| Greater Exalted | `add` × 1 | Rare → add 1 | normal | 35 |
| Perfect Exalted | `add` × 1 | Rare → add 1 | normal | 50 |
| Annulment | `del` × 1 | Remove 1 random mod | - | - |
| Divine Orb | `divine` | Reroll values within tier | - | - |
| Fracturing Orb | `fracture` | Lock 1 random mod | - | - |

### Desecration (Abyss) Currencies
| Currency | Operation | Pool | Min Mod Lv | Item Classes |
|----------|-----------|------|------------|--------------|
| Altered Collarbone | `add` × 1 | normal + desecrated | 0 | Amulet, Ring, Belt |
| Ancient Collarbone | `add` × 1 | normal + desecrated | 40 | Amulet, Ring, Belt |
| Gnawed Rib | `add` × 1 | normal + desecrated | max 64 | Armour |
| Ancient Rib | `add` × 1 | normal + desecrated | 0 | Armour |
| Preserved Rib | `add` × 1 | normal + desecrated | 40 | Armour |

### Essences
| Currency | Operation | Pool | Notes |
|----------|-----------|------|-------|
| Greater Essence | add guaranteed | essence | Magic item, guarantees one essence mod |
| Perfect Essence | add guaranteed | perfect_essence | Rare item, stronger guaranteed mod |

## Omens (Meta-crafting Modifiers)

Omens modify how the NEXT currency works. Key property: `gentype_only`:
- `gentype_only: 1` = only adds/removes PREFIXES
- `gentype_only: 2` = only adds/removes SUFFIXES

| Omen | Modifies | Effect |
|------|----------|--------|
| Sinistral Alchemy | Alchemy | Maximize prefix count |
| Dextral Alchemy | Alchemy | Maximize suffix count |
| Sinistral Coronation | Regal | Add only prefix |
| Dextral Coronation | Regal | Add only suffix |
| Sinistral Exaltation | Exalted | Add only prefix |
| Dextral Exaltation | Exalted | Add only suffix |
| Greater Exaltation | Exalted | Add TWO mods (disabled in calc) |
| Sinistral Annulment | Annulment | Remove only prefix |
| Dextral Annulment | Annulment | Remove only suffix |
| Greater Annulment | Annulment | Remove TWO mods (disabled) |
| Sinistral Erasure | Chaos | Remove only prefix |
| Dextral Erasure | Chaos | Remove only suffix |
| Whittling | Chaos | Remove lowest level mod (disabled) |
| Corruption | Vaal Orb | Remove "no change" outcome |
| Blessed | Divine | Reroll implicits instead |
| Sanctification | Divine | Sanctify item (disabled) |

## Pool Dynamics (Critical for Simulator)

When rolling a mod to add, the available pool is filtered by:
1. **Item level** — `req_level <= ilvl`
2. **Currency tier** — `req_level >= min_mod_level` (Greater/Perfect)
3. **Affix type** — if omen restricts to prefix/suffix only
4. **Mod family blocking** — families already on the item are EXCLUDED
5. **Affix slot limit** — if prefixes are full (3), only suffixes can be added
6. **Pool source** — `beforePools` (normally just "normal", desecrated adds both)

### The Simulator Must Track:
- Current item state: list of mods (family, affix_type, tier)
- Available prefix/suffix slots
- Fractured mods (cannot be removed)
- What operation the currency performs
- Dynamic pool after exclusions

## What We Have vs What We Need

### ✅ Already Have
- Mod weights per item class (from poe2db)
- All tiers with individual weights and req_levels
- Mod families (for blocking)
- Affix type (prefix/suffix)
- Greater/Perfect min_mod_level filtering
- Separate pools (normal, essence, desecrated, influence)

### ❌ Missing / Need to Build

1. **Crafting Simulator Engine** — state machine that models:
   - Item state (current mods, slots used, fractured flags)
   - Apply currency operation (add/del/del_add/reroll/fracture/divine)
   - Calculate probability of desired outcome given current state
   - Monte Carlo simulation for complex multi-step crafts

2. **Omen Integration** — modifies next operation:
   - gentype_only filtering (prefix/suffix targeting)
   - Special behaviors (Greater Exalt = add 2, Greater Annul = remove 2)

3. **Cost Estimation** — given a target outcome:
   - Expected number of attempts
   - Cost per attempt (currency price from live economy)
   - Total expected cost
   - Compare across methods (alt spam vs essence vs chaos spam vs trade)

4. **Generation Weights** — the poe2db page mentions "Generation weights now taken into account"
   in Craft of Exile beta. These might be separate from DropChance. Need to verify if our
   DropChance values already include generation weights or if there's additional data.

5. **Crafting Bench Mods** — veiled/master crafts (not urgent, bench is limited in PoE2)

## Weight Comparison: poe2db vs Craft of Exile

Both sources derive weights empirically (not from game files):
- **poe2db**: DropChance field in ModsView JSON (source unclear, likely community data)
- **Craft of Exile**: Recombinator-based + trade site parsing (Prohibited Library Discord)

They may not be identical but should be in the same ballpark. For our purposes, poe2db
is sufficient — it's the same data Craft of Exile would show, just potentially with
different normalization.

## Implementation Plan

### Phase 1: Simulator Core (MVP)
```python
class CraftingSimulator:
    def __init__(self, item_class: str, ilvl: int):
        self.item_class = item_class
        self.ilvl = ilvl
        self.mods = []  # current mods on item
        self.fractured = set()  # indices of fractured mods
        self.rarity = "Normal"
        self.pool = self._load_pool()

    def apply_currency(self, currency: str, omen: str = None) -> dict:
        """Apply a currency to the item, return result."""

    def get_probability(self, target_mod_family: str, currency: str, omen: str = None) -> float:
        """Calculate probability of hitting target mod with given currency."""

    def estimate_cost(self, target: dict, method: str) -> dict:
        """Estimate expected cost to achieve target using method."""

    def simulate(self, target: dict, method: str, n: int = 10000) -> dict:
        """Monte Carlo simulation for complex crafts."""
```

### Phase 2: Method Comparison
- For a given target (e.g., "T1 %inc ES on int gloves"), compare:
  - Alt spam → aug → regal path
  - Greater transmute spam
  - Perfect transmute spam
  - Essence guaranteed + fill
  - Buy on trade (live price)
- Return ranked list by expected cost

### Phase 3: Multi-step Crafting Plans
- "Get T1 ES + T1 Life on gloves" requires multi-step planning:
  1. Alt spam for first mod
  2. Aug/Regal for second
  3. Annul if bad mod added
  4. Exalt remaining slots
- Simulator handles conditional branching

### Phase 4: Omen-Optimized Paths
- Factor in omen cost + benefit
- "Is it worth using Omen of Sinistral Exaltation to guarantee a prefix?"
