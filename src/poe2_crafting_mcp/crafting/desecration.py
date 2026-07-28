"""
Desecration crafting engine — Abyss bone application and reveal system.

Models the full desecration flow:
  1. Apply bone → determine affix type → add unrevealed slot
  2. Reveal at Well of Souls → draw N options from desecrated pool
  3. Player/optimizer picks one → mod placed on item

Key difference from regular crafting: the player has AGENCY via choice
from revealed options, making this a branching decision node.
"""

from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass
from math import comb
from typing import Any

from poe2_crafting_mcp.crafting.simulator import ItemState, ModInstance


# ── Bone Definitions ──────────────────────────────────────────────────────────

BONES: dict[str, dict[str, Any]] = {
    # Jawbones — Weapons + Quivers
    "gnawed_jawbone":     {"slots": "weapon", "max_ilvl": 64, "min_mod_level": 0},
    "preserved_jawbone":  {"slots": "weapon", "max_ilvl": None, "min_mod_level": 0},
    "ancient_jawbone":    {"slots": "weapon", "max_ilvl": None, "min_mod_level": 40},
    # Ribs — Armour (Helmet, Gloves, Boots, Body Armour)
    "gnawed_rib":         {"slots": "armour", "max_ilvl": 64, "min_mod_level": 0},
    "preserved_rib":      {"slots": "armour", "max_ilvl": None, "min_mod_level": 0},
    "ancient_rib":        {"slots": "armour", "max_ilvl": None, "min_mod_level": 40},
    # Collarbones — Jewellery (Amulet, Ring, Belt)
    "gnawed_collarbone":  {"slots": "jewellery", "max_ilvl": 64, "min_mod_level": 0},
    "preserved_collarbone": {"slots": "jewellery", "max_ilvl": None, "min_mod_level": 0},
    "ancient_collarbone": {"slots": "jewellery", "max_ilvl": None, "min_mod_level": 40},
    # Cranium — Jewels
    "preserved_cranium":  {"slots": "jewel", "max_ilvl": None, "min_mod_level": 0},
    # Vertebrae — Waystones
    "preserved_vertebrae": {"slots": "waystone", "max_ilvl": None, "min_mod_level": 0},
}

# Item class → bone slot category mapping
_WEAPON_CLASSES = {
    "Bows", "Crossbows", "Daggers", "Claws", "Flails", "Spears",
    "One_Hand_Axes", "One_Hand_Maces", "One_Hand_Swords",
    "Two_Hand_Axes", "Two_Hand_Maces", "Two_Hand_Swords",
    "Quarterstaves", "Sceptres", "Staves", "Wands", "Quivers",
    "Talismans", "Traps",
}

_ARMOUR_CLASSES_PREFIX = {
    "Body_Armours", "Boots", "Gloves", "Helmets", "Shields", "Bucklers",
}

_JEWELLERY_CLASSES = {"Amulets", "Rings", "Belts"}
_JEWEL_CLASSES = {"Ruby", "Emerald", "Sapphire", "Diamond",
                  "Time-Lost_Ruby", "Time-Lost_Emerald", "Time-Lost_Sapphire", "Time-Lost_Diamond"}


def get_bone_slot_for_item_class(item_class: str) -> str:
    """Determine which bone slot category an item class belongs to."""
    if item_class in _WEAPON_CLASSES:
        return "weapon"
    if item_class in _JEWELLERY_CLASSES:
        return "jewellery"
    if item_class in _JEWEL_CLASSES:
        return "jewel"
    # Armour classes have attribute suffixes (e.g. Body_Armours_str)
    base = item_class.split("_")[0] if "_" in item_class else item_class
    for prefix in _ARMOUR_CLASSES_PREFIX:
        if item_class.startswith(prefix):
            return "armour"
    # Foci are off-hand, treated as armour slot for desecration
    if item_class == "Foci":
        return "armour"
    return "unknown"


# ── Desecration Pool ──────────────────────────────────────────────────────────

