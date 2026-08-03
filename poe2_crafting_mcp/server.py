"""MCP Server — PoE2 Crafting & Build Advisor."""

import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from poe2_crafting_mcp.engine.pob_engine import PoBEngine
from poe2_crafting_mcp.data.database import PoBDatabase
from poe2_crafting_mcp.data.economy import NinjaClient, EconomyError
from poe2_crafting_mcp.data.price_db import PriceDatabase

# ── Bootstrap ────────────────────────────────────────────────────────────────

POB_PATH = Path(os.environ.get("POB_PATH", Path(__file__).parent.parent / "vendor" / "PathOfBuilding-PoE2"))

mcp: FastMCP = FastMCP("poe2-crafting")

# Single engine instance — PoB boots once per server lifetime.
_engine: PoBEngine | None = None
_db: PoBDatabase | None = None
_price_db: PriceDatabase | None = None


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


def _get_price_db() -> PriceDatabase:
    global _price_db
    if _price_db is None:
        _price_db = PriceDatabase()
    return _price_db


def _to_json(obj: Any) -> str:
    """Serialise dataclasses / dicts / primitives to a compact JSON string."""
    def _default(o: Any) -> Any:
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        raise TypeError(f"Not serialisable: {type(o)}")
    return json.dumps(obj, default=_default, indent=2)


# ── MCP Resources: Crafting Knowledge Base ────────────────────────────────────

_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "guides"


@mcp.resource("poe2://crafting-guide/methods")
def crafting_guide_methods() -> str:
    """Crafting methods, currency orbs, and step-by-step crafting flow for PoE2."""
    return (_DOCS_DIR / "crafting-methods.md").read_text()


@mcp.resource("poe2://crafting-guide/modifiers")
def crafting_guide_modifiers() -> str:
    """How item modifiers work: prefixes, suffixes, tiers, ilvl, tags, local vs global."""
    return (_DOCS_DIR / "crafting-modifiers.md").read_text()


@mcp.resource("poe2://crafting-guide/corruption")
def crafting_guide_corruption() -> str:
    """Vaal Orb outcomes and corruption mechanics for items, gems, maps, and jewels."""
    return (_DOCS_DIR / "crafting-corruption.md").read_text()


@mcp.resource("poe2://crafting-guide/defences")
def crafting_guide_defences() -> str:
    """Layered defence system: avoidance, mitigation, HP, recovery. Attribute-defence mapping."""
    return (_DOCS_DIR / "crafting-defences.md").read_text()


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
def get_tree_jewels() -> str:
    """
    Get all jewels socketed in passive tree nodes.

    Returns each jewel with its passive tree node context so the agent knows
    WHERE in the tree the jewel sits (node name, ID, and approximate position).

    Returns:
        JSON list of:
        - node_id:    Passive tree node ID (use with set_tree_jewel/remove_tree_jewel)
        - node_name:  Display name of the jewel socket node on the tree
        - node_x/y:   Approximate position on the passive tree canvas
        - name:       Item name (unique name, or magic prefix/suffix combined)
        - base_type:  Base jewel type (e.g. "Viridian Jewel", "Cobalt Jewel")
        - corrupted:  Whether the jewel is corrupted
        - explicit_mods: List of mod strings on the jewel
    """
    return _to_json([vars(j) for j in _get_engine().get_tree_jewels()])


@mcp.tool()
def set_tree_jewel(node_id: int, item_text: str) -> str:
    """
    Socket a jewel into a passive tree node and return the stat delta.

    Use get_tree_jewels() to see current jewels and their node IDs.
    Use search_trade_listings(slot="jewel") to find jewels to test.

    Args:
        node_id:   Passive tree node ID to socket into.
                   Get valid IDs from get_tree_jewels() results.
        item_text: Jewel in PoB clipboard format, or item_text from a trade listing.

    Returns:
        JSON BuildStats (same shape as get_stats()) after the jewel is socketed.
    """
    return _to_json(vars(_get_engine().set_tree_jewel(node_id, item_text)))


