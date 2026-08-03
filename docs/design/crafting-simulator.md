# Crafting Simulator Design — Sprint 5c

## Key Insight: One Pool, Many Operations

All crafting currencies use the **same `normal` mod pool**. The difference is the
**operation** performed, not a different set of mods. Chaos/Annul/Exalted all draw from
the same pool — the pool just shrinks dynamically based on what's already on the item.

## State Machine Requirements

The simulator must track and model ALL of the following:

### Item State
```
- rarity: Normal | Magic | Rare | Unique
- ilvl: int (determines max tier eligibility)
- item_class: str (e.g. "Boots_int" — determines mod pool)
- prefixes: list[Mod]  (max 3 on Rare, max 1 on Magic)
- suffixes: list[Mod]  (max 3 on Rare, max 1 on Magic)
- fractured: set[int]  (indices of fractured mods — cannot be removed/changed)
- corrupted: bool      (if true, no further crafting possible)
- quality: int         (0-20 normal, 0-23 corrupted)
- sockets: list[Rune|SoulCore]
```

### Mod State
```
- family: str          (e.g. "IncreasedLife" — only one per family allowed)
- affix_type: prefix | suffix
- tier: int            (T1=best)
- req_level: int       (ilvl needed to roll this tier)
- weight: int          (spawn weight / DropChance)
- stat_text: str
- fractured: bool
```

---

## All Crafting Operations

### 1. ADD (Transmute, Aug, Regal, Exalted)
**Input:** item with open affix slots
**Process:**
1. Determine eligible pool: all tiers where `req_level <= ilvl` AND `req_level >= min_mod_level`
2. Remove all families already on the item (mod family blocking)
3. If prefix slots full → remove all prefix-type mods from pool
4. If suffix slots full → remove all suffix-type mods from pool
5. If omen `gentype_only=1` → only prefixes in pool
6. If omen `gentype_only=2` → only suffixes in pool
7. Roll one mod from remaining pool using weighted random (weight = DropChance)
8. Add to item

**Rarity changes:**
- Transmute: Normal → Magic, add 1
- Augment: Magic (1 mod) → add 1 (fills the other affix type)
- Regal: Magic → Rare, add 1
- Exalted: Rare → add 1

### 2. DEL_ADD (Chaos Orb)
**Input:** Rare item with mods
**Process:**
1. **DELETE step:** pick 1 existing mod uniformly at random (1/N chance each)
   - If omen Sinistral Erasure → only pick from prefixes
   - If omen Dextral Erasure → only pick from suffixes
   - If omen Whittling → pick the mod with LOWEST req_level (deterministic)
   - Fractured mods CANNOT be removed (excluded from selection)
2. Remove that mod from item
3. **ADD step:** same as ADD operation above (pool excludes families still on item)
   - min_mod_level applies (Greater=35, Perfect=50)

### 3. DEL (Annulment)
**Input:** Magic or Rare item with mods
**Process:**
1. Pick 1 existing mod uniformly at random (1/N)
   - If omen Sinistral Annulment → only pick from prefixes
   - If omen Dextral Annulment → only pick from suffixes
   - If omen Greater Annulment → remove 2 mods
   - Fractured mods CANNOT be removed
2. Remove that mod from item

### 4. REROLL (Alchemy)
**Input:** Normal (or Magic for PoE2 Alchemy) item
**Process:**
1. Clear all existing mods
2. Add N mods (Alchemy: N=4) using repeated ADD operations
   - Each ADD respects family blocking from previously added mods
   - Slot limits respected (typically fills ~2 prefix + 2 suffix for 4 mods)
   - If omen Sinistral Alchemy → maximize prefix count (3P + 1S)
   - If omen Dextral Alchemy → maximize suffix count (1P + 3S)
3. Item becomes Rare

### 5. FRACTURE (Fracturing Orb)
**Input:** Rare item with ≥4 explicit mods
**Process:**
1. Pick 1 existing mod uniformly at random
2. Mark it as fractured (gold text, permanent)
3. Item becomes a "fractured item"
4. Fractured mod cannot be removed, changed, or divined

### 6. DIVINE (Divine Orb)
**Input:** Magic or Rare item
**Process:**
1. For each non-fractured mod on item:
   - Reroll numeric value within its tier's min-max range
2. Does NOT change tier, does NOT change which mods are present
3. Omen of Blessed → rerolls implicit instead of explicits

### 7. ESSENCE (Greater/Perfect Essence)
**Input:** 
- Greater Essence: Magic item → Rare with guaranteed mod
- Perfect Essence: Rare item → reroll with guaranteed mod
**Process:**
1. Clear non-fractured mods (or specific behavior based on type)
2. Add the essence's guaranteed mod (from `essence` or `perfect_essence` pool)
3. Fill remaining slots from normal pool (same as REROLL but with 1 locked mod)
   - If omen Sinistral Crystallisation → remove only suffix mods (keep prefixes)
   - If omen Dextral Crystallisation → remove only prefix mods (keep suffixes)

### 8. DESECRATION (Abyss Crafting)
**Input:** Rare item + Abyssal Bone currency
**Process:**
1. Bone adds an UNREVEALED desecrated mod to item
2. Take item to Well of Souls → reveals 3 random options from desecrated pool
3. Pick 1 of 3 offered mods
4. Mod is added to item (occupies a suffix slot, separate from normal mods)
   - If omen Sinistral Necromancy → only prefix desecrated mods offered
   - If omen Dextral Necromancy → only suffix desecrated mods offered
   - If omen Abyssal Echoes → can reroll the 3 options once
   - If omen Sovereign/Liege/Blackblooded → guarantees specific lich-type mod

