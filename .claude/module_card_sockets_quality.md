# Module Card: Sockets, Quality & Socketables

## Overview

Items in PoE2 have Augment Sockets that hold Runes, Soul Cores, and Idols.
These add stats/effects to the item. Socket count is part of the item's total
power and must be represented in ItemState for PoB evaluation, price checking,
and the optimizer's terminal value calculation.

## Socket Mechanics

### Max Sockets per Slot

| Slot | Max Sockets |
|------|-------------|
| Weapon (2H) | 2 |
| Body Armour | 2 |
| Helmet | 1 |
| Gloves | 1 |
| Boots | 1 |
| **Total per character** | **7** |

One-handed weapons: need confirmation (likely 1 each = 2 total with dual wield).
Shields/Focus/Quiver: need confirmation (likely 0-1).

### How to Add Sockets

1. **Artificer's Orb** — adds or improves a socket. Each use = 1 socket attempt.
   - Not guaranteed to add? Or always adds? (need to confirm — game8 says "adds")
   - Made from 10 Artificer's Shards (auto-combine)
2. **Vaal Orb** — one possible corruption outcome is adding a socket beyond normal max
3. **Architect's Orb** — another corruption orb from Vaal Temple, can add socket

### Socket Types

All sockets accept the same socketable items (Runes, Soul Cores, Idols).
There's no socket colour/linking system like PoE1.

## Socketable Items

Three categories, all from our existing DB:

### 1. Runes (3 tiers: Lesser / Normal / Greater)

Give slot-dependent bonuses. Examples:
- Body Rune on Armour: +45 Life | on Weapon: Leeches 4% Phys as Life
- Desert Rune on Armour: +14% Fire Res | on Weapon: Adds 7-11 Fire Dmg
- Iron Rune on Armour: 20% inc Defences | on Weapon: 20% inc Phys Dmg

Runes have different effects based on item category:
- Martial Weapon
- Wand or Staff (Caster Weapon)
- Armour (all armour pieces)
- All Equipment (some runes like attribute runes)

### 2. Soul Cores

Unique socketables with powerful build-specific effects:
- Soul Core of Tacati on Armour: +11% Chaos Resistance
- Soul Core of Topotante on Weapon: Penetrate 15% Ele Res
- Citaqualotl's Soul Core of Foulness on Weapon: Adds 19-29 Chaos Dmg

Slot-restricted (only work in specific slots like Helmets, Boots, etc.)

### 3. Idols

Mostly for Helmets, Gloves, Body Armour, and Sceptres:
- Bear Idol on Helmet: 8% increased AoE
- Fox Idol on Body Armour: +2% to Quality of all Skills
- Idol of Maxarius on Body Armour: +1 Charm Slot (Limit: 1)

Some have "Limit: 1" — only one per character.

## Quality System

### Quality Currencies

| Currency | Applies To | Effect |
|----------|-----------|--------|
| Armourer's Scrap | Armour | +5% quality (increases base defences) |
| Blacksmith's Whetstone | Weapon | +5% quality (increases base damage) |
| Glassblower's Bauble | Flask | +5% quality (increases flask effect) |
| Gemcutter's Prism | Gem | +5% quality (varies by gem) |

- Max quality: 20% (normal), 23% (via lucky Vaal corruption)
- Quality = percentage increase to base stats (armour/evasion/ES for armour, pdps for weapons)
- Always applied (4 uses to reach 20%) — cost = 4 × currency price

### How Quality Affects Value

For armour: `effective_base = base_stat × (1 + quality/100)`
For weapons: `effective_damage = base_damage × (1 + quality/100)`

This is a flat multiplier on the base, calculated before % increases from mods.

## Data Model (ItemState additions)

```python
@dataclass
class ItemState:
    # ... existing fields ...
    quality: int = 0                           # 0-20 (23 max corrupted)
    sockets: list[str] = field(default_factory=list)  # socketable item names
    max_sockets: int = 0                       # determined by slot type

    @property
    def open_sockets(self) -> int:
        return max(0, self.max_sockets - len(self.sockets))
```

### Socket slot determination

```python
MAX_SOCKETS_BY_SLOT = {
    "Body Armour": 2,
    "Bow": 2, "Crossbow": 2, "Two Hand Sword": 2, "Two Hand Axe": 2,
    "Two Hand Mace": 2, "Quarterstaff": 2, "Staff": 2, "Talisman": 2,
    "Helmet": 1, "Gloves": 1, "Boots": 1,
    "One Hand Sword": 1, "One Hand Axe": 1, "One Hand Mace": 1,
    "Dagger": 1, "Claw": 1, "Flail": 1, "Spear": 1,
    "Wand": 1, "Sceptre": 1, "Focus": 1,
    "Shield": 1, "Buckler": 1,
    "Ring": 0, "Amulet": 0, "Belt": 0, "Quiver": 0,
}
```

## Integration

### For PoB DPS evaluation
- Export socketables as part of item text (PoB reads them)
- Quality affects base stats in the calculation

### For price checking
- Socket count and contents affect item value
- "3-socket body armour" is worth more than "1-socket body armour"

### For the optimizer's terminal value
- Socket value = sum of (best rune/core for build × socket count)
- Quality value = base_stat_increase × quality percentage
- Artificer cost = N × artificer_price to reach max sockets

### For the CLI sim
- `socket <rune_name>` command to place a socketable
- `unsocket` to remove
- `artificer` to add a socket
- `quality` to apply quality currency

## Questions to Confirm

1. **Jewellery sockets?** — Rings/Amulets/Belts appear to have 0 sockets.
   Confirm they can't be socketed at all.
2. **One-handed socket count** — Is it 1 per one-hander? Can dual-wield
   give 2 weapon sockets total?
3. **Artificer's Orb** — Is it always +1 socket, or can it fail?
   Game8 says "adds" without mentioning failure. Assume deterministic.
4. **Socket effects and slot** — Do all rune effects depend on the item
   being "Armour" vs "Weapon" or on the specific slot (Helmet vs Boots)?
   From the data: most runes say "Armour" (all armour pieces get same bonus)
   but Soul Cores are slot-specific (e.g. "Boots: +1% Max Lightning Res").
5. **Socketable data in DB** — Do we have rune/soul core effects in our
   item_descriptions or concepts tables? Or do we need to scrape them?
