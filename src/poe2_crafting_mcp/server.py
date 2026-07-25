"""MCP Server — PoE2 Crafting & Build Advisor."""

import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from poe2_crafting_mcp.engine.pob_engine import PoBEngine
from poe2_crafting_mcp.data.database import PoBDatabase

# ── Bootstrap ────────────────────────────────────────────────────────────────

POB_PATH = Path(os.environ.get("POB_PATH", Path(__file__).parent.parent.parent / "vendor" / "PathOfBuilding-PoE2"))

mcp: FastMCP = FastMCP("poe2-crafting")

# Single engine instance — PoB boots once per server lifetime.
_engine: PoBEngine | None = None
_db: PoBDatabase | None = None


def _get_engine() -> PoBEngine:
    global _engine
    if _engine is None:
        _engine = PoBEngine(POB_PATH)
    return _engine


def _get_db() -> PoBDatabase:
    global _db
    if _db is None:
        _db = PoBDatabase()
    return _db


def _to_json(obj: Any) -> str:
    """Serialise dataclasses / dicts / primitives to a compact JSON string."""
    def _default(o: Any) -> Any:
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        raise TypeError(f"Not serialisable: {type(o)}")
    return json.dumps(obj, default=_default, indent=2)


# ── Build Loading ─────────────────────────────────────────────────────────────

@mcp.tool()
def load_build(path: str) -> str:
    """
    Load a PoB build from a file containing a share code.

    Args:
        path: Absolute or relative path to the .txt file with the PoB share code.

    Returns:
        JSON with build info and baseline stats.
    """
    engine = _get_engine()
    engine.load_build_from_file(path)
    info = engine.get_build_info()
    stats = engine.get_stats()
    return _to_json({"info": info, "stats": stats})


@mcp.tool()
def load_build_from_code(code: str) -> str:
    """
    Load a PoB build from a raw share code string (base64url + zlib).

    Returns:
        JSON with build info and baseline stats.
    """
    engine = _get_engine()
    engine.load_build_from_code(code)
    info = engine.get_build_info()
    stats = engine.get_stats()
    return _to_json({"info": info, "stats": stats})


# ── Build Inspection ──────────────────────────────────────────────────────────

@mcp.tool()
def get_build_info() -> str:
    """
    Get metadata about the loaded build: class, ascendancy, level, main skill,
    and passive tree node counts.
    """
    return _to_json(_get_engine().get_build_info())


@mcp.tool()
def get_stats() -> str:
    """
    Get current offence and defence statistics.

    Returns DPS breakdown, resistances, life/ES/evasion/armour.
    Reflects whatever config options are currently active.
    """
    return _to_json(_get_engine().get_stats())


@mcp.tool()
def get_combat_profile() -> str:
    """
    Get the full combat scenario profile for the loaded build.

    This is the primary tool for understanding what buffs, charges, ailments,
    and config options are relevant to the build. Use it before calling
    set_config_option() to model realistic combat conditions.

    Returns a JSON object with:
    - total_dps: current DPS given active config
    - charges: {Power/Frenzy/Endurance/...} with current/max/configured
    - rage_available/rage_max/rage_current: rage info
    - ailments_on_enemy: shock/ignite/chill/freeze/poison/bleed applied to enemies
    - life/energy_shield/evasion/armour/resistances
    - damage_taken_mults: per-element damage taken multiplier after mitigation
    - relevant_config: all config knobs for this build grouped by category
      (charges, buffs, enemy, ailments, conditions, modes, other)
      Each option has: var, var_type, label, tooltip, current_value, list_options
    """
    return _to_json(_get_engine().get_combat_profile())


@mcp.tool()
def get_equipped_items() -> str:
    """
    Get all equipped items with their mods, rarity, and item level.
    Slots with no item are returned as null.
    """
    return _to_json(_get_engine().get_equipped_items())


@mcp.tool()
def get_socket_groups() -> str:
    """
    Get all skill socket groups with full gem details (level, quality,
    corrupted state, enabled state, support/active tag).
    """
    return _to_json(_get_engine().get_socket_groups())


@mcp.tool()
def get_skill_list() -> str:
    """
    List all available skills (socket group labels) in the build.

    Returns a JSON array of strings. Use the 1-based index with set_main_skill().
    """
    return _to_json(_get_engine().get_skill_list())


@mcp.tool()
def get_keystones() -> str:
    """Get allocated keystone passives as a JSON list of names."""
    return _to_json(_get_engine().get_keystones())


