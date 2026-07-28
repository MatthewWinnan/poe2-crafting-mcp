"""
Item state to/from PoB text converter.

Converts between our ItemState and Path of Building's raw item text format,
including mods, quality, sockets/socketable effects, and corruption.

PoB format:
    Rarity: Rare
    <item name>
    <base type>
    --------
    <properties: Evasion Rating, Armour, etc.>
    --------
    Requirements:
    Level: <N>
    --------
    Item Level: <N>
    --------
    <implicit mods>        <- between separators (if any)
    --------
    <explicit mods>        <- last section
    --------
    Corrupted              <- if corrupted
"""

from __future__ import annotations

from poe2_crafting_mcp.crafting.simulator import ItemState, ModInstance


# Map item_class prefixes to base type display names
_ITEM_CLASS_TO_BASE_DISPLAY: dict[str, str] = {
    "Gloves_int": "Gold Gloves",
    "Gloves_str": "Titan Gauntlets",
    "Gloves_dex": "Bound Bracers",
    "Gloves_str_dex": "Iron Gloves",
    "Gloves_str_int": "Zealot Gloves",
    "Gloves_dex_int": "Occult Gloves",
    "Bows": "Recurve Bow",
    "Crossbows": "Siege Crossbow",
    "Staves": "Coiled Staff",
    "Wands": "Opal Wand",
    "Sceptres": "Shrine Sceptre",
    "Daggers": "Kris",
    "Rings": "Gold Ring",
    "Amulets": "Gold Amulet",
    "Belts": "Heavy Belt",
}


def item_state_to_pob_text(
    item: ItemState,
    base_name: str = "",
    item_name: str = "",
    db_path: str = "data/poe2_craft.db",
) -> str:
    """Convert an ItemState to PoB raw item text format."""
    lines: list[str] = []
    sep = "--------"

    base_display = base_name or _ITEM_CLASS_TO_BASE_DISPLAY.get(item.item_class, item.item_class)

    # Header
    lines.append(f"Rarity: {item.rarity}")
    if item.rarity in ("Rare", "Unique"):
        lines.append(item_name or "Crafted Item")
    lines.append(base_display)
    lines.append(sep)

    # Properties
    if item.quality > 0:
        lines.append(f"Quality: +{item.quality}%")
    lines.append(sep)

    # Requirements
    lines.append("Requirements:")
    lines.append(f"Level: {item.ilvl}")
    lines.append(sep)

    # Item Level
    lines.append(f"Item Level: {item.ilvl}")
    lines.append(sep)

    # Implicits (corruption implicits)
    if item.implicits:
        for imp in item.implicits:
            lines.append(imp.stat_text)
        lines.append(sep)

    # Explicit mods
    for mod in item.mods:
        lines.append(mod.stat_text)

    # Socketable effects (appended as stats PoB can read)
    socketed_items = [s for s in item.sockets if s]
    if socketed_items:
        from poe2_crafting_mcp.crafting.socketables import get_socketable_effect_for_item
        for socket_name in socketed_items:
            family_key = socket_name.replace(" ", "").replace("'", "")
            effect = get_socketable_effect_for_item(db_path, item.item_class, family_key)
            if not effect:
                for prefix in ("Lesser", "Greater"):
                    if family_key.startswith(prefix):
                        effect = get_socketable_effect_for_item(
                            db_path, item.item_class, family_key[len(prefix):]
                        )
                        if effect:
                            break
            if effect:
                lines.append(effect.stat_text)

    lines.append(sep)

    # Corrupted
    if item.corrupted:
        lines.append("Corrupted")

    return "\n".join(lines)


def pob_text_to_item_state(
    text: str,
    item_class: str = "",
) -> tuple[ItemState, str, str]:
    """Parse PoB text format into an ItemState.

    Returns: (ItemState, base_name, item_name)
    """
    lines = [l.strip() for l in text.strip().split("\n")]
    sep = "--------"

    # Split into sections by separator
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line == sep:
            if current:
                sections.append(current)
            current = []
        else:
            current.append(line)
    if current:
        sections.append(current)

    # Section 0: Rarity + name + base
    rarity = "Rare"
    item_name = ""
    base_name = ""
    if sections:
        header = sections[0]
        for line in header:
            if line.startswith("Rarity:"):
                rarity = line.split(":", 1)[1].strip()
            elif not item_name and rarity in ("Rare", "Unique"):
                item_name = line
            elif not base_name:
                base_name = line

    # If rarity is Normal/Magic, first non-Rarity line is base_name
    if rarity in ("Normal", "Magic") and not base_name and item_name:
        base_name = item_name
        item_name = ""

    # Find Item Level
    ilvl = 82
    for section in sections:
        for line in section:
            if line.startswith("Item Level:"):
                try:
                    ilvl = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

    # Find Quality
    quality = 0
    for section in sections:
        for line in section:
            if line.startswith("Quality:"):
                try:
                    quality = int(line.split(":", 1)[1].strip().replace("+", "").replace("%", ""))
                except ValueError:
                    pass

    # Check corrupted
    corrupted = any(l == "Corrupted" for l in lines)

    # Find mod sections (everything after "Item Level:" section)
    mod_sections: list[list[str]] = []
    found_ilvl = False
    for section in sections:
        if any(l.startswith("Item Level:") for l in section):
            found_ilvl = True
            continue
        if found_ilvl:
            if section == ["Corrupted"]:
                continue
            mod_sections.append(section)

    implicits: list[ModInstance] = []
    explicits: list[ModInstance] = []

    if len(mod_sections) >= 2:
        # First mod section = implicits, last = explicits
        for stat in mod_sections[0]:
            implicits.append(ModInstance(
                family=_guess_family(stat),
                affix_type="implicit",
                tier=1, req_level=1, weight=1,
                stat_text=stat,
            ))
        for stat in mod_sections[-1]:
            explicits.append(ModInstance(
                family=_guess_family(stat),
                affix_type="prefix",  # can't determine without DB
                tier=1, req_level=1, weight=1,
                stat_text=stat,
            ))
    elif len(mod_sections) == 1:
        for stat in mod_sections[0]:
            explicits.append(ModInstance(
                family=_guess_family(stat),
                affix_type="prefix",
                tier=1, req_level=1, weight=1,
                stat_text=stat,
            ))

    # Resolve item_class
    if not item_class:
        item_class = _guess_item_class(base_name)

    from poe2_crafting_mcp.crafting.simulator import get_max_sockets_for_item_class
    max_sockets = get_max_sockets_for_item_class(item_class)

    item = ItemState(
        item_class=item_class,
        ilvl=ilvl,
        rarity=rarity,
        mods=explicits,
        corrupted=corrupted,
        quality=quality,
        max_sockets=max_sockets,
        implicits=implicits,
    )

    return item, base_name, item_name