@mcp.tool()
def remove_tree_jewel(node_id: int) -> str:
    """
    Remove the jewel from a passive tree node and return the stat delta.

    Args:
        node_id: Passive tree node ID to unsocket. Get from get_tree_jewels().

    Returns:
        JSON BuildStats after the jewel is removed.
    """
    return _to_json(vars(_get_engine().remove_tree_jewel(node_id)))


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
        stat_min, stat_max, req_level, group_name, mod_tags, weight_keys,
        and tier (1=best within group, use with search_trade_listings tier= param).
    """
    mods = _get_db().search_mods(keyword, item_tag, category, mod_type,
                                 min_level, max_level, limit)
    # Add tier numbers: position within each group_name (1=T1=best)
    group_count: dict[str, int] = {}
    result = []
    for m in mods:
        gn = m.get("group_name") or ""
        group_count[gn] = group_count.get(gn, 0) + 1
        result.append({**m, "tier": group_count[gn]})
    return _to_json(result)


@mcp.tool()
def get_craftable_mods(base_name: str, ilvl: int = 100,
                       pool: str = "normal", min_mod_level: int = 0) -> str:
    """
    Get all mods that can roll on a base item with real spawn weights.

    Shows the full mod pool with probabilities for crafting planning.
    Use this to determine: what mods are available, how likely each is,
    and whether alt-spamming vs essence vs trade is better value.

    Args:
        base_name: Base item name (e.g. "Gold Gloves", "Vaal Regalia")
                   or poe2db item class slug (e.g. "Gloves_int", "Amulets").
        ilvl:      Item level — determines which mod tiers are available.
                   Higher ilvl = more/better tiers eligible. Default 100.
        pool:      Mod pool — "normal" (default, standard crafting),
                   "marksman" (Kolr's Hunt influence),
                   "decay" (Katla's Gloom influence),
                   "essence" (essence-guaranteed mods),
                   "desecrated" (abyss desecrated mods).
        min_mod_level: Minimum mod tier level. Used by Greater/Perfect currencies:
                   0 = regular orbs (all tiers), 35 = Greater Regal/Chaos/Exalted,
                   44 = Greater Transmute/Augment, 50 = Perfect Regal/Chaos/Exalted,
                   70 = Perfect Transmute/Augment.

    Returns:
        JSON with: item_class, ilvl, pool, min_mod_level,
        prefixes (list of {family, family_weight, tiers: [{stat_text, weight, req_level}]}),
        suffixes (same structure),
        total_prefix_weight, total_suffix_weight, prefix_count, suffix_count.

        Each tier competes independently in the pool.
        P(specific tier) = tier_weight / total_pool_weight.
        P(any tier in family) = family_weight / total_pool_weight.
    """
    from poe2_crafting_mcp.data.poe2db_client import base_tags_to_item_class, ALL_ITEM_CLASSES
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase()

    # Resolve base_name to item_class
    item_class = None
    item_slot = None
    if base_name in ALL_ITEM_CLASSES:
        item_class = base_name
    else:
        try:
            db = _get_db()
            bases = db.search_bases(keyword=base_name, limit=1)
            if bases:
                item_slot = bases[0]['slot']
                item_class = base_tags_to_item_class(
                    bases[0]['slot'], bases[0].get('tags', []))
        except Exception:
            pass

    if not item_class:
        item_class = base_name.replace(' ', '_')

    result = pdb.get_craftable_mods(item_class, ilvl, pool,
                                    min_mod_level=min_mod_level)

    # Include essence-guaranteed mods when showing normal pool
    if pool == "normal" and item_slot:
        try:
            from poe2_crafting_mcp.crafting.essence_resolver import EssenceResolver
            resolver = EssenceResolver(os.environ.get("POE2_DB", "data/poe2_craft.db"))
            ess_mods = resolver.list_for_slot(item_slot)
            result["essence_mods"] = [
                {
                    "essence_name": m.essence_name,
                    "tier": m.tier,
                    "base_name": m.base_name,
                    "effect_type": m.effect_type,
                    "item_slots": m.item_slots,
                    "stat_text": m.stat_text,
                    "stat_min": m.stat_min,
                    "stat_max": m.stat_max,
                }
                for m in ess_mods
            ]
        except Exception:
            pass

    return _to_json(result)


@mcp.tool()
def get_desecrated_mods(base_name: str, ilvl: int = 100) -> str:
    """
    Get abyss desecrated mods available for an item base.

    These are the special mods added by Altered Collarbone (and other abyss
    jewels) via the desecration mechanic. Different from normal crafting mods.

    Args:
        base_name: Base item name or poe2db item class slug.
        ilvl:      Item level (default 100).

    Returns:
        Same structure as get_craftable_mods with pool="desecrated".
    """
    return get_craftable_mods(base_name, ilvl, pool="desecrated")


@mcp.tool()
def get_essence_mods(base_name: str, ilvl: int = 100) -> str:
    """
    Get essence-guaranteed mods for an item base.

    When using an Essence on an item, one mod slot is guaranteed to be
    the essence mod. These are the available essence mods for this base.

    Args:
        base_name: Base item name or poe2db item class slug.
        ilvl:      Item level (default 100).

    Returns:
        Same structure as get_craftable_mods with pool="essence".
    """
    return get_craftable_mods(base_name, ilvl, pool="essence")


@mcp.tool()
def get_influence_mods(base_name: str, influence: str, ilvl: int = 100) -> str:
    """
    Get influence-specific mods for an item base (Kolr's Hunt, Katla's Gloom, etc.).

    These mods only roll when the corresponding Game Warp Rune is socketed.

    Args:
        base_name: Base item name or poe2db item class slug.
        influence: Influence type — "marksman" (Kolr's Hunt),
                   "decay" (Katla's Gloom), "chronomancy" (Uhtred's Sidereus),
                   "destruction" (Thrud's Might), "berserking" (Vorana's Carnage),
                   "soul" (Medved's Tending).
        ilvl:      Item level (default 100).

    Returns:
        Same structure as get_craftable_mods with the specified influence pool.
    """
    return get_craftable_mods(base_name, ilvl, pool=influence)


@mcp.tool()
def estimate_craft_cost(
    base_name: str,
    target_mod: str,
    currency: str = "exalted",
    ilvl: int = 82,
    target_tier: int = 0,
    omen: str = "",
    currency_price: float = 0,
    omen_price: float = 0,
) -> str:
    """
    Estimate the expected cost to hit a target mod on an item.

    Calculates probability, expected attempts, and cost for a specific
    crafting currency applied to a base item targeting a specific mod family.

    Args:
        base_name: Base item name or poe2db slug (e.g. "Gold Gloves", "Boots_int")
        target_mod: Mod family to target (e.g. "IncreasedLife", "LocalIncreasedEnergyShield").
                    Use get_craftable_mods() to find available family names.
        currency: Currency to use — "transmute", "augment", "regal", "exalted", "chaos",
                  "greater_transmute", "greater_exalted", "perfect_transmute", etc.
        ilvl: Item level (default 82 — unlocks all tiers for most mods)
        target_tier: 0 = any tier in family (default), N = specific tier only
        omen: Optional omen — "sinistral_exaltation", "dextral_coronation", etc.
        currency_price: Price per currency use in chaos equivalent (0 = use default)
        omen_price: Price of omen in chaos (0 = not used)

    Returns:
        JSON with: probability, probability_pct, expected_attempts, expected_cost,
        target_weight, total_weight, available_pool_size, currency, omen
    """
    from poe2_crafting_mcp.data.poe2db_client import base_tags_to_item_class, ALL_ITEM_CLASSES
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.crafting.simulator import CraftingSimulator

    pdb = PriceDatabase()

    # Resolve item class
    item_class = None
    if base_name in ALL_ITEM_CLASSES:
        item_class = base_name
    else:
        try:
            db = _get_db()
            bases = db.search_bases(keyword=base_name, limit=1)
            if bases:
                item_class = base_tags_to_item_class(
                    bases[0]['slot'], bases[0].get('tags', []))
        except Exception:
            pass
    if not item_class:
        item_class = base_name.replace(' ', '_')

    # Get mod pool
    mod_pool = pdb.get_craftable_mods(item_class, ilvl, "normal")

    # Create simulator and calculate
    sim = CraftingSimulator(item_class, ilvl, mod_pool)
    result = sim.estimate_cost(
        target_family=target_mod,
        currency=currency,
        omen=omen,
        target_tier=target_tier,
        currency_price=currency_price or 1.0,
        omen_price=omen_price,
    )
    result['item_class'] = item_class
    result['ilvl'] = ilvl
    result['target_mod'] = target_mod
    return _to_json(result)


@mcp.tool()
def compare_craft_methods(
    base_name: str,
    target_mod: str,
    ilvl: int = 82,
    target_tier: int = 0,
) -> str:
    """
    Compare multiple crafting methods for hitting a target mod.

    Shows which currency/method is cheapest to hit the desired mod,
    accounting for pool narrowing with Greater/Perfect currencies.

    Args:
        base_name: Base item name or poe2db slug
        target_mod: Mod family to target (e.g. "IncreasedLife")
        ilvl: Item level (default 82)
        target_tier: 0 = any tier, N = specific tier

    Returns:
        JSON list of methods sorted by expected_cost (cheapest first),
        each with: currency, probability_pct, expected_attempts, expected_cost
    """
    from poe2_crafting_mcp.data.poe2db_client import base_tags_to_item_class, ALL_ITEM_CLASSES
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.crafting.simulator import CraftingSimulator

    pdb = PriceDatabase()

    # Resolve item class
    item_class = None
    if base_name in ALL_ITEM_CLASSES:
        item_class = base_name
    else:
        try:
            db = _get_db()
            bases = db.search_bases(keyword=base_name, limit=1)
            if bases:
                item_class = base_tags_to_item_class(
                    bases[0]['slot'], bases[0].get('tags', []))
        except Exception:
            pass
    if not item_class:
        item_class = base_name.replace(' ', '_')

    mod_pool = pdb.get_craftable_mods(item_class, ilvl, "normal")
    sim = CraftingSimulator(item_class, ilvl, mod_pool)

    results = sim.compare_methods(
        target_family=target_mod,
        target_tier=target_tier,
    )
    return _to_json({"item_class": item_class, "target_mod": target_mod,
                     "ilvl": ilvl, "methods": results})


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
def search_essences(
    keyword: str = "",
    tier: str = "",
    base_name: str = "",
    item_slots: str = "",
    limit: int = 20,
) -> str:
    """
    Search the essence database for crafting information.

    Each essence guarantees a specific mod when applied to an item.
    Results show the guaranteed mod per applicable item slot.

    Tiers:
      - Lesser/Normal: Normal → Magic with 1 guaranteed mod
      - Greater: Magic → Rare with guaranteed mod + random fill
      - Perfect: removes 1 random mod, adds 1 guaranteed (Rare only)
      - Corrupted: special essence-only mods (Hysteria, Horror, etc.)
      - Alloy: special mods (Runic Alloy, Prismatic Alloy, etc.)

    Args:
        keyword:    Search name, stat text, or item slots (e.g. "fire", "life", "attack speed")
        tier:       Filter by tier: "Lesser", "Normal", "Greater", "Perfect", "Corrupted", "Alloy"
        base_name:  Filter by essence base type: "Body", "Flames", "Seeking", etc.
        item_slots: Filter by applicable slots (e.g. "Weapon", "Armour", "Belt")
        limit:      Max results (default 20)

    Returns:
        JSON array of {name, tier, base_name, effect_type, item_slots, stat_text, stat_min, stat_max}
    """
    return _to_json(_get_db().search_essences(keyword, tier, base_name, item_slots, limit))


@mcp.tool()
def resolve_essence(
    essence_name: str = "",
    base_name: str = "",
    tier: str = "",
    item_slot: str = "",
) -> str:
    """
    Resolve what mod an essence gives on a specific item slot.

    Either provide essence_name (full name) OR base_name + tier.
    Always provide item_slot.

    Args:
        essence_name: Full name like "Greater Essence of the Body"
        base_name:    Base name like "Body", "Haste" (use with tier)
        tier:         "Lesser", "Normal", "Greater", "Perfect" (use with base_name)
        item_slot:    Item slot from item_bases: "Gloves", "Bow", "Body Armour", etc.

    Returns:
        JSON with essence mod details including stat_text, stat_min, stat_max,
        or error if essence doesn't apply to this slot.
    """
    from poe2_crafting_mcp.crafting.essence_resolver import EssenceResolver
    resolver = EssenceResolver(os.environ.get("POE2_DB", "data/poe2_craft.db"))

    if essence_name and item_slot:
        mod = resolver.resolve(essence_name, item_slot)
    elif base_name and tier and item_slot:
        mod = resolver.resolve_by_base(base_name, tier, item_slot)
    else:
        return _to_json({"error": "Provide (essence_name + item_slot) or (base_name + tier + item_slot)"})

    if not mod:
        return _to_json({"error": f"Essence does not apply to slot '{item_slot}'"})

    return _to_json(dataclasses.asdict(mod))


@mcp.tool()
def list_essences_for_slot(
    item_slot: str,
    tier: str = "",
) -> str:
    """
    List all essences available for a given item slot.

    Args:
        item_slot: Item slot: "Gloves", "Bow", "Body Armour", "Ring", etc.
        tier:      Optional filter: "Lesser", "Normal", "Greater", "Perfect"

    Returns:
        JSON array of essence mods available for this slot.
    """
    from poe2_crafting_mcp.crafting.essence_resolver import EssenceResolver
    resolver = EssenceResolver(os.environ.get("POE2_DB", "data/poe2_craft.db"))
    mods = resolver.list_for_slot(item_slot, tier)
    return _to_json([dataclasses.asdict(m) for m in mods])


@mcp.tool()
def get_db_summary() -> str:
    """
    Return row counts for all game data tables.

    Use this to verify the ETL has been run and data is available.
    Returns counts for: item_bases, item_mods, gems, uniques,
    passive_nodes, currencies.
    """
    return _to_json(_get_db().get_summary())


@mcp.tool()
def search_concepts(keyword: str = "", category: str = "", limit: int = 10) -> str:
    """
    Look up PoE2 keyword and mechanic definitions from the live DB.

    Covers ~200 core concepts including: damage types, ailments (Shock/Chill/Freeze/
    Ignite/Bleed/Poison/Electrocute and lesser ailments), attributes (Strength/
    Dexterity/Intelligence), defence mechanics (Armour formula, Evasion, Energy Shield,
    Ward, Block, Suppress, Deflect, Resistances), offence mechanics (Critical Hits,
    Accuracy, Leech, Penetration, Conversion, Culling Strike), charges (Power/Frenzy/
    Endurance), resources (Life/Mana/Spirit/Rage), buffs (Onslaught/Elusive/Tailwind),
    debuffs (Exposure/Blind/Crushed/Maim/Curses/Withered), combat mechanics (Combo/
    Finisher/Parry/Exerted Attack/Armour Break/Trinity/Resonance), skill keywords
    (Attack/Spell/Melee/Projectile/Aura/Herald/Trap/Mine/Warcry/Invocation),
    keystones (Chaos Inoculation/Iron Reflexes/Eldritch Battery/Blood Magic etc.).

    Each concept includes:
    - summary: plain English one-liner
    - mechanics: detailed explanation with PoE2-accurate rules
    - formula: numeric formula where applicable (e.g. Armour reduction, Freeze buildup)
    - see_also: related concepts AND PoB config var names for cross-referencing
    - source: "manual" | "PoB:ConfigOptions" | "PoB:SkillTypes" | "PoB:Gems" | "poe2wiki"
    - updated_at: ISO datetime of last update

    Args:
        keyword:  Search term — e.g. "shock", "armour", "critical", "leech", "rage".
                  Searched across name, summary, mechanics fields.
        category: Narrow by category — one of: damage_type, ailment, attribute,
                  defence, offence, charge, resource, buff, debuff, mechanic,
                  keyword, keystone, projectile, ground.
        limit:    Max results (default 10).

    Returns:
        JSON array of matching concept dicts.
    """
    pdb = _get_price_db()
    return _to_json(pdb.search_concepts(keyword=keyword, category=category, limit=limit))


@mcp.tool()
def get_concept(name: str) -> str:
    """
    Fetch the exact definition for a single PoE2 keyword by name (from DB).

    Use search_concepts() first if you're not sure of the exact name.

    Args:
        name: Concept name — e.g. "Shock", "Armour", "Power Charge", "Iron Reflexes".

    Returns:
        JSON with name, category, summary, mechanics, formula, see_also, source, updated_at.
        Returns {"error": "..."} if not found.
    """
    pdb = _get_price_db()
    result = pdb.get_concept(name)
    if not result:
        return _to_json({"error": f"Concept '{name}' not found"})
    return _to_json(result)


@mcp.tool()
def update_concept(
    name: str,
    category: str = "",
    summary: str = "",
    mechanics: str = "",
    formula: str = "",
    see_also: str = "[]",
    source: str = "manual",
    league_version: str = "",
) -> str:
    """
    Insert or update a single PoE2 concept in the DB.

    Use this to add league-specific entries, correct existing definitions, or
    add knowledge not yet in the seed data. Changes survive server restarts.

    Args:
        name:          Concept name (primary key) — e.g. "Delirium Mirror".
        category:      Category — e.g. "mechanic", "ailment", "keyword", "keystone".
        summary:       One-sentence plain-English description.
        mechanics:     Full mechanics explanation (PoE2-accurate).
        formula:       Numeric formula if applicable, else "".
        see_also:      JSON array of related concept names / PoB vars — e.g. '["Freeze","Chill"]'.
        source:        Source tag — "manual" | "poe2wiki" | "PoB:ConfigOptions" etc.
        league_version: League name if league-specific (e.g. "Settlers"), or "" for all leagues.

    Returns:
        JSON with {ok: true, name} on success or {error: ...} on failure.
    """
    pdb = _get_price_db()
    try:
        see_also_list = json.loads(see_also) if see_also else []
        pdb.upsert_concept(
            name=name,
            category=category,
            summary=summary,
            mechanics=mechanics,
            formula=formula,
            see_also=see_also_list,
            source=source,
            league_version=league_version or None,
        )
        return _to_json({"ok": True, "name": name})
    except Exception as e:
        return _to_json({"error": str(e)})


@mcp.tool()
def refresh_concepts() -> str:
    """
    Re-seed the concepts table from the built-in concepts.py definitions.

    Use this after a software update that adds new concepts, or to reset manual
    edits to built-in concepts. Custom concepts with source="manual" are preserved
    (upsert semantics — only built-in entries are overwritten).

    Returns:
        JSON with {seeded, total, status} where seeded = number of rows written.
    """
    pdb = _get_price_db()
    from poe2_crafting_mcp.data.concepts import CONCEPTS
    seeded = pdb.upsert_concepts_bulk(CONCEPTS, overwrite=False)
    status = pdb.concept_status()
    return _to_json({"seeded": seeded, **status})


@mcp.tool()
def get_item_description(name: str) -> str:
    """
    Fetch crafting context and description for a specific item by name.

    Covers key bases (Gold Gloves, Vaal Regalia, Imbued Wand, etc.), currencies
    (Orb of Alteration, Essence, Fracture Orb, etc.), runes, catalysts, and
    mechanic items. Returns crafting notes (best ilvl, target mods, which method
    to use) and drop notes alongside a plain-English description.

    Use alongside search_bases() to get both game stats and crafting context.
    Add custom entries with poe2-lookup item-desc-add or update_item_description().

    Args:
        name: Item name — e.g. "Gold Gloves", "Orb of Alteration", "Stygian Vise".

    Returns:
        JSON with name, category, description, crafting_notes, drop_notes, see_also,
        source, updated_at. Returns {"error": "..."} if not found.
    """
    pdb = _get_price_db()
    from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
    result = pdb.get_item_desc_or_fetch(name, wiki_client=Poe2WikiClient())
    if not result:
        return _to_json({"error": f"No description for '{name}' (not in cache or wiki)"})
    return _to_json(result)


@mcp.tool()
def update_item_description(
    name: str,
    category: str,
    description: str = "",
    crafting_notes: str = "",
    drop_notes: str = "",
    see_also: str = "[]",
    source: str = "manual",
    league_version: str = "",
) -> str:
    """
    Insert or update an item description in the DB.

    Use to add crafting context for items not yet in the seed data, or to
    correct existing entries. Changes persist across server restarts.

    Args:
        name:           Item name (primary key).
        category:       "base" | "currency" | "gem" | "unique" | "mechanic_item".
        description:    Plain-English description of what the item is.
        crafting_notes: When/how to use in crafting, best ilvl targets, etc.
        drop_notes:     Where it drops / how to obtain.
        see_also:       JSON array of related item/concept names.
        source:         Source tag — "manual" | "poe2wiki" | "poe2db".
        league_version: League name if league-specific, or "" for all leagues.

    Returns:
        JSON with {ok: true, name} on success or {error: ...} on failure.
    """
    pdb = _get_price_db()
    try:
        see_also_list = json.loads(see_also) if see_also else []
        pdb.upsert_item_desc(
            name=name, category=category,
            description=description,
            crafting_notes=crafting_notes,
            drop_notes=drop_notes,
            see_also=see_also_list,
            source=source,
            league_version=league_version or None,
        )
        return _to_json({"ok": True, "name": name})
    except Exception as e:
        return _to_json({"error": str(e)})


@mcp.tool()
def refresh_item_descriptions() -> str:
    """
    Re-seed mechanic concept entries (Jewellery, Focus, Idol, Rune, etc.)
    from the built-in item_descriptions.py.

    Individual item descriptions (currencies, bases) are sourced from poe2wiki.net
    and cached automatically on first access. To bulk-seed those, run:
        poe2-lookup item-desc-seed   (requires internet, ~1–2 min)

    Returns:
        JSON with {seeded, total, status}.
    """
    pdb = _get_price_db()
    from poe2_crafting_mcp.data.item_descriptions import ITEM_DESCRIPTIONS
    seeded = pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)
    status = pdb.item_desc_status()
    return _to_json({"seeded": seeded, **status})


# ── Economy & Pricing ────────────────────────────────────────────────────────


@mcp.tool()
def get_data_status() -> str:
    """
    Return the freshness status of all data sources.

    Call this at the start of any session to understand what needs updating
    before running build analysis or price lookups.

    Returns a JSON object with:
    - active_league: the league currently configured (or null if not set)
    - prices: {league, age_minutes, status} where status is one of:
        "fresh" | "stale_ttl" | "stale_league" | "missing"
    - etl: {league, age_days, status} where status is one of:
        "fresh" | "stale_age" | "stale_league" | "never_run"
    - concepts: {status, total, age_days} where status is one of:
        "fresh" | "stale" | "never_seeded"

    If prices.status != "fresh", call refresh_prices().
    If etl.status != "fresh", warn the user and offer to call refresh_etl().
    If concepts.status != "fresh", call refresh_concepts().
    """
    pdb = _get_price_db()
    active_league = pdb.get_active_league()
    if not active_league:
        # Auto-detect so we can compute staleness accurately
        try:
            active_league = NinjaClient().get_current_league()
            pdb.set_active_league(active_league)
        except EconomyError:
            active_league = None

    result: dict = {"active_league": active_league}
    if active_league:
        result["prices"] = pdb.price_cache_status(active_league)
        result["etl"] = pdb.etl_status(active_league)
    else:
        result["prices"] = {"status": "unknown", "note": "Could not reach poe.ninja to detect league"}
        result["etl"] = {"status": "unknown"}
    result["concepts"] = pdb.concept_status()
    result["item_descriptions"] = pdb.item_desc_status()
    result["mod_weights"] = pdb.mod_weight_status()
    return _to_json(result)


@mcp.tool()
def set_active_league(league: str = "") -> str:
    """
    Set the league for price lookups and freshness tracking.

    Args:
        league: League name (e.g. "Dawn of the Hunt"). Leave blank to
                auto-detect the current challenge league from poe.ninja.

    Returns:
        JSON with {active_league, prices_status, etl_status}.
    """
    pdb = _get_price_db()
    client = NinjaClient()

    if not league:
        try:
            league = client.get_current_league()
        except EconomyError as e:
            return _to_json({"error": str(e)})

    pdb.set_active_league(league)
    return _to_json({
        "active_league": league,
        "prices": pdb.price_cache_status(league),
        "etl": pdb.etl_status(league),
    })


@mcp.tool()
def refresh_prices(league: str = "") -> str:
    """
    Fetch fresh prices from poe.ninja and update the local cache.

    Fetches: currencies, fragments, unique items (all slots), base items,
    and skill gems. Takes 5-10 seconds (one HTTP call per category).

    Args:
        league: League name. Leave blank to use the active league (or
                auto-detect from poe.ninja if not yet set).

    Returns:
        JSON with {league, categories_fetched, total_prices, duration_seconds}.
    """
    import time
    pdb = _get_price_db()
    client = NinjaClient()

    if not league:
        league = pdb.get_active_league() or ""
    if not league:
        try:
            league = client.get_current_league()
        except EconomyError as e:
            return _to_json({"error": str(e)})

    pdb.set_active_league(league)

    from poe2_crafting_mcp.data.currencies import CURRENCIES
    from poe2_crafting_mcp.data.economy import GENERAL_ITEM_TYPES
    _CURRENCY_EXCHANGE_CATS = {"Orb", "Quality", "Other"}
    trade_ids = [c[4] for c in CURRENCIES if c[4] and c[1] in _CURRENCY_EXCHANGE_CATS]

    t0 = time.monotonic()
    try:
        rows = client.fetch_currency_rates(league, trade_ids)
    except EconomyError as e:
        return _to_json({"error": str(e)})

    pdb.upsert_prices(rows, league)

    # Find divine rate for chaos conversion
    divine_row = next((r for r in rows if r.get("trade_id") == "divine-orb"), None)
    divine_chaos = divine_row["chaos_value"] if divine_row else None

    # ── General exchange categories (one overview call each) ─────────────────
    categories_fetched = ["currency"]
    total_general = 0
    for item_type, label in GENERAL_ITEM_TYPES:
        try:
            gen_rows = client.fetch_exchange_category(league, item_type)
        except EconomyError:
            gen_rows = []
        if gen_rows:
            pdb.upsert_prices(gen_rows, league)
            total_general += len(gen_rows)
            categories_fetched.append(f"{label} ({len(gen_rows)})")

    if total_general:
        pdb.fill_chaos_from_divine(league)

    duration = round(time.monotonic() - t0, 2)
    return _to_json({
        "league": league,
        "categories_fetched": categories_fetched,
        "total_prices": len(rows) + total_general,
        "duration_seconds": duration,
        "divine_chaos_rate": divine_chaos,
        "note": "Unique item prices not available via poe.ninja PoE2 API.",
    })


@mcp.tool()
def refresh_etl() -> str:
    """
    Re-run the full ETL pipeline to rebuild game data from the PoB submodule.

    This takes 1-3 minutes and requires the PoB engine. It rebuilds item bases,
    mods, gems, uniques, passive nodes, and currencies from the PoB vendor data.

    Use this when:
    - get_data_status() shows etl.status = "stale_league" or "stale_age"
    - The PoB submodule has been updated (git submodule update)
    - New game content is missing from search results

    Returns:
        JSON with {ran_at, row_counts, duration_seconds}.
    """
    import time
    from poe2_crafting_mcp.data.etl import run as etl_run

    pdb = _get_price_db()
    active_league = pdb.get_active_league()

    t0 = time.monotonic()
    try:
        counts = etl_run()
    except Exception as e:
        return _to_json({"error": f"ETL failed: {e}"})

    duration = round(time.monotonic() - t0, 2)
    ran_at = pdb._now_iso()

    # Record ETL completion in economy_meta
    pdb.set_meta("etl_ran_at", ran_at)
    if active_league:
        pdb.set_meta("etl_league", active_league)

    return _to_json({
        "ran_at": ran_at,
        "league": active_league,
        "row_counts": counts,
        "duration_seconds": duration,
    })


@mcp.tool()
def get_item_price(name: str, category: str = "", league: str = "") -> str:
    """
    Look up the current market price for an item.

    Searches the local price cache (refreshed by refresh_prices()).
    If no exact match, falls back to substring search.

    Args:
        name:     Item name — e.g. "Kaom's Heart", "Titan Greaves",
                  "Divine Orb", "Ice Nova".
        category: Optional filter — "unique", "base", "gem", "currency",
                  "fragment". Leave blank to search all categories.
        league:   League name. Defaults to the active league.

    Returns:
        JSON with name, category, chaos_value, divine_value, listing_count,
        league, fetched_at. Returns a list if multiple matches found.
        Returns {"error": "..."} if nothing found — call refresh_prices() first.
    """
    pdb = _get_price_db()

    if not league:
        league = pdb.get_active_league() or ""
    if not league:
        return _to_json({"error": "No active league set. Call set_active_league() or refresh_prices() first."})

    # Exact match first
    hit = pdb.get_price(name, league, category)
    if hit:
        return _to_json(hit)

    # Substring search
    results = pdb.search_prices(name, league, category, limit=10)
    if not results:
        return _to_json({
            "error": f"No prices found for '{name}' in league '{league}'.",
            "hint": "Call refresh_prices() to populate the cache, or check the item name spelling.",
        })
    if len(results) == 1:
        return _to_json(results[0])
    return _to_json(results)


@mcp.tool()
def get_currency_rate(name: str, league: str = "") -> str:
    """
    Get the chaos and divine value of a currency or fragment.

    Useful for estimating craft costs: multiply the currency quantity
    needed by its chaos value to get total chaos cost.

    Args:
        name:   Currency name — e.g. "Divine Orb", "Orb of Alteration",
                "Lesser Essence of Electricity", "Chaos Orb".
        league: League name. Defaults to the active league.

    Returns:
        JSON with name, category, chaos_value, divine_value, listing_count,
        league, fetched_at.
        Returns {"error": "..."} if not found — call refresh_prices() first.
    """
    pdb = _get_price_db()

    if not league:
        league = pdb.get_active_league() or ""
    if not league:
        return _to_json({"error": "No active league set. Call set_active_league() or refresh_prices() first."})

    # Try currency first, then fragment
    for cat in ("currency", "fragment", ""):
        hit = pdb.get_price(name, league, cat)
        if hit:
            return _to_json(hit)

    # Substring fallback
    results = pdb.search_prices(name, league, limit=5)
    if not results:
        return _to_json({
            "error": f"Currency '{name}' not found in league '{league}'.",
            "hint": "Call refresh_prices() to populate the cache.",
        })
    return _to_json(results[0] if len(results) == 1 else results)


@mcp.tool()
def get_bulk_prices(category: str, league: str = "") -> str:
    """
    Return all cached prices for a category.

    Use this to survey all items in a category at once — e.g. all currencies
    to compare craft material costs, or all gems to find upgrade opportunities.

    Args:
        category: Required — one of: "currency", "fragment", "unique",
                  "base", "gem".
        league:   League name. Defaults to the active league.

    Returns:
        JSON array of price objects sorted by listing_count descending.
        Returns {"error": "..."} if cache is empty — call refresh_prices() first.
    """
    valid = {"currency", "fragment", "unique", "base", "gem"}
    if category not in valid:
        return _to_json({"error": f"category must be one of: {sorted(valid)}"})

    pdb = _get_price_db()

    if not league:
        league = pdb.get_active_league() or ""
    if not league:
        return _to_json({"error": "No active league set. Call set_active_league() or refresh_prices() first."})

    results = pdb.get_bulk_prices(category, league)
    if not results:
        return _to_json({
            "error": f"No '{category}' prices cached for league '{league}'.",
            "hint": "Call refresh_prices() to populate the cache.",
        })
    return _to_json(results)


@mcp.tool()
def refresh_trade_stats() -> str:
    """
    Fetch and cache the full trade stat ID list from the GGG trade2 API.

    Call this once per session (or when the cache is empty) before using
    search_trade_listings(). The cache persists across sessions in poe2_craft.db.

    Fetches ~6000 stat entries covering explicit, implicit, pseudo, enchant,
    and other stat types. Takes ~1-2 seconds.

    Returns:
        JSON with {total_stats, by_type: {explicit: N, ...}, cached_at}.
    """
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError

    try:
        stats = TradeClient().fetch_stats()
    except TradeError as e:
        return _to_json({"error": str(e)})

    pdb = _get_price_db()
    n = pdb.upsert_trade_stats(stats)

    by_type: dict[str, int] = {}
    for s in stats:
        by_type[s["stat_type"]] = by_type.get(s["stat_type"], 0) + 1

    return _to_json({
        "total_stats": n,
        "by_type": by_type,
        "cached_at": pdb.trade_stats_fetched_at(),
    })


@mcp.tool()
def search_trade_stats(
    keyword: str,
    stat_type: str = "",
    slot: str = "",
    limit: int = 10,
) -> str:
    """
    Look up trade stat IDs by keyword from the local cache.

    Use this to find the exact stat ID(s) needed for extra_stats or stat_groups
    in search_trade_listings(). No HTTP call — reads from the local cache only.

    Prerequisite: call refresh_trade_stats() at least once.

    Args:
        keyword:   Keyword to search — "maximum life", "lightning damage", etc.
        stat_type: Filter by stat type — "explicit", "implicit", "pseudo",
                   "fractured", "enchant", "desecrated", etc. Empty = all types.
        slot:      Item slot hint — used to prefer (Local) variants for armour/weapons.
                   E.g. "gloves" prefers "# to maximum Energy Shield (Local)" over global.
        limit:     Max results (default 10).

    Returns:
        JSON list of [{stat_id, stat_text, stat_type}] sorted by relevance.

    Example workflow:
        search_trade_stats("maximum life")
        → [{"stat_id": "explicit.stat_3299347043", "stat_text": "+# to maximum Life", ...}]

        search_trade_stats("energy shield", slot="gloves")
        → [{"stat_id": "explicit.stat_4052037485", "stat_text": "# to maximum Energy Shield (Local)", ...}]

        Then use the stat_id in search_trade_listings():
        search_trade_listings(
            stat_name="energy shield", slot="gloves", tier=1,
            extra_stats=[{"id": "explicit.stat_3299347043", "min": 80}]
        )
    """
    pdb = _get_price_db()
    if pdb.trade_stats_count() == 0:
        return _to_json({
            "error": "Trade stat cache is empty. Call refresh_trade_stats() first.",
            "results": [],
        })

    _armour_weapon_slots = {
        "gloves", "boots", "helmet", "helm", "body armour", "body", "chest",
        "shield", "focus", "buckler", "sword", "axe", "mace", "flail",
        "bow", "staff", "crossbow", "wand", "sceptre", "dagger", "claw",
        "spear", "quarterstaff", "warstaff", "talisman",
    }
    prefer_local = slot.lower() in _armour_weapon_slots

    matches = pdb.search_trade_stats(
        keyword, stat_type=stat_type or None, limit=limit, prefer_local=prefer_local
    )
    if not matches and stat_type:
        matches = pdb.search_trade_stats(keyword, limit=limit, prefer_local=prefer_local)

    return _to_json({
        "results": [
            {"stat_id": m["stat_id"], "stat_text": m["stat_text"], "stat_type": m.get("stat_type", "")}
            for m in matches
        ],
        "total": len(matches),
        "hint": "Use stat_id in extra_stats=[{\"id\": \"...\", \"min\": N}] or stat_groups.",
    })


@mcp.tool()
def search_trade_listings(
    stat_name: str,
    slot: str = "",
    rarity: str = "magic",
    min_value: float | None = None,
    max_value: float | None = None,
    tier: int | None = None,
    ilvl_min: int = 80,
    ilvl_max: int | None = None,
    stat_type: str = "explicit",
    league: str = "",
    # Multi-stat parameters
    extra_stats: list[dict] | None = None,
    stats_type: str = "and",
    stats_min_count: int | None = None,
    stat_groups: list[dict] | None = None,
    # Item property filters
    corrupted: bool | None = None,
    fractured_item: bool | None = None,
    identified: bool | None = None,
    mirrored: bool | None = None,
    quality_min: int | None = None,
    quality_max: int | None = None,
    rune_sockets_min: int | None = None,
    # Equipment stat filters
    ar_min: int | None = None,
    ev_min: int | None = None,
    es_min: int | None = None,
    dps_min: float | None = None,
    pdps_min: float | None = None,
    edps_min: float | None = None,
    aps_min: float | None = None,
    # Gem filters
    gem_level_min: int | None = None,
    gem_level_max: int | None = None,
    # Map filters
    map_tier_min: int | None = None,
    map_tier_max: int | None = None,
    map_iir_min: int | None = None,
    map_packsize_min: int | None = None,
    # Trade filters
    indexed: str | None = None,
    price_max: float | None = None,
    price_currency: str | None = None,
    account: str | None = None,
    # Client-side filters (not supported by trade2 API, applied post-fetch)
    affix_filter: str | None = None,
    affix_count_min: int | None = None,
    affix_count_max: int | None = None,
) -> str:
    """
    Search the GGG trade site for items with a specific mod/stat.

    Primary tool for finding items to buy based on desired stats.
    Examples:
    - "Find the cheapest magic gloves with T1 energy shield"
    - "Find rare rings with at least 80 max life"
    - "Find fractured boots with T1 movement speed (crafting base)"
    - "Find uncorrupted magic helmets with T1 ES, listed in the last day"

    Prerequisite: call refresh_trade_stats() at least once per session if
    the cache is empty (check via get_data_status()).

    Workflow:
        1. refresh_trade_stats()            # once per session
        2. search_mods("energy shield")     # optional: check tier values in game DB
        3. search_trade_listings(           # live trade search
               stat_name="energy shield",
               slot="gloves",
               rarity="magic",
               tier=1                      # auto-looks up T1 min from game DB
           )

    Multi-stat example (all stats in one query):
        search_trade_listings(
            stat_name="energy shield", slot="gloves", tier=1,
            extra_stats=[{"id": "explicit.stat_XXXX", "min": 30}],
            stats_type="and"
        )

    Stat groups example (N of M matching):
        search_trade_listings(
            stat_name="",  # ignored when stat_groups provided
            stat_groups=[
                {"type": "count", "min_count": 2, "filters": [
                    {"id": "explicit.stat_A", "min": 30},
                    {"id": "explicit.stat_B", "min": 20},
                    {"id": "explicit.stat_C", "min": 15},
                ]},
            ]
        )

    Args:
        stat_name:      Stat keyword — "energy shield", "maximum life", "cold resistance", etc.
                        Matched against the trade stat ID cache. Can be empty if stat_groups used.
        slot:           Item slot — "gloves", "boots", "helmet", "ring", "amulet", "belt",
                        "body armour", "shield", "focus", "buckler", "spear", "staff",
                        "bow", "crossbow", "wand", "sceptre", "gem", "jewel", "waystone",
                        "tablet", "flask", "charm", etc. See SLOT_TO_CATEGORY for full list.
        rarity:         "magic" | "rare" | "normal" | "nonunique" | "any" (default: "magic").
        min_value:      Minimum stat value. Takes precedence over `tier`.
        max_value:      Maximum stat value.
        tier:           Mod tier (1=best). Auto-looks up minimum value from game DB.
        ilvl_min:       Minimum item level (default 80).
        ilvl_max:       Maximum item level (optional).
        stat_type:      "explicit" (default) | "implicit" | "fractured" | "pseudo" | "desecrated".
        league:         League name (defaults to active league).

        Multi-stat parameters:
        extra_stats:    Additional stat filters [{id, min?, max?}] merged into the primary group.
                        Use when searching for items with multiple mods simultaneously.
        stats_type:     Type of stat matching — "and" (all match), "if" (match if present),
                        "count" (N of M), "not" (must not have), "weight" (weighted sum).
                        Default: "and".
        stats_min_count: For stats_type="count", the minimum number of stats that must match.
        stat_groups:    List of independent stat group dicts, each with:
                          - filters: [{id, min?, max?}] — stats to match
                          - type: "and"|"if"|"count"|"not"|"weight" (default "and")
                          - min_count: int — for type="count"
                        When provided, overrides stat_name/extra_stats/stats_type/stats_min_count.

        Item property filters (None = any):
        corrupted:      True = corrupted only, False = non-corrupted, None = any.
        fractured_item: True = has a fractured mod. Key for crafting base searches.
        identified:     True/False filter.
        mirrored:       True = mirrored copies.
        quality_min/max: Quality % bounds.
        rune_sockets_min: Minimum number of rune sockets.

        Equipment stat filters (direct item stats, not mod-based):
        ar_min:         Minimum total armour on the item.
        ev_min:         Minimum total evasion.
        es_min:         Minimum total energy shield.
        dps_min:        Minimum combined DPS (physical + elemental).
        pdps_min:       Minimum physical DPS.
        edps_min:       Minimum elemental DPS.
        aps_min:        Minimum attacks per second.

        Gem filters:
        gem_level_min/max: Gem level bounds.

        Map filters:
        map_tier_min/max:     Waystone tier bounds.
        map_iir_min:          Minimum item quantity %.
        map_packsize_min:     Minimum pack size %.

        Trade filters:
        indexed:        Listing freshness — "1hour", "3hours", "12hours", "1day",
                        "3days", "1week", "2weeks", "1month". Restricts to recent listings.
        price_max:      Maximum price (in price_currency units).
        price_currency: Currency for price_max — "divine", "exalted", "chaos", etc.
        account:        Filter by seller account name.
        affix_filter:     Client-side keyword filter. After fetching results, only keep
                          listings where one of the explicit/fractured/crafted mods
                          matches this stat keyword. Useful to verify a specific affix
                          is truly present, e.g. affix_filter="energy shield local" to
                          confirm flat local ES (not % ES) appears on each result.
                          Resolved automatically to the best-matching trade stat_id.
        affix_count_min:  Client-side filter: minimum number of explicit+fractured mods.
        affix_count_max:  Client-side filter: maximum number of explicit+fractured mods.
                          E.g. affix_count_max=1 finds magic items with only 1 affix
                          (ideal crafting bases — one good mod, room for bench craft).
                          NOTE: trade2 API doesn't support affix count filtering natively.

    Returns:
        JSON with:
        - found: bool
        - total_listings: int
        - min_price / median_price: {amount, currency}
        - trade_url: direct link to open in browser
        - listings: [{name, base_type, rarity, ilvl, price_amount, price_currency, account}]
        - matched_stat: {stat_id, stat_text}
        - tier_min_used: float | null
        - other_stat_matches: [{stat_id, stat_text}] (up to 2 alternatives)
    """
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError, SLOT_TO_CATEGORY
    from poe2_crafting_mcp.data.price_cli import _lookup_tier_min

    pdb = _get_price_db()

    if not league:
        league = pdb.get_active_league() or ""
    if not league:
        return _to_json({"error": "No active league. Call set_active_league() first."})

    if pdb.trade_stats_count() == 0:
        return _to_json({
            "error": "Trade stat cache is empty. Call refresh_trade_stats() first.",
        })

    slot_lower = slot.lower()
    _armour_weapon_slots = {
        "gloves", "boots", "helmet", "helm", "body armour", "body", "chest",
        "shield", "focus", "buckler", "sword", "axe", "mace", "flail",
        "bow", "staff", "crossbow", "wand", "sceptre", "dagger", "claw",
        "spear", "quarterstaff", "warstaff", "talisman",
    }
    prefer_local = slot_lower in _armour_weapon_slots

    # ── Resolve slot → category ───────────────────────────────────────────────
    category: str | None = None
    if slot_lower:
        category = SLOT_TO_CATEGORY.get(slot_lower)
        if not category:
            for k, v in SLOT_TO_CATEGORY.items():
                if k.startswith(slot_lower) or slot_lower.startswith(k):
                    category = v
                    break

    def _resolve_stat_spec(spec: dict) -> dict | None:
        """Resolve a stat spec that may use 'keyword' instead of 'id'."""
        if "id" in spec:
            return spec
        kw = spec.get("keyword", "")
        if not kw:
            return None
        kw_matches = pdb.search_trade_stats(kw, limit=1, prefer_local=prefer_local)
        if not kw_matches:
            return None
        resolved = {"id": kw_matches[0]["stat_id"]}
        if "min" in spec:
            resolved["min"] = spec["min"]
        if "max" in spec:
            resolved["max"] = spec["max"]
        return resolved

    # ── When stat_groups provided, skip stat_name resolution ──────────────────
    chosen = None
    matches: list[dict] = []
    tier_min_used: float | None = min_value
    primary_stat_filter: list[dict] = []

    if not stat_groups:
        # ── Resolve stat ID ───────────────────────────────────────────────────
        if stat_name:
            matches = pdb.search_trade_stats(stat_name, stat_type=stat_type, limit=5, prefer_local=prefer_local)
            if not matches:
                matches = pdb.search_trade_stats(stat_name, limit=5, prefer_local=prefer_local)
            if not matches:
                return _to_json({
                    "error": f"No stat IDs found for '{stat_name}'.",
                    "hint": "Try a different keyword, or call refresh_trade_stats() to refresh the cache.",
                })
            chosen = matches[0]

        # ── Resolve tier → min value ──────────────────────────────────────────
        if tier is not None and min_value is None and stat_name:
            tier_min_used = _lookup_tier_min(stat_name, tier, slot_lower)

        # ── Build primary stat filter ─────────────────────────────────────────
        if chosen:
            sf: dict = {"id": chosen["stat_id"]}
            if tier_min_used is not None:
                sf["min"] = tier_min_used
            if max_value is not None:
                sf["max"] = max_value
            primary_stat_filter = [sf]

        # ── Resolve + merge extra_stats ───────────────────────────────────────
        resolved_extras: list[dict] = []
        for spec in (extra_stats or []):
            r = _resolve_stat_spec(spec)
            if r:
                resolved_extras.append(r)
            else:
                return _to_json({
                    "error": f"Could not resolve extra stat spec: {spec}",
                    "hint": "Provide 'id' (raw stat ID) or 'keyword' (auto-resolved via cache).",
                })
        all_stat_filters = primary_stat_filter + resolved_extras
    else:
        # ── Resolve keyword-form filters inside each stat group ───────────────
        resolved_groups: list[dict] = []
        for group in stat_groups:
            resolved_filters: list[dict] = []
            for spec in group.get("filters", []):
                r = _resolve_stat_spec(spec)
                if r:
                    resolved_filters.append(r)
                else:
                    return _to_json({
                        "error": f"Could not resolve stat group filter: {spec}",
                        "hint": "Provide 'id' or 'keyword' in each filter.",
                    })
            resolved_groups.append({**group, "filters": resolved_filters})
        stat_groups = resolved_groups
        all_stat_filters = None  # stat_groups takes over

    # ── Resolve affix_filter keyword → stat_id ────────────────────────────────
    resolved_affix_filter: str | None = None
    if affix_filter:
        af_matches = pdb.search_trade_stats(affix_filter, limit=1, prefer_local=prefer_local)
        if not af_matches:
            af_matches = pdb.search_trade_stats(affix_filter, limit=1)
        if af_matches:
            resolved_affix_filter = af_matches[0]["stat_id"]

    # ── Search ────────────────────────────────────────────────────────────────
    try:
        result = TradeClient().estimate_trade_price(
            league,
            stat_filters=all_stat_filters,
            stats_type=stats_type,
            stats_min_count=stats_min_count,
            stat_groups=stat_groups,
            affix_filter=resolved_affix_filter,
            affix_count_min=affix_count_min,
            affix_count_max=affix_count_max,
            category=category,
            rarity=rarity if rarity != "any" else None,
            ilvl_min=ilvl_min if ilvl_min else None,
            ilvl_max=ilvl_max,
            quality_min=quality_min,
            quality_max=quality_max,
            ar_min=ar_min,
            ev_min=ev_min,
            es_min=es_min,
            dps_min=dps_min,
            pdps_min=pdps_min,
            edps_min=edps_min,
            aps_min=aps_min,
            rune_sockets_min=rune_sockets_min,
            corrupted=corrupted,
            fractured_item=fractured_item,
            identified=identified,
            mirrored=mirrored,
            gem_level_min=gem_level_min,
            gem_level_max=gem_level_max,
            map_tier_min=map_tier_min,
            map_tier_max=map_tier_max,
            map_iir_min=map_iir_min,
            map_packsize_min=map_packsize_min,
            indexed=indexed,
            price_max=price_max,
            price_currency=price_currency,
            account=account,
        )
    except TradeError as e:
        return _to_json({"error": str(e)})

    if chosen:
        result["matched_stat"] = {"stat_id": chosen["stat_id"], "stat_text": chosen["stat_text"]}
        result["other_stat_matches"] = [
            {"stat_id": m["stat_id"], "stat_text": m["stat_text"]}
            for m in matches[1:3]
        ]
    result["tier_min_used"] = tier_min_used

    # Include the PoB slot name so the agent can call simulate_trade_item directly
    from poe2_crafting_mcp.data.trade_client import CATEGORY_TO_POB_SLOT
    pob_slot = CATEGORY_TO_POB_SLOT.get(category or "")
    if pob_slot:
        result["pob_slot"] = pob_slot

    return _to_json(result)


@mcp.tool()
def simulate_trade_item(
    item_text: str,
    slot: str,
    price_amount: float | None = None,
    price_currency: str = "divine",
) -> str:
    """
    Equip a trade listing item into the loaded build, measure its impact, then unequip.

    This is the core tool for evaluating whether a specific item is worth buying.
    Feed it the item_text from a search_trade_listings() result and it will:
      1. Equip the item into the given slot
      2. Measure DPS and defence changes
      3. Unequip (restore previous item)
      4. Return the delta + value rating (dps gain per chaos)

    Typical workflow:
        results = search_trade_listings("energy shield", slot="gloves", tier=1)
        for listing in results["listings"][:5]:
            sim = simulate_trade_item(
                item_text=listing["item_text"],
                slot=results["pob_slot"],          # "Gloves"
                price_amount=listing["price_amount"],
                price_currency=listing["price_currency"],
            )
            # sim["dps_delta_pct"] tells you how much DPS this item adds
            # sim["dps_gain_per_chaos"] ranks items by value

    Args:
        item_text:       Item text from listing["item_text"] in search_trade_listings results.
                         Also accepts manual PoB clipboard text (Ctrl+C from in-game).
        slot:            PoB slot name — "Gloves", "Boots", "Helmet", "Body Armour",
                         "Weapon 1", "Weapon 2", "Amulet", "Ring 1", "Ring 2", "Belt".
                         Use results["pob_slot"] from search_trade_listings directly.
        price_amount:    Item price for value calculations (optional).
        price_currency:  Currency of the price — "divine", "exalted", "chaos", etc.

    Returns:
        JSON with:
        - slot: str
        - item_summary: {name, base_type, ilvl, mods preview}
        - dps_before / dps_after: float
        - dps_delta: float
        - dps_delta_pct: float
        - es_before / es_after / es_delta: float
        - life_before / life_after / life_delta: float
        - evasion_before / evasion_after: float
        - armour_before / armour_after: float
        - price: {amount, currency, chaos_value} (if price provided)
        - dps_gain_per_chaos: float | null (dps_delta / chaos_value, for ranking)
        - verdict: "upgrade" | "downgrade" | "sidegrade"
    """
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    engine = _get_engine()

    # Snapshot stats before
    before = engine.get_stats()
    dps_before  = before.get("TotalDPS", 0) or 0
    es_before   = before.get("EnergyShield", 0) or 0
    life_before = before.get("Life", 0) or 0
    ev_before   = before.get("Evasion", 0) or 0
    ar_before   = before.get("Armour", 0) or 0

    # Extract a brief item summary from the text (first 3 non-separator lines)
    text_lines = [ln.strip() for ln in item_text.splitlines() if ln.strip() and ln.strip() != "--------"]
    item_summary = " | ".join(text_lines[:3])

    # Equip
    try:
        engine.equip_item(slot, item_text)
    except Exception as exc:
        return _to_json({"error": f"equip_item failed: {exc}", "slot": slot})

    # Snapshot stats after
    after = engine.get_stats()
    dps_after  = after.get("TotalDPS", 0) or 0
    es_after   = after.get("EnergyShield", 0) or 0
    life_after = after.get("Life", 0) or 0
    ev_after   = after.get("Evasion", 0) or 0
    ar_after   = after.get("Armour", 0) or 0

    # Restore previous item
    try:
        engine.unequip_slot(slot)
    except Exception:
        pass  # Non-fatal — build state may be slightly off but simulation is done

    # Compute deltas
    dps_delta     = dps_after - dps_before
    dps_delta_pct = (dps_delta / dps_before * 100) if dps_before else 0.0

    # Convert price → chaos for value rating
    chaos_value: float | None = None
    dps_gain_per_chaos: float | None = None
    price_result: dict | None = None

    if price_amount is not None and price_amount > 0:
        pdb = _get_price_db()
        league = pdb.get_active_league() or ""
        if price_currency in ("divine", "exalted"):
            rate_row = pdb.get_price(
                "Divine Orb" if price_currency == "divine" else "Exalted Orb",
                league, "currency"
            )
            rate = float(rate_row["chaos_value"]) if rate_row and rate_row.get("chaos_value") else None
            chaos_value = price_amount * rate if rate else None
        elif price_currency == "chaos":
            chaos_value = price_amount
        price_result = {"amount": price_amount, "currency": price_currency, "chaos_value": chaos_value}
        if chaos_value and chaos_value > 0 and dps_delta > 0:
            dps_gain_per_chaos = dps_delta / chaos_value

    # Verdict
    if dps_delta_pct > 2:
        verdict = "upgrade"
    elif dps_delta_pct < -2:
        verdict = "downgrade"
    else:
        # Check defences even if DPS is neutral
        total_def_before = es_before + life_before
        total_def_after  = es_after  + life_after
        def_delta_pct = ((total_def_after - total_def_before) / total_def_before * 100) if total_def_before else 0
        verdict = "upgrade" if def_delta_pct > 2 else ("downgrade" if def_delta_pct < -2 else "sidegrade")

    out: dict = {
        "slot":           slot,
        "item_summary":   item_summary,
        "dps_before":     round(dps_before, 1),
        "dps_after":      round(dps_after, 1),
        "dps_delta":      round(dps_delta, 1),
        "dps_delta_pct":  round(dps_delta_pct, 2),
        "es_before":      round(es_before, 0),
        "es_after":       round(es_after, 0),
        "es_delta":       round(es_after - es_before, 0),
        "life_before":    round(life_before, 0),
        "life_after":     round(life_after, 0),
        "life_delta":     round(life_after - life_before, 0),
        "evasion_before": round(ev_before, 0),
        "evasion_after":  round(ev_after, 0),
        "armour_before":  round(ar_before, 0),
        "armour_after":   round(ar_after, 0),
        "verdict":        verdict,
    }
    if price_result:
        out["price"] = price_result
    if dps_gain_per_chaos is not None:
        out["dps_gain_per_chaos"] = round(dps_gain_per_chaos, 2)

    return _to_json(out)


# ── Crafting Optimizer ────────────────────────────────────────────────────────

@mcp.tool()
def optimize_craft_path(
    item_class: str,
    targets: str,
    ilvl: int = 82,
    trade_price: float = 0,
    base_item: str = "",
    quick: bool = True,
) -> str:
    """
    Find the optimal crafting strategy for an item using evolutionary optimization.

    Runs a GP (Genetic Programming) optimizer that evolves rule-list strategies,
    evaluates them via Monte Carlo simulation, and returns the best approaches
    ranked by cost, reliability, and consistency.

    Args:
        item_class: poe2db item class (e.g. "Gloves_int", "Boots_dex", "Amulets")
        targets:    Comma-separated "Family:affix:tier" specs.
                    Example: "IncreasedEnergyShield:prefix:1, FireResistance:suffix:2"
                    affix = "prefix" or "suffix", tier = 1 for T1 only, 2 for T1-T2, etc.
        ilvl:       Item level (determines mod pool eligibility, default 82)
        trade_price: Known trade price for the finished item (for CRAFT vs BUY verdict).
                     Set to 0 to skip verdict (optimizer just finds cheapest strategy).
        base_item:  Starting base specification:
                    - "fractured:FamilyName:220" = start from fractured base (220c)
                    - "magic:FamilyName:35" = start from magic with mod (35c)
                    - "white:2" = start from white base (2c, default)
                    - "" = use default white base pricing
        quick:      If true (default), use fast settings (pop=50, gen=10, trials=200).
                    Set false for thorough optimization (pop=200, gen=50, trials=500).

    Returns:
        JSON with:
        - strategies: ranked list of discovered crafting strategies
        - best_verdict: "CRAFT (saves Xc)" or "BUY (costs Xc more)"
        - metadata: generations, evaluations, wall_time, archive_coverage
    """
    from poe2_crafting_mcp.crafting.optimizer.preflight import preflight
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize, OptimizerConfig
    from poe2_crafting_mcp.crafting.optimizer.cli import _parse_targets, _apply_base_item

    # Parse targets
    target_mods = _parse_targets(targets)
    if not target_mods:
        return _to_json({"error": "No valid targets. Format: 'Family:prefix|suffix:tier'"})

    # Preflight
    pool_data, prices, target = preflight(item_class, ilvl, target_mods)

    # Apply options
    if trade_price > 0:
        prices.trade_finished = trade_price
    if base_item:
        _apply_base_item(base_item, prices, target)

    # Config
    if quick:
        config = OptimizerConfig(pop_size=50, max_generations=10, mc_trials=200)
    else:
        config = OptimizerConfig(pop_size=200, max_generations=50, mc_trials=500)

    # Run
    result = optimize(pool_data, target, prices, config)

    # Format output
    strategies_out = []
    seen: set[str] = set()
    for s in result.strategies:
        if s.family_name in seen:
            continue
        seen.add(s.family_name)
        strategies_out.append({
            "family_name": s.family_name,
            "verdict": s.verdict,
            "expected_cost": round(s.expected_cost, 1),
            "base_acquisition_cost": round(s.base_acquisition_cost, 1),
            "currency_cost": round(s.currency_cost, 1),
            "success_rate": round(s.success_rate, 3),
            "cost_p90": round(s.cost_p90, 1),
            "savings_vs_trade": round(s.savings_vs_trade, 1),
            "starting_state": s.starting_state,
            "steps": s.steps,
            "rule_count": s.rulelist.size,
        })

    return _to_json({
        "target": str(target),
        "trade_price": prices.trade_finished if prices.trade_finished < float("inf") else None,
        "best_verdict": result.best_verdict,
        "strategies": strategies_out,
        "metadata": {
            "generations": result.generations,
            "evaluations": result.evaluations,
            "wall_time_seconds": round(result.wall_time_seconds, 2),
            "archive_coverage": round(result.archive_coverage, 3),
            "rust_available": result.rust_available,
            "strategy_families": len(strategies_out),
            "archive_strategies": len(result.archive_strategies),
        },
    })


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
