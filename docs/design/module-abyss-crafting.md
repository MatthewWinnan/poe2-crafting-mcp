# Module Card: Abyss Crafting (Desecration System)

## Overview

Abyss crafting is a **choice-based reveal system** that differs fundamentally
from regular currency crafting. Instead of rolling a random mod from a pool,
the player applies a bone → reveals 3 options at the Well of Souls → picks one.

This gives the player **agency** in the outcome, making it probabilistically
superior to blind exalting from the same pool. The optimizer must model this
as a conditional probability (P of target appearing in N revealed options).

## Mechanics (from Mobalytics abyss-crafting guide + poe2db)

### Step-by-Step Flow

```
1. APPLY BONE to Rare item
   ├─ If item has < 6 mods → adds desecrated slot (prefix or suffix based on open slots)
   │   ├─ Both open → random prefix or suffix
   │   ├─ Only prefix open → desecrated prefix
   │   └─ Only suffix open → desecrated suffix
   └─ If item has 6 mods → removes 1 random mod, adds desecrated slot (same affix type)
   
2. Item now has "Unrevealed Desecrated Modifier" (hidden)
   - Item cannot be desecrated again (one desecrated mod per item)
   - Item can still be crafted with other currency before revealing

3. REVEAL at Well of Souls
   ├─ Shown 3 random options from desecrated pool (weighted)
   ├─ With Omen of Abyssal Echoes: can reroll → 6 total options (pick from either set)
   └─ Player picks 1 option → mod placed on item

4. Result: item has a revealed desecrated mod (occupies normal prefix/suffix slot)
   - Can be removed with Annulment (Omen of Light targets only desecrated mods)
   - After removal, item can be desecrated again
```

### Bone Types

| Bone | Applies To | Quality Variants |
|------|-----------|-----------------|
| **Jawbone** | Weapon or Quiver | Gnawed (≤ilvl 64), Preserved (any ilvl), Ancient (min_lv 40) |
| **Rib** | Armour (Helmet, Gloves, Boots, Body Armour) | Gnawed (≤ilvl 64), Preserved (any ilvl), Ancient (min_lv 40) |
| **Collarbone** | Amulet, Ring, Belt | Gnawed (≤ilvl 64), Preserved (any ilvl), Ancient (min_lv 40) |
| **Cranium** | Jewels | (single quality) |
| **Vertebrae** | Waystones | (single quality) |

Quality determines the ilvl constraint and mod pool filtering:
- **Gnawed**: max ilvl 64 on the item, draws from full pool up to that ilvl
- **Preserved**: no ilvl restriction, draws from full pool
- **Ancient**: no max ilvl, but guarantees minimum modifier level 40 (filters low tiers)

### Faction Tags (Lich Omens)

Every desecrated mod belongs to exactly one faction (or none for jewels):
- `amanamu_mod` — 235 mods total (Omen of the Liege guarantees this pool)
- `kurgal_mod` — 223 mods total (Omen of the Blackblooded guarantees this pool)
- `ulaman_mod` — 228 mods total (Omen of the Sovereign guarantees this pool)
- No faction — 8 mods (jewels only, via Cranium)

When a lich omen is active, the reveal draws ONLY from that faction's mods.
This dramatically narrows the pool and increases target hit rate.

### Abyss Omens (affect desecration/reveal)

| Omen | Effect on Desecration |
|------|----------------------|
| Sinistral Necromancy | Desecration adds only prefix |
| Dextral Necromancy | Desecration adds only suffix |
| Omen of Light | Next annulment removes only desecrated mods |
| Abyssal Echoes | Reveal gives reroll (6 choices instead of 3) |
| Putrefaction | Replace ALL mods with up to 6 desecrated + corrupts item |
| Blackblooded | Reveal draws only from Kurgal pool |
| Liege | Reveal draws only from Amanamu pool |
| Sovereign | Reveal draws only from Ulaman pool |

### Essence of the Abyss

