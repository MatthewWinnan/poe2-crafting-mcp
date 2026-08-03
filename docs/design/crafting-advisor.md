# Crafting Advisor Design (Sprint 5a)

## Key Finding: poe2db Has Real Spawn Weights

The modifier weight data is **embedded directly in the HTML** of poe2db pages as a JSON
blob inside `new ModsView({...})`. No headless browser needed — plain HTTP + parse.

The `DropChance` field is the actual spawn weight used for probability calculations.

Example from Gloves_int base prefix pool:
- `+Life`: DropChance=900 (14.1% of total prefix weight 6370)
- `+Mana`: DropChance=900
- `+ES flat`: DropChance=700
- `%inc ES`: DropChance=700
- `%inc ES + flat Life`: DropChance=600
- `Adds Phys to Attacks`: DropChance=780
- `Adds Fire to Attacks`: DropChance=390

Total prefix weight (Gloves_int): 6370
→ P(hitting +Life prefix) = 900/6370 ≈ 14.1%

## Data Source

URL pattern: `https://poe2db.tw/us/{ItemClass}`

Where ItemClass is:
- Armour: `{Slot}_{attr}` — e.g. `Gloves_int`, `Body_Armours_str_dex`, `Helmets_dex_int`
- Weapons: `One_Hand_Swords`, `Bows`, `Crossbows`, `Daggers`, etc.
- Jewellery: `Amulets`, `Rings`, `Belts`
- Off-hand: `Shields_str`, `Bucklers`, `Foci`, `Quivers`
- Jewels: `Ruby`, `Emerald`, `Sapphire`, `Diamond`
- Flasks: `Life_Flasks`, `Mana_Flasks`
- Charms: `Charms`

## Mapping: PoB Base → poe2db Item Class

PoB bases have `tags` like `['default', 'armour', 'int_armour', 'gloves']`.
The key tag is the attribute tag (e.g. `int_armour`) which maps to the poe2db suffix.

Mapping:
- `int_armour` → `_int`
- `str_armour` → `_str`
- `dex_armour` → `_dex`
- `str_dex_armour` → `_str_dex`
- `str_int_armour` → `_str_int`
- `dex_int_armour` → `_dex_int`
- `str_dex_int_armour` → `_str_dex_int`
- No armour tag → just the slot name

Slot name mapping (PoB slot → poe2db):
- `Gloves` → `Gloves`
- `Boots` → `Boots`
- `Helmet` → `Helmets`
- `Body Armour` → `Body_Armours`
- `Shield` → `Shields`
- `Focus` → `Foci`
- `Buckler` → `Bucklers` (no attr variant)
- `Bow` → `Bows`
- `One Hand Sword` → `One_Hand_Swords`
- `Ring` → `Rings`
- `Amulet` → `Amulets`
- `Belt` → `Belts`
- etc.

Items with the SAME tag share the same mod pool. Gold Gloves and Adorned Gloves
both have `int_armour` → both use `Gloves_int` mod pool.

## Data Structure in poe2db HTML

The JSON is inside: `new ModsView({...})`

Key fields:
```json
{
  "baseitem": {"href": "Gloves", "tags": "Int", ...},
  "config": { "normal": {...}, "marksman": {...}, "decay": {...}, ... },
  "opt": {"tags": "int_armour", "ItemClassesCode": "Gloves"},
  "normal": [  // <-- THIS is the base mod pool
    {
      "Name": "of the Mongoose",
      "Level": "1",           // ilvl required
      "ModGenerationTypeID": "2",  // 1=prefix, 2=suffix
      "ModFamilyList": ["Dexterity"],
      "DropChance": "1000",   // <-- THE REAL WEIGHT
      "Code": "IncreasedDexterity1___",
      "ModTypeID": "...",
      "str": "<html stat text>",
      "reqlvl": 9,
      "TagsList": [...],
      "WeightList": [...]
    },
    ...
  ],
  "marksman": [...],  // Kolr's Hunt influence mods
  "decay": [...],     // Katla's Gloom influence mods
  "essence": [...],   // Essence-guaranteed mods
  "desecrated": [...], // Abyss desecrated mods
  ...
}
```

