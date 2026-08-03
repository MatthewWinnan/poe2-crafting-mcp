# Crafting Pipeline Design

> Module card for Sprint 5a–5c: `get_craftable_mods`, real weights, crafting methods

---

## 1. `get_craftable_mods` — function design

### 1.1 Signature

```python
def get_craftable_mods(
    base_name: str,
    ilvl: int,
    slot: str = "",
    include_tiers: bool = True,
    include_weights: bool = True,
    category: str = "Item",
) -> CraftableModPool
```

Also exposed as MCP tool:

```
get_craftable_mods(base_name, ilvl, slot?, include_tiers?, include_weights?)
→ CraftableModPool (JSON-serialisable dict)
```

And CLI:

```
poe2-lookup craftable <base_name> [--ilvl N] [--slot SLOT]
```

---

### 1.2 Algorithm

```
1. Look up base in item_bases WHERE name LIKE ? (fuzzy, pick closest)
   → base_tags: list[str]   e.g. ['dex_int_armour', 'armour', 'body_armour', 'default']
   → base_slot: str         e.g. 'Body Armour'
   → base_req_level: int

2. Determine item_type_tags = [t for t in base_tags if t != 'default']
   These are the discriminating tags used for mod filtering.

3. Query item_mods WHERE category = 'Item' AND req_level <= ilvl
   (broad SQL, then Python post-filter)

4. For each mod row:
   a. Parse weight_keys / weight_vals as lists
   b. Check eligibility:
      - If weight_keys is empty → eligible (universal mod)
      - Elif any item_type_tag is in weight_keys with weight > 0 → eligible
      - Elif 'default' in weight_keys with weight > 0 → eligible
      - Else → skip
   c. Collect eligible group_names

5. For each eligible group_name, expand all tiers via expand_mod_tiers()
   → ordered by req_level DESC (T1 = highest req_level within group)
   → filter tiers to req_level <= ilvl

6. Separate into prefixes and suffixes by mod_type field

7. For each group, assign tier labels T1, T2, T3... counting from highest req_level

8. Build and return CraftableModPool
```

---

### 1.3 Return type: `CraftableModPool`

```python
@dataclass
class ModTier:
    tier: int              # 1 = best (highest req_level), counting up
    tier_label: str        # e.g. "T1", "T2", "Unassailable"
    req_level: int         # ilvl required for this tier to roll
    stat_text: str         # e.g. "(92-100)% increased Energy Shield"
    stat_min: float        # lower bound of value range
    stat_max: float        # upper bound of value range (= stat_min if flat)
    weight: int            # 0/1 from DB (or real weight if ETL upgraded)
    weight_is_real: bool   # True if sourced from RePoE, False if binary from PoB

@dataclass
class CraftableMod:
    group_name: str        # e.g. "LocalEnergyShieldPercent"
    mod_type: str          # "prefix" | "suffix"
    stat_text_top: str     # stat_text of best eligible tier (for display)
    tiers: list[ModTier]   # all eligible tiers sorted T1 → Tn
    tags: list[str]        # weight_keys that grant this mod (minus 'default')
    total_weight: int      # sum of weights across tiers (for pool ratio estimate)

@dataclass
class CraftableModPool:
    base_name: str
    base_tags: list[str]
    slot: str
    ilvl: int
    prefixes: list[CraftableMod]   # max 3 can be on an item
    suffixes: list[CraftableMod]   # max 3 can be on an item
    prefix_count: int              # len(prefixes)
    suffix_count: int              # len(suffixes)
    weights_are_real: bool         # True if any mod has real weights
    # Probability estimates (only meaningful with real weights)
    prefix_pool_size: int          # sum of all prefix weights
    suffix_pool_size: int          # sum of all suffix weights
    note: str                      # "weights are binary (PoB data) — probabilities approximate"
```

JSON shape for MCP:

```json
{
  "base_name": "Sleek Jacket",
  "base_tags": ["dex_int_armour", "armour", "body_armour", "default"],
  "slot": "Body Armour",
  "ilvl": 80,
  "prefix_count": 6,
  "suffix_count": 4,
  "weights_are_real": false,
  "note": "weights are binary (PoB data only) — per-mod probabilities approximate",
  "prefixes": [
    {
      "group_name": "LocalEnergyShieldPercent",
      "mod_type": "prefix",
      "stat_text_top": "(92-100)% increased Energy Shield",
      "total_weight": 1,
      "tags": ["dex_int_armour"],
      "tiers": [
        {"tier": 1, "tier_label": "Unassailable", "req_level": 75, "stat_text": "(92-100)% ...", "stat_min": 92, "stat_max": 100, "weight": 1, "weight_is_real": false},
        {"tier": 2, "tier_label": "Unbreakable",  "req_level": 60, "stat_text": "(80-91)% ...",  "stat_min": 80, "stat_max": 91,  "weight": 1, "weight_is_real": false}
      ]
    }
  ],
  "suffixes": [ ... ]
}
```