Special interaction: replaces a random mod with "Mark of the Abyssal Lord".
When desecrating an item with this mark, the mark is always removed and the
desecrated mod that replaces it will be of higher tier than the removed mod.
This provides deterministic removal targeting (similar to how slot-forcing works).

## Data We Have

```sql
-- Full desecrated pool with weights and faction tags
SELECT * FROM mod_weights WHERE pool='desecrated' AND item_class='Bows';
-- 694 total mods across 54 item classes
-- Each mod has tags array with faction: amanamu_mod, kurgal_mod, or ulaman_mod
-- weight=1 for all desecrated mods (equal weighting within pool)
```

All weights are 1 (equal probability among eligible mods in the pool).
This simplifies the math: P(target) = 1 / pool_size for each draw.

## Simulator Model

### New Operation: `desecrate`

```python
CURRENCIES["desecrate"] = {
    "op": "desecrate",
    "from_rarity": ["Rare"],
    "min_lv": 0,  # overridden by bone quality (Ancient=40)
}
```

### Key Difference from Other Currencies

Regular currencies: `apply_currency() → random outcome`
Desecration: `apply_bone() → reveal(N=3) → player_chooses(target)`

The simulator doesn't randomly place a mod. Instead, it calculates:
- P(target in N draws from pool without replacement)
- Expected cost = bone_price / P(success)

For the optimizer's MC simulation, we model it as:
1. Draw N mods from eligible pool (N=3 normally, N=6 with Echoes)
2. If target_family is among the N draws → SUCCESS (pick it)
3. If not → FAIL (bone wasted, try again or switch strategy)

### Pool Filtering for Desecration

```python
def get_desecration_pool(
    item_class: str,
    ilvl: int,
    affix_type: str,           # "prefix" or "suffix" (determined by item state)
    min_mod_level: int = 0,    # 0 for Preserved, 40 for Ancient
    faction: str = "",         # "" for all, "amanamu"/"kurgal"/"ulaman" for lich omens
    blocked_families: set = set(),  # families already on item
) -> list[dict]:
    """Get eligible desecrated mods for reveal."""
    query = """
        SELECT * FROM mod_weights
        WHERE pool = 'desecrated'
          AND item_class = ?
          AND affix_type = ?
          AND req_level <= ?
          AND req_level >= ?
    """
    # Filter by faction tag if lich omen active
    # Filter out blocked families (family blocking still applies)
    # All weights are 1 → uniform distribution
```

### Probability Calculation

Since all desecrated mods have weight=1 (uniform):

```
pool_size = len(eligible_mods)  # after family blocking + affix type + faction filter
P(target in 1 draw) = 1 / pool_size
P(target NOT in N draws) = C(pool_size - 1, N) / C(pool_size, N)
                         = product((pool_size - i) for i in range(1, N+1)) / product((pool_size - i + 1) for i in range(1, N+1))
                         # simplified for small N:
P(miss all 3) = ((pool_size - 1) / pool_size) * ((pool_size - 2) / (pool_size - 1)) * ((pool_size - 3) / (pool_size - 2))
              = (pool_size - 3) / pool_size  # for N=3 without replacement

P(hit in 3) = 1 - (pool_size - 3) / pool_size = 3 / pool_size
P(hit in 6) = 1 - (pool_size - 6) / pool_size = 6 / pool_size  # with Echoes
```

Wait — that's only for a single target family. If target has multiple tiers:

```
target_count = number of eligible mods matching target family
P(hit in N) = 1 - C(pool_size - target_count, N) / C(pool_size, N)
```

