"""
Socketable system — runes, soul cores, idols, and their slot-dependent effects.

Queries the mod_weights table (pool='socketable') to get what each
socketable item does on a given item class.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class SocketableEffect:
    """What a socketable item does on a specific item class."""
    name: str              # mod_family key (e.g. "BodyRune", "SoulCoreofTacati")
    display_name: str      # human-readable (e.g. "Body Rune", "Soul Core of Tacati")
    stat_text: str         # effect text (e.g. "+45 to maximum Life")
    tier: int              # tier within the socketable (1=Lesser, 2=Normal, etc.)
    item_class: str        # which item class this applies to


def _family_to_display_name(family: str) -> str:
    """Convert mod_family key to display name.
    
    'BodyRune' → 'Body Rune'
    'SoulCoreofTacati' → 'Soul Core of Tacati'
    'GreaterDesertRune' → 'Greater Desert Rune'
    """
    import re
    # Insert spaces before capitals (but not at start)
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', family)
    # Fix "of" being capitalized
    name = name.replace(" Of ", " of ").replace("Soulcore", "Soul Core")
    # Fix common patterns
    name = name.replace("Soul Coreof", "Soul Core of")
    name = name.replace("Runeof", "Rune of")
    name = name.replace("Idolof", "Idol of")
    return name


def get_socketable_effects(
    db_path: str,
    item_class: str,
    socketable_name: str = "",
) -> list[SocketableEffect]:
    """Get socketable effects for an item class.
    
    Args:
        db_path: path to poe2_craft.db
        item_class: poe2db item class (e.g. "Gloves_int", "Bows")
        socketable_name: filter by specific socketable mod_family.
                         If empty, returns all socketables for this item class.
    
    Returns list of SocketableEffect with tier info.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    if socketable_name:
        rows = conn.execute(
            "SELECT mod_family, stat_text, req_level FROM mod_weights "
            "WHERE pool = 'socketable' AND item_class = ? AND mod_family = ? "
            "ORDER BY req_level",
            (item_class, socketable_name),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT mod_family, stat_text, req_level FROM mod_weights "
            "WHERE pool = 'socketable' AND item_class = ? "
            "ORDER BY mod_family, req_level",
            (item_class,),
        ).fetchall()
    conn.close()
    
    results: list[SocketableEffect] = []
    # Group by family to assign tier numbers
    current_family = ""
    tier_counter = 0
    
    for row in rows:
        family = row["mod_family"]
        if family != current_family:
            current_family = family
            tier_counter = 0
        tier_counter += 1
        
        results.append(SocketableEffect(
            name=family,
            display_name=_family_to_display_name(family),
            stat_text=row["stat_text"],
            tier=tier_counter,
            item_class=item_class,
        ))
    
    return results


def get_socketable_effect_for_item(
    db_path: str,
    item_class: str,
    socketable_name: str,
    tier: int = -1,
) -> SocketableEffect | None:
    """Get the effect of a specific socketable at a specific tier.
    
    Args:
        db_path: path to DB
        item_class: item class
        socketable_name: mod_family key or display name
        tier: which tier (1-based). -1 = best (highest tier)
    
    Returns SocketableEffect or None.
    """
    # Try exact family match first, then fuzzy
    effects = get_socketable_effects(db_path, item_class, socketable_name)
    
    if not effects:
        # Try converting display name to family key
        family_key = socketable_name.replace(" ", "").replace("'", "")
        effects = get_socketable_effects(db_path, item_class, family_key)
    
    if not effects:
        return None
    
    if tier == -1:
        return effects[-1]  # best tier (last)
    
    if 1 <= tier <= len(effects):
        return effects[tier - 1]
    
    return effects[-1]  # fallback to best


def list_socketable_families(db_path: str, item_class: str) -> list[dict]:
    """List all unique socketable families available for an item class.
    
    Returns list of {name, display_name, tiers, best_stat_text}.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute(
        "SELECT mod_family, stat_text, COUNT(*) as tier_count "
        "FROM mod_weights "
        "WHERE pool = 'socketable' AND item_class = ? "
        "GROUP BY mod_family "
        "ORDER BY mod_family",
        (item_class,),
    ).fetchall()
    conn.close()
    
    results = []
    for row in rows:
        family = row["mod_family"]
        results.append({
            "name": family,
            "display_name": _family_to_display_name(family),
            "tiers": row["tier_count"],
            "best_stat_text": row["stat_text"],  # last grouped = highest tier
        })
    
    return results
