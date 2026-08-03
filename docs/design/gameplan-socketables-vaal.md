# Implementation Gameplan: Socketables, Vaal Orbs & Terminal Value

## Blockers Before Optimizer (in priority order)

### 1. Socketable Effect Data (scraping + DB)

**Goal:** Know what each rune/soul core/idol does on each slot type.

**Data source:** poe2db.tw/us/Rune, poe2db.tw/us/Soul_Core, or scrape from game8 tables.

**Schema:**
```sql
CREATE TABLE socketable_effects (
    name        TEXT NOT NULL,     -- "Greater Body Rune", "Soul Core of Tacati"
    category    TEXT NOT NULL,     -- "rune", "soul_core", "idol"
    tier        TEXT,              -- "Lesser", "Normal", "Greater" (runes only)
    slot_type   TEXT NOT NULL,     -- "Martial Weapon", "Wand or Staff", "Armour", etc.
    stat_text   TEXT NOT NULL,     -- "+45 to maximum Life"
    PRIMARY KEY (name, slot_type)
);
```

**Implementation:**
- Add scraper to `poe2db_client.py` (or hardcode from game8 tables since the list is finite ~100 items)
- Add to `seed-all` step
- Query via `get_socketable_effect(name, item_slot) → stat_text`

### 2. Vaal Orb Corruption System (refine simulator)

**Confirmed outcomes for non-unique equipment (from poe2wiki):**
1. **No change** — just adds corrupted tag (~25%)
2. **Reroll up to 3 mods** — changes existing mods to new ones (~25%)
3. **Add Vaal enchantment** — special corruption-only enchantment mod (~25%)
4. **Add socket** — ignores socket limits (weapons + armour only) (~25%)
   - For jewellery: this outcome = "no change" instead (Omen of Corruption doesn't remove it!)

**For unique equipment:**
1. No change
2. Modifier magnitude multiplier (0.78x-1.22x) — like a divine
3. Vaal enchantment
4. Add socket (or no change for jewellery)

**Key rules:**
- All outcomes "seem to be equally likely" per wiki
- Omen of Corruption removes the explicit "No change" outcome (but NOT the pseudo no-change for jewellery sockets)
- Architect's Orb: 50% chance to add second corruption enchantment, 50% destroy item
- Socket limit: item cannot have more sockets than inventory space it occupies (1x1=1, 1x2=2, 2x2=4, etc.)

**Corruption enchantment pool:**
- Separate pool per item class + ilvl (like mod_weights)
- Already on poe2db: `https://poe2db.tw/us/Gloves_str#ModifiersCalc` has `corrupted` and `corruption_upgrade` pools
- We already have `mod_weights WHERE pool='corrupted'` — need to verify

**Implementation:**
- Update `apply_currency("vaal")` with proper outcome weights
- Add `corruption_enchantment` field to ItemState
- Support Omen of Corruption (remove "no change" outcome)
- Add Architect's Orb currency (50/50 second enchantment or destroy)

### 3. PoB Integration for Socketables

**Goal:** Export item with socketables in PoB-readable format.

**PoB item text format includes:**
```
Rarity: Rare
Gold Gloves
Satin Gloves
Quality: 20
Sockets: Greater Body Rune, Soul Core of Tacati
LevelReq: 82
Prefix: {IncreasedLife T1} +(85-99) to maximum Life
...
```

**Implementation:**
- Add `item_state_to_pob_text(item: ItemState) → str` converter
- Include socketable effects as stats in the item text
- Wire into `PoBEngine.equip_item()` flow

### 4. Effect-Based Valuation (optimizer terminal value)

**Formula:**
```
socket_value = sum(
    get_socketable_effect(socket_name, item_slot).dps_value
    for socket_name in item.sockets if socket_name
)

quality_value = base_stat * (quality / 100)

terminal_value = socket_value + quality_value
terminal_cost = (artificer_price × sockets_needed) + (quality_currency × 4) + sum(socketable_prices)
```

**Implementation:**
- After optimizer finds best mod strategy, add terminal value/cost to final evaluation
- Compare total (crafting_cost + terminal_cost) vs trade price

---

## Implementation Order

```
Phase A: Data (can be done now)
  A1. Check mod_weights for corrupted/corruption_upgrade pools ✓ (already have)
  A2. Scrape/hardcode socketable effects into new DB table
  A3. Add to seed-all

Phase B: Simulator refinements
  B1. Refine Vaal Orb outcomes (proper 4-way, enchantment pool, jewellery edge case)
  B2. Add corruption_enchantment to ItemState
  B3. Omen of Corruption integration (remove no-change outcome)
  B4. Architect's Orb (50/50 second enchant or destroy)

Phase C: Integration
  C1. item_state_to_pob_text() converter with socketable effects
  C2. Terminal value function (socket_value + quality_value)
  C3. Wire into optimizer fitness evaluation

Phase D: CLI enhancements
  D1. 'socketables' command — show available runes/cores/idols with effects for this slot
  D2. 'corrupt' command — interactive, shows outcome
  D3. 'architect' command — 50/50 gamble
```

## What's NOT blocking the optimizer

The optimizer doesn't need socketables or Vaal Orbs to function. These are
terminal steps that add known value AFTER the optimizer finds the best mod
strategy. The optimizer can run with:

- `terminal_socket_value = socket_count × avg_rune_value` (from prices, no effects needed)
- `terminal_quality_value = known_base_multiplier × 0.20`
- `terminal_corruption_ev = 0` (assume no corruption for first pass)

So technically we CAN start the optimizer now and add these refinements later.
The question is whether you want the full system modeled first for accuracy,
or the optimizer running with approximate terminal values.

## Recommendation

Start the optimizer with approximate terminal values NOW. Implement the
socketable/Vaal refinements in parallel or as a follow-up. The optimizer's
core job is finding the best MOD strategy — sockets and corruption are
independent terminal steps that don't change which currency sequence is optimal.