For typical pools:
- Bows desecrated suffix pool: ~9 mods (after affix filter)
- With Kurgal omen: ~3 mods (just that faction's suffixes)
- P(target in 3 from 9) = 1 - C(8,3)/C(9,3) = 1 - 56/84 = 33%
- P(target in 3 from 3) = 100% (lich omen guarantees if only 3 options!)

### ItemState Changes

```python
@dataclass
class ItemState:
    # ... existing fields ...
    desecrated: bool = False        # has an unrevealed desecrated mod
    desecrated_affix: str = ""      # "prefix" or "suffix" (which slot is reserved)
    desecrated_revealed: bool = False  # has been revealed (mod is concrete)
```

### Simulator Methods

```python
class CraftingSimulator:
    def apply_bone(
        self,
        bone_quality: str = "preserved",  # "gnawed", "preserved", "ancient"
        omens: list[str] = [],
    ) -> ItemState:
        """Apply abyssal bone. Adds unrevealed desecrated slot."""
        
    def reveal_desecrated(
        self,
        target_family: str = "",
        omens: list[str] = [],
    ) -> tuple[bool, ModInstance | None]:
        """Simulate reveal at Well of Souls.
        
        Returns (success, mod) where success=True if target was among options.
        In MC simulation: draws N options, checks if target present.
        """
        
    def get_desecration_probability(
        self,
        target_family: str,
        affix_type: str,
        faction: str = "",
        min_mod_level: int = 0,
        echoes: bool = False,
    ) -> float:
        """Analytical P(target appears in reveal options)."""
```

## File Layout

```
src/poe2_crafting_mcp/crafting/
  desecration.py      # Desecration engine (apply_bone, reveal, probability)
  simulator.py        # Add desecrate ops, integrate with existing state machine
```

## Integration with Optimizer

The GP rule-list can include desecration actions:

```
IF open_suffix AND missing_target_suffix AND target_is_desecrated
  THEN desecrate(bone="preserved", faction="kurgal", target="ColdResistancePenetration")
```

The fitness evaluation computes:
- cost_per_attempt = bone_price + omen_price (if using lich/echoes omen)
- P(success) = analytical from pool size
- expected_cost = cost_per_attempt / P(success)
- If P(success) = 0 (target not in pool) → action is invalid, skip

## Interaction with Essence of the Abyss

The Essence of the Abyss provides deterministic removal targeting:
1. Use Essence of Abyss → replaces a random mod with "Mark of the Abyssal Lord"
2. Apply bone → Mark is always removed, desecrated mod takes its slot
3. Revealed desecrated mod is guaranteed to be higher tier than the removed mark

This means you can control WHICH mod gets replaced by first marking it.
For the optimizer: this is a 2-step action (essence + bone) that provides
both targeted removal AND a desecrated mod in one sequence.

## Open Questions

1. **Does family blocking apply to desecrated reveal?** — Likely yes (can't
   get a mod of a family already on item). Need to confirm.
2. **Can you desecrate + reveal before finishing other crafting?** — Yes per
   the guide ("Item can still be crafted with other currency before revealing").
   This means strategic ordering: desecrate early, craft other slots, reveal last.
3. **Putrefaction omen**: replaces ALL mods with up to 6 desecrated + corrupts.
   Is each of the 6 revealed independently? Or is it one big reveal of 6?
   Likely 6 independent reveals (each gets 3 options). Very complex to model.
4. **Pool weighting**: poe2db shows weight=1 for all desecrated mods. Is this
   truly uniform, or does the scraper not capture different weights? The equal
   weight makes the 3-choice mechanic give ~uniform odds across all options.

## Reveal as Branching Decision Node

The reveal is NOT a binary hit/miss — it's a full branching point because
the specific mod chosen affects all future crafting decisions (family blocking,
slot counts, annul targets). The MC simulation must:

1. Draw N mods from pool (N=3, or N=6 with Echoes)
2. If target is among them → pick target (deterministic best choice)
3. If target is NOT among them → pick "least damaging" option:
   - Prefer mod whose family doesn't block future targets
   - Prefer affix type easier to annul later (opposite side from targets)
   - Prefer lowest req_level (easier to Whittling-remove)
   
The optimizer can evolve the miss-case heuristic, but the simulator must
place the actual concrete mod so downstream item state is correct.

```python
def simulate_desecration(item, pool, target_family, N=3):
    drawn = random.sample(pool, min(N, len(pool)))
    
    # Hit case
    hits = [m for m in drawn if m.family == target_family]
    if hits:
        return hits[0], True
    
    # Miss case: pick least-damaging from the drawn options
    best = pick_least_damaging(drawn, item, future_targets)
    return best, False  # miss, but concrete mod placed on item
```

## CLI: Interactive Crafting Mode

The CLI exposes desecration as an interactive step where the user sees the
revealed options and chooses — matching how the game works. This allows
manual testing against known crafting guides (e.g. Craft of Exile paths).

### CLI Flow: `poe2-craft sim`

```
$ poe2-craft sim "Gold Gloves" --ilvl 82

Item: Gold Gloves (Rare, ilvl 82)
Mods: (empty)

> transmute
Item: Gold Gloves (Magic, ilvl 82)
  prefix T3 | IncreasedLife | +(30-39) to maximum Life

> greater_essence IncreasedEnergyShield
Item: Gold Gloves (Rare, ilvl 82)
  prefix T1 | IncreasedEnergyShield | (68-79)% increased Energy Shield [ESSENCE]
  suffix T2 | FireResistance | +(21-25)% to Fire Resistance
  prefix T4 | IncreasedMana | +(45-54) to maximum Mana
  suffix T5 | Dexterity | +(13-16) to Dexterity

> desecrate --bone preserved
Applying Preserved Rib to Gold Gloves...
Item has open suffix — desecrating as suffix.

Revealed options (pick 1-3):
  [1] suffix | SpiritReservation | (5-10)% increased Spirit Reservation Efficiency  [amanamu]
  [2] suffix | CritMultiplier    | (25-34)% increased Critical Damage Bonus         [kurgal]
  [3] suffix | LifeRecoup        | (15-20)% of Damage taken Recouped as Life        [ulaman]

Pick (1-3, or 'r' to reroll with Echoes omen): 2

Item: Gold Gloves (Rare, ilvl 82)
  prefix T1 | IncreasedEnergyShield | (68-79)% increased Energy Shield [ESSENCE]
  suffix T2 | FireResistance | +(21-25)% to Fire Resistance
  prefix T4 | IncreasedMana | +(45-54) to maximum Mana
  suffix T5 | Dexterity | +(13-16) to Dexterity
  suffix T1 | CritMultiplier | (25-34)% increased Critical Damage Bonus [DESECRATED]

> exalted --omens sinistral_exaltation
...

> save my_gloves.json
Saved item state to my_gloves.json

> quit
```

### Key CLI Features:

1. **Interactive reveal**: shows 3 (or 6) options, user picks
2. **Item state persistence**: `save`/`load` commands to serialize item state as JSON
3. **Feed back in**: `poe2-craft sim --load my_gloves.json` to continue from saved state
4. **Omen stacking**: `--omens sinistral_exaltation,greater_exaltation`
5. **Seed control**: `--seed 42` for reproducible simulations
6. **History**: shows all operations performed (for comparing with Craft of Exile)

### Item State JSON Format:

```json
{
  "item_class": "Gloves_int",
  "base_name": "Gold Gloves",
  "ilvl": 82,
  "rarity": "Rare",
  "mods": [
    {"family": "IncreasedEnergyShield", "affix_type": "prefix", "tier": 1,
     "req_level": 72, "stat_text": "(68-79)% increased Energy Shield",
     "fractured": false, "desecrated": false},
    ...
  ],
  "corrupted": false,
  "essence_mod_family": "IncreasedEnergyShield",
  "desecrated_mod_family": "CritMultiplier",
  "history": [
    {"step": 1, "action": "transmute", "omens": []},
    {"step": 2, "action": "greater_essence", "essence_family": "IncreasedEnergyShield"},
    {"step": 3, "action": "desecrate", "bone": "preserved", "revealed": [...], "chose": 2},
    {"step": 4, "action": "exalted", "omens": ["sinistral_exaltation"]}
  ]
}
```

This lets us:
- Replay crafting sequences for verification
- Compare against known Craft of Exile strategies
- Feed saved states into the optimizer for "mid-craft entry" optimization
- Share crafting plans as reproducible JSON files