@mcp.tool()
def get_notables() -> str:
    """Get allocated notable passives as a JSON list of names."""
    return _to_json(_get_engine().get_notables())


@mcp.tool()
def get_output() -> str:
    """
    Get the full raw PoB calculation output as a flat JSON object.

    Contains ~200 offence + defence stats keyed by PoB's internal names
    (e.g. TotalDPS, Ward, BlockChance, ShockChance).
    Use this for any stat not covered by get_stats(), or to compare
    exactly what changed after a config or gear modification.
    """
    return _to_json(_get_engine().get_output())


# ── Scenario Configuration ────────────────────────────────────────────────────

@mcp.tool()
def set_config_option(var: str, value: str) -> str:
    """
    Set a PoB config option and return updated stats.

    Use get_combat_profile() first to discover the available var names,
    their types, and valid values for list options.

    Args:
        var:   Config option var name (e.g. "usePowerCharges", "enemyIsBoss",
               "conditionEnemyShocked", "multiplierRage").
        value: String representation of the value:
               - bool:   "true" / "false"
               - int:    "30"
               - float:  "1.5"
               - list:   the val string from list_options (e.g. "None", "Pinnacle")
               - clear:  "null" to reset to PoB default

    Returns:
        JSON with updated BuildStats.
    """
    engine = _get_engine()

    # Parse value string into the appropriate Python type
    parsed: bool | int | float | str | None
    v = value.strip()
    if v.lower() == "null" or v.lower() == "none":
        parsed = None
    elif v.lower() == "true":
        parsed = True
    elif v.lower() == "false":
        parsed = False
    else:
        try:
            parsed = int(v)
        except ValueError:
            try:
                parsed = float(v)
            except ValueError:
                parsed = v  # treat as string (list val)

    stats = engine.set_config_option(var, parsed)
    return _to_json(stats)


@mcp.tool()
def get_all_config() -> str:
    """
    Get all currently-set config options as a flat JSON object.
    Only options that have been explicitly set are returned.
    """
    return _to_json(_get_engine().get_all_config())


@mcp.tool()
def set_main_skill(index: int) -> str:
    """
    Set the active skill by 1-based index.

    Use get_skill_list() to find the index for a skill by name.

    Returns:
        JSON with updated BuildStats.
    """
    return _to_json(_get_engine().set_main_skill(index))


# ── Gear Modifications ────────────────────────────────────────────────────────

@mcp.tool()
def equip_item(slot: str, item_text: str) -> str:
    """
    Equip an item in a slot and return the stat delta.

    Args:
        slot: PoB slot name — one of: "Weapon 1", "Weapon 2", "Helmet",
              "Body Armour", "Gloves", "Boots", "Amulet", "Ring 1",
              "Ring 2", "Belt"
        item_text: Item in PoB raw text format (copy from PoB item editor
                   or Ctrl+C from in-game).

    Returns:
        JSON DPSDelta with before/after stats and convenience change fields.
    """
    return _to_json(_get_engine().equip_item(slot, item_text))


@mcp.tool()
def unequip_slot(slot: str) -> str:
    """
    Remove the item from a slot and return the stat delta.

    Returns:
        JSON DPSDelta.
    """
    return _to_json(_get_engine().unequip_slot(slot))


# ── Gem Modifications ─────────────────────────────────────────────────────────

@mcp.tool()
def set_gem_level(group: int, gem: int, level: int) -> str:
    """
    Set the level of a gem (1–40) and return updated stats.

    Args:
        group: 1-based socket group index (from get_socket_groups()).
        gem:   1-based gem index within the group.
        level: New gem level.
    """
    return _to_json(_get_engine().set_gem_level(group, gem, level))


@mcp.tool()
def set_gem_quality(group: int, gem: int, quality: int) -> str:
    """Set the quality of a gem (0–40) and return updated stats."""
    return _to_json(_get_engine().set_gem_quality(group, gem, quality))


# ── Character ─────────────────────────────────────────────────────────────────

@mcp.tool()
def set_character_level(level: int) -> str:
    """Set the character level (1–100) and return updated stats."""
    return _to_json(_get_engine().set_character_level(level))


# ── Condition Sources ─────────────────────────────────────────────────────────