def _guess_family(stat_text: str) -> str:
    """Best-effort guess at mod family from stat text."""
    lower = stat_text.lower()
    if "maximum life" in lower or "to maximum life" in lower:
        return "IncreasedLife"
    if "maximum mana" in lower or "to maximum mana" in lower:
        return "IncreasedMana"
    if "evasion" in lower and "increased" in lower:
        return "DefencesPercent"
    if "evasion rating" in lower and "+" in stat_text:
        return "BaseLocalDefences"
    if "energy shield" in lower:
        return "DefencesPercent"
    if "armour" in lower and "break" not in lower and "increased" in lower:
        return "DefencesPercent"
    if "fire resistance" in lower:
        return "FireResistance"
    if "cold resistance" in lower:
        return "ColdResistance"
    if "lightning resistance" in lower:
        return "LightningResistance"
    if "chaos resistance" in lower:
        return "ChaosResistance"
    if "attack speed" in lower:
        return "IncreasedAttackSpeed"
    if "cast speed" in lower:
        return "IncreasedCastSpeed"
    if "critical" in lower and "chance" in lower:
        return "CriticalStrikeChance"
    if "critical" in lower and "damage" in lower:
        return "CriticalStrikeMultiplier"
    if "abyssal lord" in lower:
        return "EssenceAbyss"
    if "physical damage" in lower and "adds" in lower:
        return "PhysicalDamage"
    if "fire damage" in lower and "adds" in lower:
        return "FireDamage"
    if "cold damage" in lower and "adds" in lower:
        return "ColdDamage"
    if "lightning damage" in lower and "adds" in lower:
        return "LightningDamage"
    if "accuracy" in lower:
        return "IncreasedAccuracy"
    return "Unknown"


def _guess_item_class(base_name: str) -> str:
    """Guess item_class from base type name."""
    lower = base_name.lower()
    for cls, display in _ITEM_CLASS_TO_BASE_DISPLAY.items():
        if display.lower() == lower:
            return cls
    if "bracers" in lower or "gauntlets" in lower or "gloves" in lower:
        if "gold" in lower or "satin" in lower:
            return "Gloves_int"
        if "titan" in lower or "plated" in lower:
            return "Gloves_str"
        return "Gloves_dex"
    if "bow" in lower and "cross" not in lower:
        return "Bows"
    if "crossbow" in lower:
        return "Crossbows"
    if "staff" in lower:
        return "Staves"
    if "wand" in lower:
        return "Wands"
    if "sceptre" in lower:
        return "Sceptres"
    if "ring" in lower:
        return "Rings"
    if "amulet" in lower:
        return "Amulets"
    if "belt" in lower:
        return "Belts"
    if "helmet" in lower or "helm" in lower or "mask" in lower:
        return "Helmets_dex"
    if "boots" in lower or "greaves" in lower:
        return "Boots_str"
    return base_name


def item_state_to_trade_text(item: ItemState, base_name: str = "") -> str:
    """Convert ItemState to a human-readable format similar to trade site display."""
    lines: list[str] = []
    base_display = base_name or _ITEM_CLASS_TO_BASE_DISPLAY.get(item.item_class, item.item_class)

    header = f"{item.rarity} {base_display}"
    if item.quality > 0:
        header += f" (Q{item.quality}%)"
    if item.corrupted:
        header += " [Corrupted]"
    lines.append(header)
    lines.append(f"ilvl {item.ilvl} | {len(item.prefixes)}P/{len(item.suffixes)}S")

    if item.implicits:
        for imp in item.implicits:
            lines.append(f"  [Implicit] {imp.display_text}")

    for mod in item.mods:
        prefix = "P" if mod.affix_type == "prefix" else "S"
        markers = ""
        if mod.fractured:
            markers += " [F]"
        if mod.desecrated:
            markers += " [D]"
        if item.essence_mod_family and mod.family == item.essence_mod_family:
            markers += " [E]"
        lines.append(f"  [{prefix}] T{mod.tier} {mod.stat_text}{markers}")

    if any(s for s in item.sockets if s):
        lines.append(f"  Sockets: {', '.join(s for s in item.sockets if s)}")

    return "\n".join(lines)