---

### 1.4 CLI output

```
$ poe2-lookup craftable "Sleek Jacket" --ilvl 80

Base: Sleek Jacket  |  Tags: dex_int_armour, body_armour  |  ilvl: 80
Weights: binary (PoB data) — pool ratios are estimates only

── PREFIXES (6 groups) ──────────────────────────────────────────────────────
Group                    T1 (ilvl 75)              T2 (ilvl 60)         ...
LocalEnergyShieldPerc    (92-100)% inc ES          (80-91)% inc ES
LocalEnergyShield        +(130-150) ES flat        ...
...

── SUFFIXES (4 groups) ──────────────────────────────────────────────────────
...
```

---

## 2. Real mod weights — acquisition plan

### 2.1 Problem

PoB stores only binary eligibility in `item_mods.weight_keys/weight_vals` (`0` or `1`).
Real crafting probability requires actual pool weights like:

```
LocalEnergyShieldPercent  dex_int_armour  →  500
LocalEnergyShield         dex_int_armour  →  1000
FireResistance            default         →  2000
```

These determine P(rolling mod X) = weight_X / Σ(all eligible weights).

### 2.2 Best source: RePoE (PoE2 fork)

- **Repo**: `brather/RePoE` (has active PoE2 branch) or `lvlvllvlvllvlvl/RePoE2`
- **File**: `data/mods.min.json` — keyed by mod id, contains `spawn_weights`
- **Format**:
  ```json
  "LocalEnergyShieldPercent3": {
    "spawn_weights": [
      {"tag": "dex_int_armour", "weight": 500},
      {"tag": "default",        "weight": 0}
    ],
    "generation_type": "prefix",
    "required_level": 75,
    ...
  }
  ```
- **Coverage**: all spawnble mods including essences, breach, abyss desecrated
- **Lag**: usually updated within 1-2 patches

**Alternative**: Game `.dat64` files via `PyPoE` → slower to parse, requires game install.

### 2.3 ETL integration plan

**New ETL step** (`etl.py: _load_repoe_weights`):

```python
def _load_repoe_weights(conn, repoe_mods_path: str):
    """
    Load real spawn weights from RePoE mods.min.json into item_mods.
    Updates weight_vals in-place; also stores raw weights in new mod_weights table.
    """
```

**New table `mod_weights`** (add to schema.sql):

```sql
CREATE TABLE IF NOT EXISTS mod_weights (
    mod_key        TEXT NOT NULL,   -- RePoE mod key e.g. "LocalEnergyShieldPercent3"
    tag            TEXT NOT NULL,   -- spawn weight tag
    weight         INTEGER NOT NULL,
    source         TEXT DEFAULT 'repoe',
    PRIMARY KEY (mod_key, tag)
);
```

**Matching strategy** (PoB group_name ↔ RePoE key):

1. PoB `group_name` = `LocalEnergyShieldPercent`, RePoE key = `LocalEnergyShieldPercent3`
   → strip trailing digit(s) from RePoE key, then match to PoB group_name
2. Match on `stat_text` as fallback if group_name mapping fails
3. Unmatched mods: keep binary weight=1, set `weight_is_real=False`

**ETL flag**: run `python -m poe2_crafting_mcp.data.etl --weights-only` to refresh weights
without rebuilding the full DB (fast, ~5s).

**DB column addition**: `ALTER TABLE item_mods ADD COLUMN weight_is_real INTEGER DEFAULT 0;`
Or: just store raw weights in `mod_weights` and JOIN at query time.

### 2.4 Weight data shape in `get_craftable_mods`

Until RePoE integration is complete, use equal-weight approximation:

```python
# Binary weight estimate: each eligible mod gets weight=1 within group
# Pool ratio = 1 / prefix_count for each prefix
weight = 1 if binary else repoe_weight
```

After integration:

```python
weight = mod_weights[group_name][tag]  # from mod_weights table JOIN
weight_is_real = True
```

---

## 3. PoE2 crafting methods — complete catalogue

### 3.1 Base currency operations