@mcp.tool()
def get_condition_sources() -> str:
    """
    Explain WHY each condition in relevant_config matters for the active skill.

    For every condition variable used by the current skill calculation, returns:
    - sources: list of passive nodes / gems that reference this condition
    - auto_applicable: True if the condition is reliably active in normal combat
      (e.g. conditionCritRecently at >15% crit chance)
    - current_value: the currently configured value (null = PoB default)

    Use this alongside get_combat_profile() when deciding which conditions to
    enable for a realistic scenario (e.g. "should I set conditionCritRecently?").
    """
    return _to_json(_get_engine().get_condition_sources())


@mcp.tool()
def setup_realistic_scenario(boss: str = "None", enemy_level: int = 80) -> str:
    """
    Auto-configure the most realistic in-combat scenario for the loaded build.

    Applies a generic set of heuristics that work for any build:
    - Enables config options that have defaultState=true in PoB (e.g. targetBrandedEnemy,
      inDemonForm) if they are relevant to this build.
    - Enables enemy ailment conditions (conditionEnemyShocked etc.) for each ailment
      the build can apply (based on ailment chance > 0%).
    - Enables charge use (usePowerCharges, useFrenzyCharges, useEnduranceCharges, etc.)
      and sets multipliers to the build's maximum for each charge type available.
    - Sets rage to the build's maximum if the build can generate rage.
    - Sets Trinity resonance to 200 if the build uses Trinity.
    - Sets enemy type and level.

    Call get_combat_profile() first to see the starting state.
    Call get_combat_profile() again after to inspect the updated scenario details.

    Args:
        boss:        Enemy type — "None" (map monster), "Rare", "Unique" (pinnacle boss).
                     Default "None" for typical mapping scenarios.
        enemy_level: Enemy level for resistance penalty calculations (default 80).

    Returns:
        JSON with:
        - applied: list of {var, value, reason} describing each change made
        - dps_before: DPS before any changes
        - dps_after:  DPS after all changes applied
        - dps_change_percent: % change in DPS
    """
    return _to_json(_get_engine().setup_realistic_scenario(boss=boss, enemy_level=enemy_level))


# ── Export ────────────────────────────────────────────────────────────────────

@mcp.tool()
def export_build_code() -> str:
    """
    Export the current build state as a PoB share code.

    Returns a JSON object with {"code": "<share_code>"}.
    The code can be imported into PoB or saved to a file.
    """
    return _to_json({"code": _get_engine().export_build_code()})


# ── Game Data (ETL-backed) ────────────────────────────────────────────────────

@mcp.tool()
def search_bases(slot: str = "", sub_type: str = "", keyword: str = "",
                 min_level: int = 0, max_level: int = 100,
                 limit: int = 50) -> str:
    """
    Find craftable item bases for a slot and defence type.

    Args:
        slot:      Item slot — "Gloves", "Helmet", "Body Armour", "Boots",
                   "Ring", "Amulet", "Belt", "Weapon", "Shield", "Quiver".
                   Leave blank to search all slots.
        sub_type:  Defence subtype — "Armour", "Evasion", "Energy Shield",
                   "Armour/Evasion", "Evasion/Energy Shield", etc.
                   Leave blank for all subtypes.
        min_level: Minimum required character level.
        max_level: Maximum required character level.
        limit:     Max results (default 50).

    Returns:
        JSON array of bases with name, slot, sub_type, req_level, req_str/dex/int,
        socket_limit, tags, armour, evasion, energy_shield, ward.
    """
    return _to_json(_get_db().search_bases(slot, sub_type, keyword, min_level, max_level, limit))


@mcp.tool()
def search_mods(keyword: str = "", item_tag: str = "",
                category: str = "Item", mod_type: str = "",
                min_level: int = 0, max_level: int = 100,
                limit: int = 30) -> str:
    """
    Search explicit item mods for crafting.

    Use this to find what mods can roll on an item base, or to identify the
    best mod for a given stat improvement.

    Args:
        keyword:   Stat keyword — e.g. "lightning damage", "critical strike",
                   "maximum life", "attack speed". Searches stat text and affix name.
        item_tag:  Filter to mods that can roll on this item type tag —
                   e.g. "gloves", "ring", "staff", "str_armour", "dex_armour",
                   "bow", "wand". Matches against the mod's weight_keys.
        category:  Mod pool — "Item" (default, regular crafted mods),
                   "Jewel", "Runes", "Corruption", "Desecrated", "Flask", "Charm".
        mod_type:  "Prefix" or "Suffix". Leave blank for both.
        min_level: Minimum ilvl required (req_level).
        max_level: Maximum ilvl.
        limit:     Max results (default 30).

    Returns:
        JSON array of mods with id, category, mod_type, affix, stat_text,
        stat_min, stat_max, req_level, group_name, mod_tags, weight_keys.
    """
    return _to_json(_get_db().search_mods(keyword, item_tag, category, mod_type,
                                          min_level, max_level, limit))