@dataclass
class DesecrationOption:
    """A single revealed option at the Well of Souls."""
    family: str
    affix_type: str
    tier: int
    req_level: int
    stat_text: str
    faction: str         # "amanamu", "kurgal", "ulaman", or ""
    tags: list[str]

    def to_mod_instance(self, desecrated: bool = True) -> ModInstance:
        """Convert to a ModInstance for placement on item."""
        mod = ModInstance(
            family=self.family,
            affix_type=self.affix_type,
            tier=self.tier,
            req_level=self.req_level,
            weight=1,  # desecrated mods have uniform weight
            stat_text=self.stat_text,
        )
        return mod


def get_desecration_pool(
    db_path: str,
    item_class: str,
    ilvl: int,
    affix_type: str = "",
    min_mod_level: int = 0,
    faction: str = "",
    blocked_families: set[str] | None = None,
) -> list[DesecrationOption]:
    """Get eligible desecrated mods for reveal.

    Args:
        db_path: path to poe2_craft.db
        item_class: poe2db item class (e.g. "Bows", "Gloves_int")
        ilvl: item level (max req_level for eligible mods)
        affix_type: "prefix", "suffix", or "" for both
        min_mod_level: minimum req_level (0 for Preserved, 40 for Ancient)
        faction: "" for all, "amanamu"/"kurgal"/"ulaman" for lich omen filter
        blocked_families: families already on item (excluded from pool)

    Returns list of DesecrationOption (all weight=1, uniform distribution).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    q = """
        SELECT mod_family, affix_type, mod_code, stat_text, weight, req_level, tags
        FROM mod_weights
        WHERE pool = 'desecrated'
          AND item_class = ?
          AND req_level <= ?
          AND req_level >= ?
    """
    params: list[Any] = [item_class, ilvl, min_mod_level]

    if affix_type:
        q += " AND affix_type = ?"
        params.append(affix_type)

    rows = conn.execute(q, params).fetchall()
    conn.close()

    blocked = blocked_families or set()
    results: list[DesecrationOption] = []

    for row in rows:
        family = row["mod_family"]
        if family in blocked:
            continue

        tags = json.loads(row["tags"]) if row["tags"] else []

        # Determine faction from tags
        mod_faction = ""
        if "amanamu_mod" in tags:
            mod_faction = "amanamu"
        elif "kurgal_mod" in tags:
            mod_faction = "kurgal"
        elif "ulaman_mod" in tags:
            mod_faction = "ulaman"

        # Filter by faction if lich omen active
        if faction and mod_faction != faction:
            continue

        # Tier: desecrated mods typically have single tier, use 1
        results.append(DesecrationOption(
            family=family,
            affix_type=row["affix_type"],
            tier=1,  # desecrated mods are single-tier
            req_level=row["req_level"],
            stat_text=row["stat_text"],
            faction=mod_faction,
            tags=tags,
        ))

    return results


# ── Probability Calculation ───────────────────────────────────────────────────

def desecration_hit_probability(
    pool_size: int,
    target_count: int = 1,
    draws: int = 3,
) -> float:
    """Calculate P(at least one target mod appears in N draws without replacement).

    Since all desecrated mods have weight=1 (uniform distribution):
    P(hit) = 1 - C(pool_size - target_count, draws) / C(pool_size, draws)

    Args:
        pool_size: total eligible mods in pool
        target_count: how many mods in pool match the target family
        draws: number of options revealed (3 normally, 6 with Echoes)

    Returns probability [0.0, 1.0].
    """
    if pool_size <= 0 or target_count <= 0:
        return 0.0
    if target_count >= pool_size or draws >= pool_size:
        return 1.0
    if draws <= 0:
        return 0.0

    # P(miss all draws) = C(pool - targets, draws) / C(pool, draws)
    non_targets = pool_size - target_count
    if non_targets < draws:
        return 1.0  # not enough non-targets to fill all draws → guaranteed hit

    p_miss = comb(non_targets, draws) / comb(pool_size, draws)
    return 1.0 - p_miss


# ── Desecration Engine ────────────────────────────────────────────────────────

@dataclass
class RevealResult:
    """Result of a desecration reveal."""
    options: list[DesecrationOption]   # the 3 (or 6) revealed options
    chosen: DesecrationOption | None   # which one was picked
    hit_target: bool                   # was the target among options?
    rerolled: bool = False             # was Echoes omen used?


class DesecrationEngine:
    """Handles bone application, pool lookup, reveal simulation, and probability."""

    def __init__(self, db_path: str = "data/poe2_craft.db"):
        self._db_path = db_path

    def validate_bone(self, bone: str, item_class: str, ilvl: int) -> str | None:
        """Check if a bone can be applied to this item. Returns error or None."""
        bone_def = BONES.get(bone)
        if not bone_def:
            return f"Unknown bone: {bone}"

        expected_slot = bone_def["slots"]
        actual_slot = get_bone_slot_for_item_class(item_class)
        if actual_slot != expected_slot:
            return f"Bone '{bone}' is for {expected_slot}, item is {actual_slot}"

        max_ilvl = bone_def.get("max_ilvl")
        if max_ilvl and ilvl > max_ilvl:
            return f"Bone '{bone}' requires item level ≤ {max_ilvl}, item is ilvl {ilvl}"

        return None

    def determine_affix_type(
        self, item: ItemState, gentype_only: int = 0
    ) -> str:
        """Determine whether desecration adds a prefix or suffix.

        Rules:
        - Necromancy omen overrides (gentype_only: 1=prefix, 2=suffix)
        - If only prefix open → prefix
        - If only suffix open → suffix
        - If both open → random
        - If neither open (6 mods) → random (a mod will be removed first)
        """
        if gentype_only == 1:
            return "prefix"
        if gentype_only == 2:
            return "suffix"

        if item.open_prefixes > 0 and item.open_suffixes == 0:
            return "prefix"
        if item.open_suffixes > 0 and item.open_prefixes == 0:
            return "suffix"

        # Both open or both full → random
        return random.choice(["prefix", "suffix"])

    def apply_bone(
        self,
        item: ItemState,
        bone: str,
        omens: list[str] | None = None,
    ) -> tuple[ItemState, str]:
        """Apply bone to item. Returns (modified item, affix_type of desecrated slot).

        If item has 6 mods, removes a random mod first (same affix type as desecrated).
        Special: if item has_abyss_mark, the Mark is always removed (deterministic).
        """
        from poe2_crafting_mcp.crafting.simulator import OMENS

        # Merge omen effects
        gentype_only = 0
        if omens:
            for omen_key in omens:
                omen_def = OMENS.get(omen_key, {})
                applies_to = omen_def.get("applies_to", [])
                if "desecrate" in applies_to:
                    if omen_def.get("gentype_only"):
                        gentype_only = omen_def["gentype_only"]

        # Special: Abyss Mark is always removed when desecrating
        if item.has_abyss_mark:
            mark_mod = next(
                (m for m in item.mods if m.family == "EssenceAbyss"), None
            )
            if mark_mod:
                affix_type = mark_mod.affix_type
                item.mods.remove(mark_mod)
                item.has_abyss_mark = False
                item.essence_mod_family = None
                return item, affix_type

        affix_type = self.determine_affix_type(item, gentype_only)

        # If item is full (6 mods), remove a random mod of the same affix type
        if item.open_affixes == 0:
            removable = [
                m for m in item.mods
                if m.affix_type == affix_type and not m.fractured
            ]
            if removable:
                to_remove = random.choice(removable)
                item.mods.remove(to_remove)

        return item, affix_type

    def get_reveal_pool(
        self,
        item_class: str,
        ilvl: int,
        affix_type: str,
        bone: str,
        item: ItemState,
        omens: list[str] | None = None,
    ) -> list[DesecrationOption]:
        """Get the pool from which reveal options will be drawn."""
        from poe2_crafting_mcp.crafting.simulator import OMENS

        bone_def = BONES.get(bone, {})
        min_mod_level = bone_def.get("min_mod_level", 0)

        # Check for lich omen → faction filter
        faction = ""
        if omens:
            for omen_key in omens:
                omen_def = OMENS.get(omen_key, {})
                if omen_def.get("lich_pool"):
                    faction = omen_def["lich_pool"]

        # Family blocking: exclude families already on item
        blocked_families = item.families_on_item

        return get_desecration_pool(
            db_path=self._db_path,
            item_class=item_class,
            ilvl=ilvl,
            affix_type=affix_type,
            min_mod_level=min_mod_level,
            faction=faction,
            blocked_families=blocked_families,
        )

    def reveal(
        self,
        pool: list[DesecrationOption],
        target_family: str = "",
        echoes: bool = False,
        future_targets: set[str] | None = None,
    ) -> RevealResult:
        """Simulate a reveal at the Well of Souls.

        Draws 3 options (or 6 with Echoes). If target_family is specified,
        auto-picks it on hit. On miss, picks "least damaging" option.

        Args:
            pool: eligible desecration options
            target_family: family we're hoping to hit (empty = manual choice)
            echoes: True if Omen of Abyssal Echoes active (6 draws)
            future_targets: families we plan to target later (for miss heuristic)

        Returns RevealResult with options, chosen mod, and hit status.
        """
        n_draws = 6 if echoes else 3
        n_draws = min(n_draws, len(pool))

        if n_draws == 0:
            return RevealResult(options=[], chosen=None, hit_target=False, rerolled=echoes)

        options = random.sample(pool, n_draws)

        # Check for hit
        if target_family:
            hits = [o for o in options if o.family == target_family]
            if hits:
                return RevealResult(
                    options=options,
                    chosen=hits[0],
                    hit_target=True,
                    rerolled=echoes,
                )

        # Miss case: pick least damaging option
        chosen = self._pick_least_damaging(options, future_targets)
        return RevealResult(
            options=options,
            chosen=chosen,
            hit_target=False,
            rerolled=echoes,
        )

    def _pick_least_damaging(
        self,
        options: list[DesecrationOption],
        future_targets: set[str] | None = None,
    ) -> DesecrationOption:
        """Heuristic: pick the option that blocks the fewest future targets.

        Priority:
        1. Doesn't block any future target family
        2. Lowest req_level (easier to remove with Whittling)
        3. First option (arbitrary tiebreak)
        """
        targets = future_targets or set()

        # Prefer options that don't block future targets
        non_blocking = [o for o in options if o.family not in targets]
        candidates = non_blocking if non_blocking else options

        # Among non-blocking, prefer lowest req_level (easiest to remove)
        candidates.sort(key=lambda o: o.req_level)
        return candidates[0]

    def hit_probability(
        self,
        item_class: str,
        ilvl: int,
        affix_type: str,
        target_family: str,
        bone: str = "preserved_rib",
        item: ItemState | None = None,
        omens: list[str] | None = None,
        echoes: bool = False,
    ) -> dict:
        """Calculate analytical probability of hitting target on reveal.

        Returns dict with pool_size, target_count, draws, probability, and
        expected_attempts.
        """
        # Build a temporary item for family blocking if not provided
        blocked = item.families_on_item if item else set()
        from poe2_crafting_mcp.crafting.simulator import OMENS

        bone_def = BONES.get(bone, {})
        min_mod_level = bone_def.get("min_mod_level", 0)

        faction = ""
        if omens:
            for omen_key in omens:
                omen_def = OMENS.get(omen_key, {})
                if omen_def.get("lich_pool"):
                    faction = omen_def["lich_pool"]

        pool = get_desecration_pool(
            db_path=self._db_path,
            item_class=item_class,
            ilvl=ilvl,
            affix_type=affix_type,
            min_mod_level=min_mod_level,
            faction=faction,
            blocked_families=blocked,
        )

        pool_size = len(pool)
        target_count = len([m for m in pool if m.family == target_family])
        draws = 6 if echoes else 3

        prob = desecration_hit_probability(pool_size, target_count, draws)

        return {
            "pool_size": pool_size,
            "target_count": target_count,
            "draws": draws,
            "probability": round(prob, 4),
            "expected_attempts": round(1.0 / prob, 2) if prob > 0 else float("inf"),
            "faction": faction or "all",
            "affix_type": affix_type,
            "min_mod_level": min_mod_level,
        }
