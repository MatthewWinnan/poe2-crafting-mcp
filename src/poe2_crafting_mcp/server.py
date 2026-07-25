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

POB_PATH = Path(os.environ.get("POB_PATH", Path(__file__).parent.parent.parent / "vendor" / "PathOfBuilding-PoE2"))

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


@mcp.tool()
def search_concepts(keyword: str = "", category: str = "", limit: int = 10) -> str:
    """
    Look up PoE2 keyword and mechanic definitions.

    Covers ~180 core concepts including: damage types, ailments (Shock/Chill/Freeze/
    Ignite/Bleed/Poison/Electrocute and lesser ailments), attributes (Strength/
    Dexterity/Intelligence), defence mechanics (Armour formula, Evasion, Energy Shield,
    Ward, Block, Suppress, Deflect, Resistances), offence mechanics (Critical Hits,
    Accuracy, Leech, Penetration, Conversion, Culling Strike), charges (Power/Frenzy/
    Endurance), resources (Life/Mana/Spirit/Rage), buffs (Onslaught/Elusive/Tailwind),
    debuffs (Exposure/Blind/Crushed/Maim/Curses/Withered), mechanics (Recently/Lucky/
    Stun/Recoup/Reserve/Low Life), skill keywords (Attack/Spell/Melee/Projectile/
    Channelling/Totem/Minion/Warcry), keystones (Chaos Inoculation/Iron Reflexes/
    Eldritch Battery/Blood Magic/Avatar of Fire/Resolute Technique etc.), and more.

    Each concept includes:
    - summary: plain English one-liner
    - mechanics: detailed explanation with PoE2-accurate rules
    - formula: numeric formula where applicable (e.g. Armour reduction, Freeze buildup)
    - see_also: related concepts AND PoB config var names for cross-referencing

    Args:
        keyword:  Search term — e.g. "shock", "armour", "critical", "leech", "rage".
                  Searched across name, summary, mechanics, and see_also fields.
        category: Narrow by category — one of: damage_type, ailment, attribute,
                  defence, offence, charge, resource, buff, debuff, mechanic,
                  keyword, keystone, projectile, ground.
        limit:    Max results (default 10).

    Returns:
        JSON array of matching concept dicts.
    """
    from poe2_crafting_mcp.data.concepts import search_concepts as _search
    return _to_json(_search(keyword=keyword, category=category, limit=limit))


