"""
Item state to PoB text converter.

Converts our ItemState to Path of Building's raw item text format,
including mods, quality, sockets/socketable effects, and corruption.
"""

from __future__ import annotations

from poe2_crafting_mcp.crafting.simulator import ItemState, ModInstance


# Map item_class prefixes to base type display names
_ITEM_CLASS_TO_BASE_DISPLAY: dict[str, str] = {
    "Gloves_int": "Gold Gloves",
    "Gloves_str": "Titan Gauntlets",
    "Gloves_dex": "Stealth Gloves",
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
    """Convert an ItemState to PoB raw item text format.

    Args:
        item: the crafted item state
        base_name: display name of the base type (e.g. "Gold Gloves")
        item_name: optional rare item name (e.g. "Apocalypse Grip")
        db_path: path to DB for socketable effect lookup

    Returns:
        Multi-line string in PoB clipboard format.
    """
    lines: list[str] = []
    sep = "--------"

    # ── Rarity & name ─────────────────────────────────────────────────────────
    lines.append(f"Rarity: {item.rarity}")

    base_display = base_name or _ITEM_CLASS_TO_BASE_DISPLAY.get(item.item_class, item.item_class)

    if item.rarity in ("Rare", "Unique"):
        name = item_name or f"Crafted {base_display}"
        lines.append(name)
        lines.append(base_display)
    else:
        lines.append(base_display)

    lines.append(sep)

    # ── Properties ────────────────────────────────────────────────────────────
    if item.quality > 0:
        lines.append(f"Quality: +{item.quality}%")
    lines.append(f"Item Level: {item.ilvl}")
    lines.append(sep)

    # ── Implicit mods (corruption implicits, base implicits) ────────────────
    if item.implicits:
        for imp in item.implicits:
            lines.append(imp.stat_text)
        lines.append(sep)

    # ── Explicit mods ─────────────────────────────────────────────────────────
    for mod in item.mods:
        mod_line = mod.stat_text
        if mod.fractured:
            mod_line += " (fractured)"
        if mod.desecrated:
            mod_line += " (desecrated)"
        lines.append(mod_line)

    # ── Socketable effects ────────────────────────────────────────────────────
    # Socketable effects are added as stats (PoB reads them as implicit-like bonuses)
    socketed_items = [s for s in item.sockets if s]
    if socketed_items:
        lines.append(sep)
        from poe2_crafting_mcp.crafting.socketables import get_socketable_effect_for_item
        for socket_name in socketed_items:
            # Convert display name to family key for lookup
            # "Greater Body Rune" → try "GreaterBodyRune", "BodyRune", etc.
            family_key = socket_name.replace(" ", "").replace("'", "")
            effect = get_socketable_effect_for_item(
                db_path, item.item_class, family_key
            )
            if not effect:
                # Try stripping tier prefix (Lesser/Greater)
                for prefix in ("Lesser", "Greater"):
                    if family_key.startswith(prefix):
                        stripped = family_key[len(prefix):]
                        effect = get_socketable_effect_for_item(
                            db_path, item.item_class, stripped
                        )
                        if effect:
                            break
            if effect:
                lines.append(f"{effect.stat_text} (augment)")
            else:
                lines.append(f"[{socket_name}] (augment)")

    # ── Footer ────────────────────────────────────────────────────────────────
    if item.corrupted:
        lines.append(sep)
        lines.append("Corrupted")

    return "\n".join(lines)


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
