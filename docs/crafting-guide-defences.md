# PoE2 Defence Guide: Layered Defences

Source: mobalytics.gg (paraphrased for compliance with licensing restrictions)

## Defence Philosophy: The Onion Model

Incoming damage passes through layers in order:
1. **Avoidance** — can you dodge/block it entirely?
2. **Mitigation** — how much damage is reduced?
3. **HP** — do you have enough life/ES to survive?
4. **Recovery** — can you heal back what you lost?
5. **Damage** — can you kill enemies before they kill you?

## Layer 1: Avoidance

### Primary Avoidance
- **Evasion Rating** (DEX armour) — % chance to avoid attacks
- **Block** (Shields) — passive + active (Raise Shield)
- **Movement Speed** (Boots) — get out of the way
- **Dodge Roll** (player skill) — manual i-frames

### Ailment Prevention
- Ailment/Stun Threshold
- Charms (auto-activate when ailment applied)
- Limited immunity sources (Dream Fragments, Chaos Inoculation)

### Important Note
Evasion doesn't work against: certain boss abilities (slams), DoT effects.
Acrobatics keystone makes Evasion work against ALL hits but still not DoT.

## Layer 2: Mitigation

### Physical Mitigation
- **Armour** (STR gear) — reduces physical hit damage
- **Deflection** — flat minimum 40% reduction when triggered
- **Taken As** — physical damage taken as elemental (e.g., Cloak of Flame)
- **Flat reduced damage taken** — from specific gear/passives

### Elemental & Chaos Mitigation
- **Resistances** — higher = less damage taken. Max is normally 75%.
- **Maximum Resistance** increases (gear, passives, soul cores)
- **"% of Armour also applies to Elemental Damage"** — scales armour for ele hits

### Conditional Mitigation
- Less damage taken modifiers
- Reduced enemy crit damage bonus
- Specific ascendancy mechanics (Wind Ward, Grasping Wounds, etc.)

## Layer 3: HP Pool

### Life
- Flat +Life from gear and passives
- % increased Maximum Life (limited on tree)
- Strength gives life

### Energy Shield
- From INT gear
- Acts as extra buffer above life
- Recharges after not taking damage

### Mana (Mind Over Matter)
- Can convert mana into pseudo-life pool

## Layer 4: Recovery

### Active Recovery (requires action)
- Life Leech / Life Gained on Hit
- Life/Mana Flasks
- Recoup (% of damage taken recovered over time)

### Passive Recovery (automatic)
- Life Regeneration (flat or % per second)
- Mana Regeneration
- Energy Shield Recharge (starts after delay)

## Attribute → Defence Type Mapping

| Attribute | Defence | Gear Examples |
|-----------|---------|---------------|
| STR | Armour | str_armour bases |
| DEX | Evasion | dex_armour bases |
| INT | Energy Shield | int_armour bases |
| STR/DEX | Armour + Evasion | str_dex_armour bases |
| STR/INT | Armour + ES | str_int_armour bases |
| DEX/INT | Evasion + ES | dex_int_armour bases |

## Practical Priorities by Slot

- **Body Armour**: Life, primary defence (AR/EV/ES), resistances
- **Helmet**: Life, resistances, defence
- **Gloves**: Life, resistances, attack/cast speed, damage
- **Boots**: Movement Speed (most important), life, resistances
- **Belt**: Life, resistances, charm slots
- **Rings**: Resistances, attributes, life, damage stats
- **Amulet**: Attributes, crit, damage, life
- **Shield**: Block chance, life, resistances, defence