@mcp.tool()
def get_concept(name: str) -> str:
    """
    Fetch the exact definition for a single PoE2 keyword by name.

    Use search_concepts() first if you're not sure of the exact name.

    Args:
        name: Concept name — e.g. "Shock", "Armour", "Power Charge", "Iron Reflexes".

    Returns:
        JSON with name, category, summary, mechanics, formula, see_also.
        Returns {"error": "..."} if not found.
    """
    from poe2_crafting_mcp.data.concepts import get_concept as _get
    result = _get(name)
    if not result:
        return _to_json({"error": f"Concept '{name}' not found"})
    return _to_json(result)


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

    If prices.status != "fresh", call refresh_prices().
    If etl.status != "fresh", warn the user and offer to call refresh_etl().
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
    trade_ids = [c[4] for c in CURRENCIES if c[4]]

    t0 = time.monotonic()
    try:
        rows = client.fetch_currency_rates(league, trade_ids)
    except EconomyError as e:
        return _to_json({"error": str(e)})

    pdb.upsert_prices(rows, league)
    duration = round(time.monotonic() - t0, 2)

    # Find divine rate for display
    divine_row = next((r for r in rows if r.get("trade_id") == "divine-orb"), None)
    divine_chaos = divine_row["chaos_value"] if divine_row else None

    return _to_json({
        "league": league,
        "categories_fetched": ["currency"],
        "total_prices": len(rows),
        "duration_seconds": duration,
        "divine_chaos_rate": divine_chaos,
        "note": "Item prices (uniques/bases/gems) not available via poe.ninja PoE2 API.",
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
def search_trade_listings(
    stat_name: str,
    slot: str = "",
    rarity: str = "magic",
    min_value: float | None = None,
    max_value: float | None = None,
    tier: int | None = None,
    ilvl_min: int = 80,
    stat_type: str = "explicit",
    league: str = "",
) -> str:
    """
    Search the GGG trade site for items with a specific mod/stat.

    This is the primary tool for finding items to buy based on desired stats.
    Example use cases:
    - "Find the cheapest magic gloves with T1 energy shield"
    - "Find rare rings with at least 80 max life"
    - "Find magic boots with movement speed T1"

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

    Args:
        stat_name:  Stat to search for — e.g. "energy shield", "maximum life",
                    "cold resistance", "movement speed", "attack speed".
                    Matched against the trade stat ID cache via FTS.
        slot:       Item slot to restrict to — e.g. "gloves", "boots", "helmet",
                    "ring", "amulet", "belt", "body armour", "shield".
                    Leave blank to search all item types.
        rarity:     "magic" (default) | "rare" | "normal" | "any".
                    Magic bases with one strong mod are prime crafting candidates.
        min_value:  Minimum stat value (e.g. 50 for 50+ energy shield).
                    If both min_value and tier are given, min_value takes precedence.
        max_value:  Maximum stat value (optional upper bound).
        tier:       Mod tier number — 1 = best. Auto-looks up the tier's minimum
                    value from the game DB (item_mods table). If the DB lookup
                    fails, the search runs without a value floor.
        ilvl_min:   Minimum item level (default 80).
        stat_type:  "explicit" (default) | "implicit" | "pseudo".
        league:     League name. Defaults to the active league.

    Returns:
        JSON with:
        - found: bool
        - total_listings: int (how many exist on trade)
        - min_price: {amount, currency}
        - median_price: {amount, currency}
        - trade_url: direct link to open in browser
        - listings: [{name, base_type, rarity, ilvl, price_amount, price_currency, account}]
        - matched_stat: {stat_id, stat_text} — the stat we searched for
        - tier_min_used: float | null — the min value used (from tier lookup or min_value)
    """
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError, SLOT_TO_CATEGORY
    from poe2_crafting_mcp.data.price_cli import _lookup_tier_min, _slot_to_pob_tag

    pdb = _get_price_db()

    if not league:
        league = pdb.get_active_league() or ""
    if not league:
        return _to_json({"error": "No active league. Call set_active_league() first."})

    if pdb.trade_stats_count() == 0:
        return _to_json({
            "error": "Trade stat cache is empty. Call refresh_trade_stats() first.",
        })

    # ── Resolve stat ID ───────────────────────────────────────────────────────
    # Armour/weapon slots use local mods — prefer (Local) stat variants
    _armour_slots = {"gloves", "boots", "helmet", "helm", "body armour", "body", "chest",
                     "shield", "focus", "buckler", "weapon", "sword", "axe", "mace",
                     "bow", "staff", "crossbow", "wand", "sceptre", "dagger", "claw", "spear"}
    prefer_local = slot_lower in _armour_slots
    matches = pdb.search_trade_stats(stat_name, stat_type=stat_type, limit=5, prefer_local=prefer_local)
    if not matches:
        matches = pdb.search_trade_stats(stat_name, limit=5, prefer_local=prefer_local)
    if not matches:
        return _to_json({
            "error": f"No stat IDs found for '{stat_name}'.",
            "hint": "Try a different keyword, or call refresh_trade_stats() to refresh the cache.",
        })
    chosen = matches[0]

    # ── Resolve slot → category ───────────────────────────────────────────────
    category: str | None = None
    slot_lower = slot.lower()
    if slot_lower:
        category = SLOT_TO_CATEGORY.get(slot_lower)
        if not category:
            for k, v in SLOT_TO_CATEGORY.items():
                if k.startswith(slot_lower) or slot_lower.startswith(k):
                    category = v
                    break

    # ── Resolve tier → min value ──────────────────────────────────────────────
    tier_min_used: float | None = min_value
    if tier is not None and min_value is None:
        tier_min_used = _lookup_tier_min(stat_name, tier, slot_lower)

    # ── Build stat filter ─────────────────────────────────────────────────────
    stat_filter: dict = {"id": chosen["stat_id"]}
    if tier_min_used is not None:
        stat_filter["min"] = tier_min_used
    if max_value is not None:
        stat_filter["max"] = max_value

    # ── Search ────────────────────────────────────────────────────────────────
    try:
        result = TradeClient().estimate_trade_price(
            league,
            stat_filters=[stat_filter],
            category=category,
            rarity=rarity,
            ilvl_min=ilvl_min,
        )
    except TradeError as e:
        return _to_json({"error": str(e)})

    result["matched_stat"] = {"stat_id": chosen["stat_id"], "stat_text": chosen["stat_text"]}
    result["tier_min_used"] = tier_min_used
    result["other_stat_matches"] = [
        {"stat_id": m["stat_id"], "stat_text": m["stat_text"]}
        for m in matches[1:3]
    ]
    return _to_json(result)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
