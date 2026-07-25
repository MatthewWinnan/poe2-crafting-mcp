"""MCP Server — PoE2 Crafting & Build Advisor."""

import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from poe2_crafting_mcp.engine.pob_engine import PoBEngine

# ── Bootstrap ────────────────────────────────────────────────────────────────

POB_PATH = Path(os.environ.get("POB_PATH", Path(__file__).parent.parent.parent / "vendor" / "PathOfBuilding-PoE2"))

mcp: FastMCP = FastMCP("poe2-crafting")

# Single engine instance — PoB boots once per server lifetime.
_engine: PoBEngine | None = None


def _get_engine() -> PoBEngine:
    global _engine
    if _engine is None:
        _engine = PoBEngine(POB_PATH)
    return _engine


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


# ── Export ────────────────────────────────────────────────────────────────────

@mcp.tool()
def export_build_code() -> str:
    """
    Export the current build state as a PoB share code.

    Returns a JSON object with {"code": "<share_code>"}.
    The code can be imported into PoB or saved to a file.
    """
    return _to_json({"code": _get_engine().export_build_code()})


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