ModGenerationTypeID: 1=Prefix, 2=Suffix

## Architecture

### Scraping Strategy: Pull All at Once + Cache

Reason: ~50 item classes total, each page is ~500KB HTML. One-time seed takes ~3min
with rate limiting. Data changes only on game patches (every few months).

### DB Schema

```sql
CREATE TABLE mod_weights (
    item_class   TEXT NOT NULL,     -- poe2db slug: "Gloves_int", "Amulets"
    pool         TEXT NOT NULL,     -- "normal", "marksman", "decay", "essence", etc.
    mod_code     TEXT NOT NULL,     -- PoB mod ID: "IncreasedDexterity1___"
    affix_type   TEXT NOT NULL,     -- "prefix" or "suffix"
    mod_family   TEXT NOT NULL,     -- "Dexterity", "LocalIncreasedEnergyShield"
    stat_text    TEXT NOT NULL,     -- cleaned stat text
    weight       INTEGER NOT NULL,  -- DropChance value (spawn weight)
    req_level    INTEGER NOT NULL,  -- minimum ilvl to roll
    tags         TEXT NOT NULL DEFAULT '[]',  -- JSON array of mod tags
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (item_class, pool, mod_code)
);
CREATE INDEX idx_mod_weights_class_pool ON mod_weights(item_class, pool);
CREATE INDEX idx_mod_weights_family ON mod_weights(mod_family);
```

### Query Flow

```
User asks: "what mods can roll on Gold Gloves at ilvl 82?"

1. PoBDatabase.search_bases("Gold Gloves") → tags=['default','armour','int_armour','gloves']
2. Map int_armour + Gloves → item_class = "Gloves_int"
3. SELECT * FROM mod_weights WHERE item_class='Gloves_int' AND pool='normal' AND req_level <= 82
4. Group by affix_type, sort by weight desc
5. Calculate: P(mod) = weight / sum(all weights in same affix_type at this ilvl)
```

### CLI

```bash
poe2-lookup "Gold Gloves" --craftable              # all mods, ilvl 100
poe2-lookup "Gold Gloves" --craftable --ilvl 82    # filtered by ilvl
poe2-lookup "Gold Gloves" --craftable --prefix     # prefixes only
poe2-lookup "Gold Gloves" --craftable --suffix     # suffixes only
poe2-lookup "Gold Gloves" --craftable --pool marksman  # Kolr's Hunt mods
```

### MCP Tool

```python
@mcp.tool()
def get_craftable_mods(base_name: str, ilvl: int = 100, pool: str = "normal") -> str:
    """Get all mods that can roll on a base item with spawn weights and probabilities."""
```

### Seeding

```bash
poe2-lookup mod-pool-seed              # fetch all item classes from poe2db
poe2-lookup mod-pool-seed --class Gloves_int  # single class
poe2-lookup mod-pool-status            # show freshness
```

## Implementation Order

1. `poe2db_client.py` — scraper that fetches + parses the ModsView JSON
2. DB schema + `mod_weights` table in price_db.py
3. `get_craftable_mods()` in database.py or price_db.py
4. CLI: `--craftable` flag on base lookup
5. MCP tool
6. Seed command: `poe2-lookup mod-pool-seed`
7. Status command: `poe2-lookup mod-pool-status`

## Crafting Methods (for cost estimation later)

The ModsView JS already encodes crafting rules:
- Transmute: Normal → Magic, adds 1 mod from "normal" pool
- Augment: Magic (1 mod) → adds 1 mod from "normal" pool (opposite affix type)
- Regal: Magic → Rare, adds 1 mod
- Alchemy: Normal → Rare with 4 mods
- Chaos: Rare → reroll 4 mods from "normal" pool
- Exalted: Rare → add 1 mod
- Essence: guarantees 1 mod from "essence" pool + fills rest from "normal"
- Influence mods: separate pools (marksman, decay, chronomancy, etc.)