**Bone types:**
- Altered Collarbone: Jewellery (Amulet, Ring, Belt)
- Gnawed Rib (max ilvl 64) / Ancient Rib / Preserved Rib (min 40): Armour
- Gnawed Jawbone (max 64) / Preserved Jawbone / Ancient Jawbone (min 40): Weapons
- Preserved Cranium: Jewels
- Preserved Vertebrae: Waystones

### 9. GENESIS TREE (Breach Crafting)
**Input:** Hiveblood + Wombgift
**Process:**
1. Invest points in Genesis Tree branches to influence outcomes
2. Tree "births" items with modifiers influenced by branch choices
3. Passive skills on tree can:
   - Force maximum prefix/suffix values
   - Block certain mod types (no caster/attack/fire/cold/etc. mods)
   - Guarantee minion or caster mods
   - Target specific attribute combinations

This is a SEPARATE crafting system from currency — more like targeted item generation.

### 10. FLUX ORBS (Elemental Conversion)
**Input:** Item with resistance mods
**Process:**
- Blazing Flux: converts Cold+Lightning resistance → Fire resistance
- Chilling Flux: converts Fire+Lightning resistance → Cold resistance
- Crackling Flux: converts Fire+Cold resistance → Lightning resistance
- Void Flux: converts Fire+Cold+Lightning resistance → Chaos resistance

### 11. CORRUPTION (Vaal Orb)
See crafting-guide-corruption.md for full outcomes.
After corruption, item.corrupted = true, no further crafting possible.

---

## Pool Dynamics — What Gets Excluded

When calculating the available pool for an ADD operation:

```python
available_mods = []
for mod in all_mods_in_pool:
    if mod.req_level > item.ilvl:
        continue  # too high ilvl needed
    if mod.req_level < min_mod_level:
        continue  # below currency minimum (Greater/Perfect)
    if mod.family in [m.family for m in item.current_mods]:
        continue  # family already on item (BLOCKED)
    if mod.affix_type == 'prefix' and len(item.prefixes) >= max_prefixes:
        continue  # prefix slots full
    if mod.affix_type == 'suffix' and len(item.suffixes) >= max_suffixes:
        continue  # suffix slots full
    if omen_gentype_only == 1 and mod.affix_type != 'prefix':
        continue  # omen restricts to prefix
    if omen_gentype_only == 2 and mod.affix_type != 'suffix':
        continue  # omen restricts to suffix
    available_mods.append(mod)

# Roll using weighted random
total_weight = sum(m.weight for m in available_mods)
P(specific_mod) = mod.weight / total_weight
```

---

## Implementation Architecture

```
src/poe2_crafting_mcp/crafting/
├── __init__.py
├── simulator.py      # CraftingSimulator state machine
├── item_state.py     # ItemState dataclass
├── operations.py     # Currency operation logic (add/del/del_add/reroll/etc)
├── calculator.py     # Probability calculator (analytical)
├── monte_carlo.py    # Monte Carlo simulation for complex paths
└── cost_estimator.py # Integrates with live prices for cost comparison
```

### Key Classes

```python
@dataclass
class ModInstance:
    family: str
    affix_type: str  # prefix/suffix
    tier: int
    req_level: int
    weight: int
    stat_text: str
    fractured: bool = False

@dataclass
class ItemState:
    item_class: str
    ilvl: int
    rarity: str  # Normal/Magic/Rare
    mods: list[ModInstance]
    corrupted: bool = False
    
    @property
    def prefixes(self) -> list[ModInstance]: ...
    @property
    def suffixes(self) -> list[ModInstance]: ...
    @property
    def open_prefixes(self) -> int: ...
    @property
    def open_suffixes(self) -> int: ...

class CraftingSimulator:
    def __init__(self, item_class: str, ilvl: int, mod_pool: dict):
        self.item = ItemState(item_class, ilvl, "Normal", [])
        self.pool = mod_pool  # from get_craftable_mods()
    
    def apply(self, currency: str, omen: str = None) -> ItemState:
        """Apply currency, return new item state."""
    
    def probability_of(self, target_family: str, currency: str, 
                       omen: str = None) -> float:
        """P(hitting target) given current state + currency."""
    
    def expected_attempts(self, target: dict, currency: str,
                         omen: str = None) -> float:
        """Expected number of currency uses to hit target."""
    
    def simulate(self, target: dict, method: list[str], 
                 n: int = 10000) -> SimulationResult:
        """Monte Carlo: run n simulations of a multi-step craft."""
```

---

## What We Have vs What We Need to Build

### ✅ Have (data layer complete)
- All mod pools with real weights (poe2db scraper)
- Tier data with req_levels
- Mod families for blocking
- Affix types (prefix/suffix)
- Currency definitions (min_mod_level, operations)
- Essence/desecrated/influence pools
- Omen definitions (gentype_only, reqids)

### ❌ Need to Build
1. `ItemState` dataclass with slot tracking
2. `apply_currency()` operation dispatcher
3. `get_available_pool()` with dynamic exclusions
4. Probability calculator (analytical for single-step)
5. Monte Carlo simulator (for multi-step crafts)
6. Cost estimator (integrates live prices)
7. Method comparison tool
8. MCP tools: `simulate_craft`, `estimate_craft_cost`, `compare_craft_methods`
9. CLI: `poe2-lookup craft-sim` interactive commands