@mcp.tool()
def get_gem_info(name: str) -> str:
    """
    Get details for a specific gem by exact name.

    Returns gem_type, is_support, tier, attribute requirements, tags,
    tag_string, weapon_requirements, and natural_max_level.

    Use search_gems() if you don't know the exact name.
    """
    gem = _get_db().get_gem(name)
    if not gem:
        return _to_json({"error": f"Gem '{name}' not found"})
    return _to_json(gem)


@mcp.tool()
def search_gems(keyword: str = "", gem_type: str = "",
                is_support: bool | None = None,
                tag: str = "", limit: int = 30) -> str:
    """
    Search active and support gems.

    Args:
        keyword:    Name/tag keyword — e.g. "lightning", "strike", "aoe", "channelling".
        gem_type:   "Attack", "Spell", or "" for all.
        is_support: true = support gems only, false = active gems only, null = all.
        tag:        Tag filter — e.g. "cold", "projectile", "melee", "duration".
        limit:      Max results.

    Returns:
        JSON array of gems with name, gem_type, is_support, tier, requirements,
        tags, tag_string, weapon_requirements.
    """
    return _to_json(_get_db().search_gems(keyword, gem_type, is_support, tag, limit))


@mcp.tool()
def search_uniques(slot: str = "", keyword: str = "",
                   base_type: str = "", limit: int = 20) -> str:
    """
    Search unique items.

    Args:
        slot:      PoB slot key — "gloves", "ring", "helmet", "body", "boots",
                   "amulet", "belt", "weapon1", "weapon2", "shield".
        keyword:   Search term in unique name or mod text — e.g. "rage",
                   "lightning", "power charge", "life leech".
        base_type: Filter by base type name — e.g. "Moulded Mitts".
        limit:     Max results.

    Returns:
        JSON array of uniques with name, slot, base_type, source, variants,
        and raw_text (full item text for use with equip_item()).
    """
    return _to_json(_get_db().search_uniques(slot, keyword, base_type, limit))


@mcp.tool()
def search_passive_nodes(keyword: str = "", node_type: str = "",
                         ascendancy: str = "", limit: int = 50) -> str:
    """
    Search passive tree nodes by stat or name keyword.

    Use this to discover what passives enhance a particular build goal —
    e.g. find all keystones, all Invoker ascendancy notables, or all nodes
    that provide lightning damage.

    Note: Jewel sockets can be filled from ANY class starting area if you path
    near them (see Timeless Jewels) — the agent should not assume jewel slots
    are class-locked.

    Args:
        keyword:    Stat or name keyword — e.g. "critical", "lightning damage",
                    "power charge", "energy shield", "evasion".
        node_type:  "Notable", "Keystone", "Normal", "JewelSocket", "ClassStart".
                    Leave blank for all types.
        ascendancy: Ascendancy name filter — e.g. "Invoker", "Warbringer",
                    "Stormweaver", "Infernalist". Leave blank for base tree.
        limit:      Max results (default 50).

    Returns:
        JSON array of nodes with node_id, name, node_type, ascendancy,
        is_jewel_socket, stats (array of stat strings), x, y, group_id.
    """
    return _to_json(_get_db().search_passive_nodes(keyword, node_type, ascendancy, limit=limit))


@mcp.tool()
def search_currencies(category: str = "", keyword: str = "") -> str:
    """
    List PoE2 currencies with their effects.

    Args:
        category: Filter by category — "Orb", "Quality", "Essence", "Rune",
                  "SoulCore", "Distilled", "Fragment", "Catalyst", "Other".
                  Leave blank to list all.
        keyword:  Substring search in name or effect description.

    Returns:
        JSON array of currencies with name, category, subcategory, effect,
        and trade_id (for price lookups).
    """
    return _to_json(_get_db().search_currencies(category, keyword))


@mcp.tool()
def get_db_summary() -> str:
    """
    Return row counts for all game data tables.

    Use this to verify the ETL has been run and data is available.
    Returns counts for: item_bases, item_mods, gems, uniques,
    passive_nodes, currencies.
    """
    return _to_json(_get_db().get_summary())


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