| Currency | Requires | Effect | Mod count result |
|---|---|---|---|
| Orb of Transmutation | Normal (white) | → Magic (blue), 1-2 mods | 1–2 |
| Orb of Augmentation | Magic, 1 mod | Adds 1 mod | 2 |
| Orb of Alteration | Magic | Rerolls all mods | 1–2 |
| Regal Orb | Magic, 2 mods | → Rare, adds 1 prefix or suffix | 3 |
| Orb of Alchemy | Normal | → Rare, 4 mods | 4 |
| Chaos Orb | Rare | Rerolls all mods | 4 (3-6) |
| Exalted Orb | Rare, <6 mods | Adds 1 mod | n+1 |
| Divine Orb | Any magic/rare/unique | Rerolls values within tier ranges | same tiers |
| Orb of Annulment | Magic or Rare | Removes 1 mod randomly | n-1 |
| Vaal Orb | Any | Corrupts — see §3.6 | varies |

### 3.2 Crafting method models

#### Alteration spam → Regal

Goal: hit 1 target modifier (prefix or suffix) on magic item.

```
P(hit) = weight[target] / Σ(all prefix weights)   # if target is a prefix
Expected alts = 1 / P(hit)
Expected cost = expected_alts × price(Orb of Alteration)
              + 1 × price(Regal Orb)
              + optional bench craft for last affix
```

Model struct:

```python
@dataclass
class AltRegalPlan:
    target_mod: str          # group_name
    p_hit_per_alt: float     # weight[target] / pool_size
    expected_alts: float     # 1 / p_hit_per_alt
    chaos_cost: float        # expected_alts * alt_price_in_chaos + regal_price
    method: str = "alt_regal"
```

#### Chaos spam

Goal: hit ≥2 target modifiers (e.g. T1 ES + T1 resist) on rare item.

```
If targets are independent (different groups):
  P(hit both) = P(prefix mod in pool) × P(suffix mod in pool)
  But these are NOT independent — chaos rolls 3–6 mods from pool.
  Better model: hypergeometric / Monte Carlo simulation.

Approximate: P = P(mod_A is in 3 prefix rolls) × P(mod_B is in 3 suffix rolls)
           = (1 - (1 - pA)^3) × (1 - (1 - pB)^3)
  where pA = weight[A] / prefix_pool_size
        pB = weight[B] / suffix_pool_size

Expected chaos = 1 / P(hit both)
```

Model struct:

```python
@dataclass
class ChaosSpamPlan:
    target_mods: list[str]     # group_names of all target mods
    p_hit: float               # combined probability
    expected_chaos: float      # 1 / p_hit
    chaos_cost: float          # expected_chaos * chaos_orb_price_in_chaos (=1)
    method: str = "chaos_spam"
```

#### Essence craft

Essences guarantee one specific mod. Remaining slots are chaos-random.

```
P(desired fill | essence guarantee) =
  P(get remaining target mods on the chaos-filled slots)

For each essence type → guaranteed_mod_group (look up essence_to_mod table)
```

**Essence → mod mapping** (needs static table, not in DB yet):

```python
ESSENCE_TO_MOD: dict[str, dict[str, str]] = {
    "Essence of Torment": {
        "Gloves":      "LocalAttackSpeed",
        "Body Armour": "LocalEnergyShield",
        ...
    },
    "Essence of Anger": {
        "Gloves":      "FireResistance",
        ...
    },
    # ... all essences × all slots
}
```

This table must be sourced from poedb.tw or game files (not in PoB data).

Model struct:

```python
@dataclass
class EssencePlan:
    essence_name: str
    guaranteed_mod: str       # group_name guaranteed by this essence
    remaining_targets: list[str]
    p_fill: float             # P(remaining targets fill correctly)
    expected_tries: float     # 1 / p_fill
    chaos_cost: float         # expected_tries * essence_price + optional divine
    method: str = "essence"
```

#### Fracture + craft

Buy a fractured base with T1 of one mod pre-locked. Fill remaining 5 affixes.

```
Fractured mod is immovable.
Remaining = 3 prefixes - 1 (fractured), 3 suffixes.
Cost = price(fractured base) + fill cost (alts or essences for remaining targets)
```

Model struct:

```python
@dataclass
class FracturePlan:
    fractured_mod: str        # group_name of the fractured mod
    fractured_base_cost: float  # from trade API estimate
    remaining_targets: list[str]
    fill_plan: AltRegalPlan | ChaosSpamPlan | EssencePlan
    total_chaos_cost: float
    method: str = "fracture_craft"
```

#### Exalt slam

Add a random mod to an item with <6 affixes.

```
P(hit target) = weight[target] / Σ(eligible mods for current open prefix/suffix slot)
  where eligible = mods not already on item (group exclusion)

Annulment removes 1 random mod with P = 1/(current mod count)
```

#### Divine reroll

Rerolls values within current tier ranges (does NOT change which tier).

```
For each rerolled mod:
  new_value ~ Uniform(stat_min[tier], stat_max[tier])
  P(new ≥ threshold) = (stat_max - threshold) / (stat_max - stat_min)
```

---

### 3.3 Special crafting: Runes

