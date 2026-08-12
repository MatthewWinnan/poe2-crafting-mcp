"""
Essence resolver — maps (essence_name, item_slot) → essence mod details.

Bridges the essences DB table to the crafting simulator by resolving
which mod an essence gives on a specific item type.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class EssenceMod:
    """Resolved essence mod for a specific item slot."""
    essence_name: str
    tier: str           # "Lesser", "Normal", "Greater", "Perfect", "Corrupted", "Alloy"
    base_name: str      # e.g. "Body", "Haste"
    effect_type: str    # "upgrade" or "swap"
    item_slots: str     # matched slot string from DB
    stat_text: str
    stat_min: float | None
    stat_max: float | None


# Mapping from item_bases.slot → set of essence slot category terms that match.
# An essence row matches if ANY of its comma-separated item_slots terms matches
# any of the categories for the item's slot.
#
# Categories:
#   Armour = Body Armour, Boots, Gloves, Helmet, Shield (defensive gear)
#   Jewellery = Amulet, Ring, Talisman
#   Martial Weapon = melee weapons + bow + crossbow (non-caster)
#   Caster Weapon = Wand, Sceptre, Staff, Focus
#   Melee Weapon = all melee weapon slots
#   Weapons = all weapons
#   Equipment = everything wearable
#   One Handed Melee Weapon = Claw, Dagger, One Hand Axe/Mace/Sword, Flail, Spear
#   Two Handed Melee Weapon = Two Hand Axe/Mace/Sword, Quarterstaff

_SLOT_TO_CATEGORIES: dict[str, set[str]] = {
    # Armour pieces
    "Body Armour":    {"Body Armour", "Armour", "Equipment"},
    "Boots":          {"Boots", "Armour", "Equipment"},
    "Gloves":         {"Gloves", "Armour", "Equipment"},
    "Helmet":         {"Helmet", "Armour", "Equipment"},
    "Shield":         {"Shield", "Armour", "Equipment"},
    # Jewellery
    "Amulet":         {"Amulet", "Jewellery", "Equipment"},
    "Ring":           {"Ring", "Jewellery", "Equipment"},
    "Talisman":       {"Talisman", "Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "Two Handed Melee Weapon", "Two Handed Melee Weapon or Crossbow"},
    "Belt":           {"Belt", "Equipment"},
    # Ranged weapons
    "Bow":            {"Bow", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon or Bow"},
    "Crossbow":       {"Crossbow", "Martial Weapon", "Weapons", "Equipment",
                       "Two Handed Melee Weapon or Crossbow", "Bow or Crossbow"},
    # Caster weapons
    "Wand":           {"Wand", "Caster Weapon", "Weapons", "Equipment"},
    "Sceptre":        {"Sceptre", "Caster Weapon", "Weapons", "Equipment"},
    "Staff":          {"Staff", "Caster Weapon", "Weapons", "Equipment"},
    "Focus":          {"Focus", "Caster Weapon", "Equipment"},
    # One-handed melee
    "Claw":           {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    "Dagger":         {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    "One Hand Axe":   {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    "One Hand Mace":  {"Mace", "Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    "One Hand Sword": {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    "Flail":          {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    "Spear":          {"Spear", "Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "One Handed Melee Weapon", "One Handed Melee Weapon or Bow"},
    # Two-handed melee
    "Two Hand Axe":   {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "Two Handed Melee Weapon", "Two Handed Melee Weapon or Crossbow"},
    "Two Hand Mace":  {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "Two Handed Melee Weapon", "Two Handed Melee Weapon or Crossbow"},
    "Two Hand Sword": {"Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "Two Handed Melee Weapon", "Two Handed Melee Weapon or Crossbow"},
    "Quarterstaff":   {"Quarterstaff", "Melee Weapon", "Martial Weapon", "Weapons", "Equipment",
                       "Two Handed Melee Weapon", "Two Handed Melee Weapon or Crossbow"},
    # Other
    "Quiver":         {"Quiver", "Equipment"},
}


def _parse_item_slots(item_slots_str: str) -> set[str]:
    """Parse "Belt, Boots, Gloves or Helmet" → {"Belt", "Boots", "Gloves", "Helmet"}."""
    # Split on ", " and " or "
    parts = item_slots_str.replace(" or ", ", ").split(", ")
    return {p.strip() for p in parts if p.strip()}


def slot_matches_essence(item_slot: str, essence_item_slots: str) -> bool:
    """Check if an item's slot matches an essence's item_slots string."""
    categories = _SLOT_TO_CATEGORIES.get(item_slot)
    if not categories:
        return False

    essence_terms = _parse_item_slots(essence_item_slots)

    # Direct match: item_slot itself appears in essence terms
    if item_slot in essence_terms:
        return True

    # Category match: any of the item's categories match an essence term
    return bool(categories & essence_terms)


class EssenceResolver:
    """Resolves essence name + item slot → EssenceMod."""

    def __init__(self, db_path: str = "data/poe2_craft.db"):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def resolve(self, essence_name: str, item_slot: str) -> EssenceMod | None:
        """Find the specific mod an essence gives on an item slot.

        Args:
            essence_name: Full name like "Greater Essence of the Body"
            item_slot: item_bases.slot value like "Gloves", "Bow", "Ring"

        Returns:
            EssenceMod with stat details, or None if essence doesn't apply to this slot.
        """
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM essences WHERE name = ?", (essence_name,)
        ).fetchall()
        conn.close()

        if not rows:
            return None

        # Find the row whose item_slots matches this item slot
        # Most specific match wins (fewest slot terms)
        best: dict | None = None
        best_specificity = 999

        for row in rows:
            if slot_matches_essence(item_slot, row["item_slots"]):
                terms = _parse_item_slots(row["item_slots"])
                if len(terms) < best_specificity:
                    best = dict(row)
                    best_specificity = len(terms)

        if not best:
            return None

        return EssenceMod(
            essence_name=best["name"],
            tier=best["tier"],
            base_name=best["base_name"],
            effect_type=best["effect_type"],
            item_slots=best["item_slots"],
            stat_text=best["stat_text"],
            stat_min=best["stat_min"],
            stat_max=best["stat_max"],
        )

    def resolve_by_base(self, base_name: str, tier: str, item_slot: str) -> EssenceMod | None:
        """Resolve by essence base name and tier.

        Args:
            base_name: e.g. "Body", "Haste"
            tier: e.g. "Greater", "Perfect"
            item_slot: e.g. "Gloves", "Bow"
        """
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM essences WHERE base_name = ? AND tier = ?",
            (base_name, tier),
        ).fetchall()
        conn.close()

        if not rows:
            return None

        best: dict | None = None
        best_specificity = 999

        for row in rows:
            if slot_matches_essence(item_slot, row["item_slots"]):
                terms = _parse_item_slots(row["item_slots"])
                if len(terms) < best_specificity:
                    best = dict(row)
                    best_specificity = len(terms)

        if not best:
            return None

        return EssenceMod(
            essence_name=best["name"],
            tier=best["tier"],
            base_name=best["base_name"],
            effect_type=best["effect_type"],
            item_slots=best["item_slots"],
            stat_text=best["stat_text"],
            stat_min=best["stat_min"],
            stat_max=best["stat_max"],
        )

    def list_for_slot(self, item_slot: str, tier: str = "") -> list[EssenceMod]:
        """List all essences available for a given item slot.

        Args:
            item_slot: e.g. "Gloves", "Bow"
            tier: optional filter by tier ("Lesser", "Greater", etc.)
        """
        conn = self._conn()
        if tier:
            rows = conn.execute(
                "SELECT * FROM essences WHERE tier = ?", (tier,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM essences").fetchall()
        conn.close()

        results: list[EssenceMod] = []
        seen: set[str] = set()  # dedupe by (name, best match)

        for row in rows:
            if slot_matches_essence(item_slot, row["item_slots"]):
                key = (row["name"], row["item_slots"])
                if key not in seen:
                    seen.add(key)
                    results.append(EssenceMod(
                        essence_name=row["name"],
                        tier=row["tier"],
                        base_name=row["base_name"],
                        effect_type=row["effect_type"],
                        item_slots=row["item_slots"],
                        stat_text=row["stat_text"],
                        stat_min=row["stat_min"],
                        stat_max=row["stat_max"],
                    ))

        # Sort: most specific match first (fewest slot terms), then by name
        results.sort(key=lambda e: (len(_parse_item_slots(e.item_slots)), e.essence_name))
        return results

    def get_currency_key(self, tier: str) -> str:
        """Map essence tier to simulator currency key."""
        return {
            "Lesser": "lesser_essence",
            "Normal": "normal_essence",
            "Greater": "greater_essence",
            "Perfect": "perfect_essence",
            "Alloy": "alloy",
        }.get(tier, "")