- Runes socket into weapon/armour rune slots (separate from prefix/suffix system)
- Each rune grants a specific bonus (e.g. Iron Rune = +flat armour)
- No randomness: choosing a rune is deterministic
- Model: rune_effects[rune_name] → {stat, value} — static lookup table (not in DB yet)
- Slots: weapons/armour can have 0–4 rune sockets depending on base

### 3.4 Special crafting: Corruption (Vaal Orb)

Outcomes (roughly equal probability):
1. **Nothing** (~25%)
2. **Corrupt implicit** — adds or replaces an implicit mod (~25%)
3. **Reroll mods** like a chaos orb (~25%)
4. **Transform to unique** (very rare, ~few%)
5. **Add gem sockets** (item type dependent)

Cannot be undone. Cannot apply further crafting currencies.

Model struct:

```python
@dataclass
class CorruptionOutcome:
    p_nothing: float       # ~0.25
    p_implicit: float      # ~0.25
    p_chaos_reroll: float  # ~0.25
    p_unique: float        # ~0.01
    p_socket: float        # ~0.24 (remainder)
    possible_implicits: list[str]  # from corruption_mods table (tagged 'corrupted')
```

### 3.5 Special crafting: Abyss Jewels → Desecrated mods

Desecrated mods come from Abyss Jewels socketed into Bone Sockets on items.
Tagged `kurgal_mod`, `ulaman_mod`, etc. in weight_keys.

```
Desecrated mod tags: kurgal_mod, ulaman_mod, abyssal_jewel, ...
Source: searching item_mods WHERE weight_keys contains any desecrated tag
Roll: determined by the Abyss Jewel type + ilvl of the jewel, not the base item
```

### 3.6 Special crafting: Essence-socketed items (Breach)

Breach splinters → Breachstones → items with Breach mods.
Tagged with breach-related tags in weight_keys.

---

## 4. `estimate_craft_cost` design (Sprint 5c)

```python
def estimate_craft_cost(
    base_name: str,
    target_mods: list[str],     # group_names or keywords
    ilvl: int,
    method: str = "auto",       # "auto"|"alt_regal"|"chaos"|"essence"|"fracture"
    budget_chaos: float = 0,    # 0 = no limit
) -> CraftCostEstimate
```

```python
@dataclass
class CraftCostEstimate:
    method: str
    target_mods: list[str]
    p_success: float
    expected_tries: float
    expected_cost_chaos: float
    expected_cost_divine: float   # = expected_cost_chaos / divine_rate
    breakdown: dict               # per-currency counts
    alternatives: list["CraftCostEstimate"]  # other methods ranked by cost
    note: str
```

**Auto-selection logic**:

```
1 target mod  → alt_regal is cheapest if pool not tiny
2+ target mods → essence if an essence guarantees one, then compare chaos
Fractured base available on trade cheaper than expected fill cost → fracture
```

---

## 5. Data gaps and dependency order

| Gap | Blocks | Source | ETL effort |
|---|---|---|---|
| Real mod weights (RePoE) | Accurate probability math | RePoE PoE2 fork JSON | Medium (2-3h) |
| Essence → mod mapping | EssencePlan | poedb.tw or game files | Medium (manual table) |
| Rune effects table | Rune modelling | wiki / game files | Small |
| Corruption implicit pool | CorruptionOutcome | item_mods `corrupted` tag | Already in DB |
| Bench craft mod pool | BenchCraftPlan | PoB bench data (CraftingBench.lua) | Medium |

### Implementation order

```
Sprint 5a: get_craftable_mods + CLI (binary weights, no probability)
  → unblocks agent mod lookup immediately

Sprint 5b: RePoE weight ETL
  → enables accurate P(hit) estimates

Sprint 5c: estimate_craft_cost
  → requires: get_craftable_mods + weights + live prices
  → start with alt_regal and chaos_spam models (simplest)
  → add essence + fracture after essence table is sourced
```

---

## 6. MCP tool stubs

```python
@mcp.tool()
def get_craftable_mods(
    base_name: str,
    ilvl: int,
    slot: str = "",
) -> dict:
    """
    Return all modifiers that can roll on a specific item base at a given ilvl.
    Groups mods into prefixes/suffixes with all tiers and value ranges.
    Includes per-mod pool weights (binary from PoB until RePoE ETL is run).
    """

@mcp.tool()
def estimate_craft_cost(
    base_name: str,
    target_mods: list[str],
    ilvl: int,
    method: str = "auto",
) -> dict:
    """
    Estimate the expected currency cost to craft target mods onto a base item.
    Returns best method recommendation + cost breakdown per currency.
    Requires get_craftable_mods data + live currency prices (refresh_prices first).
    """
```
