"""Pre-flight data fetching for the optimizer.

Queries the real DB for mod pool weights and live economy prices,
encoding them into the format the Rust evaluator expects.

Two phases:
  1. HOT (instant, from poe.ninja SQLite cache): currency, omen, essence prices
  2. COLD (optional, from trade API): base item trade prices

Usage:
    from poe2_crafting_mcp.crafting.optimizer.preflight import preflight
    pool_data, prices, target = preflight("Gloves_int", 82, [("IncreasedES", "prefix", 1)])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..optimizer.bridge import encode_pool
from ..optimizer.gene import CraftTarget, ModTarget, PriceCache

log = logging.getLogger(__name__)

# Currency name mapping: DB names (poe.ninja) → gene.py Currency enum names
# DB names have inconsistent casing and no apostrophes
_CURRENCY_NAME_MAP: dict[str, str] = {
    "Exalted Orb": "exalted",
    "Chaos Orb": "chaos",
    "Divine Orb": "divine",
    "Orb Of Annulment": "annulment",
    "Orb Of Transmutation": "transmute",
    "Regal Orb": "regal",
    "Orb Of Alchemy": "alchemy",
    "Orb Of Augmentation": "augment",
    "Vaal Orb": "vaal",
    "Fracturing Orb": "fracturing",
    "Artificers Orb": "artificer",
    "Armourers Scrap": "armourers_scrap",
    "Blacksmiths Whetstone": "blacksmiths_whetstone",
    "Perfect Orb of Transmutation": "perfect_transmute",
    # Greater/Perfect variants (may have varying DB names)
    "Greater Exalted Orb": "greater_exalted",
    "Greater Orb of Transmutation": "greater_transmute",
    "Greater Orb of Augmentation": "greater_augment",
    "Greater Regal Orb": "greater_regal",
    "Greater Chaos Orb": "greater_chaos",
    "Perfect Exalted Orb": "perfect_exalted",
    "Perfect Orb of Augmentation": "perfect_augment",
    "Perfect Regal Orb": "perfect_regal",
    "Perfect Chaos Orb": "perfect_chaos",
}

_OMEN_NAME_MAP: dict[str, str] = {
    "Omen of Sinistral Exaltation": "sinistral_exaltation",
    "Omen of Dextral Exaltation": "dextral_exaltation",
    "Omen of Greater Exaltation": "greater_exaltation",
    "Omen of Sinistral Annulment": "sinistral_annulment",
    "Omen of Dextral Annulment": "dextral_annulment",
    "Omen of Sinistral Coronation": "sinistral_coronation",
    "Omen of Dextral Coronation": "dextral_coronation",
    "Omen of Whittling": "whittling",
    "Omen of Abyssal Echoes": "abyssal_echoes",
    "Omen of Sinistral Necromancy": "sinistral_necromancy",
    "Omen of Dextral Necromancy": "dextral_necromancy",
    "Omen of Corruption": "corruption",
    "Omen of Sanctification": "sanctification",
}


def preflight(
    item_class: str,
    ilvl: int,
    target_mods: list[tuple[str, str, int]],
    db_path: str | None = None,
    rune_pools: list[str] | None = None,
) -> tuple[dict, PriceCache, CraftTarget]:
    """Fetch all data needed for optimization from the local DB.

    Args:
        item_class: poe2db item class slug (e.g. "Gloves_int", "Boots_dex")
        ilvl: item level (determines mod pool eligibility)
        target_mods: list of (family_name, affix_type, max_tier) tuples
            e.g. [("IncreasedEnergyShield", "prefix", 1),
                   ("IncreasedLife", "prefix", 2),
                   ("FireResistance", "suffix", 2)]
        db_path: optional path to SQLite DB (uses default if None)
        rune_pools: optional list of rune pool names to merge into the mod pool
            (e.g. ["marksman", "decay"]). These expand the available mod pool.

    Returns:
        pool_data: encoded mod pool dict for bridge.encode_pool()
        prices: PriceCache with live economy data
        target: CraftTarget with resolved family IDs
    """
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase(db_path) if db_path else PriceDatabase()
    league = pdb.get_active_league() or ""

    # ── Phase 1: Mod Pool ──
    pool_result = pdb.get_craftable_mods(item_class, ilvl, pool="normal")

    # Flatten pool into per-tier arrays
    prefix_weights: list[int] = []
    prefix_families: list[int] = []
    prefix_tiers: list[int] = []
    prefix_req_levels: list[int] = []
    suffix_weights: list[int] = []
    suffix_families: list[int] = []
    suffix_tiers: list[int] = []
    suffix_req_levels: list[int] = []

    # Assign numeric family IDs (sequential, stable within a run)
    family_to_id: dict[str, int] = {}
    next_id = 1

    def get_family_id(name: str) -> int:
        nonlocal next_id
        if name not in family_to_id:
            family_to_id[name] = next_id
            next_id += 1
        return family_to_id[name]

    for group in pool_result["prefixes"]:
        fam_id = get_family_id(group["family"])
        for tier_idx, tier in enumerate(group["tiers"]):
            prefix_weights.append(tier["weight"])
            prefix_families.append(fam_id)
            prefix_tiers.append(tier_idx + 1)  # T1=1 (best), T2=2, T3=3, ...
            prefix_req_levels.append(tier["req_level"])

    for group in pool_result["suffixes"]:
        fam_id = get_family_id(group["family"])
        for tier_idx, tier in enumerate(group["tiers"]):
            suffix_weights.append(tier["weight"])
            suffix_families.append(fam_id)
            suffix_tiers.append(tier_idx + 1)  # T1=1, T2=2, ...
            suffix_req_levels.append(tier["req_level"])

    # ── Phase 1b: Merge Rune Pools ──
    # Rune mods expand the normal pool — same family can appear in both.
    # Uses the same family_to_id mapping so family blocking works correctly.
    rune_mod_count = 0
    if rune_pools:
        for pool_name in rune_pools:
            rune_result = pdb.get_craftable_mods(item_class, ilvl, pool=pool_name)
            for group in rune_result["prefixes"]:
                fam_id = get_family_id(group["family"])
                for tier_idx, tier in enumerate(group["tiers"]):
                    prefix_weights.append(tier["weight"])
                    prefix_families.append(fam_id)
                    prefix_tiers.append(tier_idx + 1)
                    prefix_req_levels.append(tier["req_level"])
                    rune_mod_count += 1
            for group in rune_result["suffixes"]:
                fam_id = get_family_id(group["family"])
                for tier_idx, tier in enumerate(group["tiers"]):
                    suffix_weights.append(tier["weight"])
                    suffix_families.append(fam_id)
                    suffix_tiers.append(tier_idx + 1)
                    suffix_req_levels.append(tier["req_level"])
                    rune_mod_count += 1

    # ── Phase 2: Build CraftTarget with resolved IDs ──
    targets: list[ModTarget] = []
    for family_name, affix_type, max_tier in target_mods:
        fam_id = get_family_id(family_name)
        targets.append(ModTarget(family_name, fam_id, affix_type, max_tier))

    target = CraftTarget(targets=targets, item_class=item_class, ilvl=ilvl)

    # ── Phase 3: Encode pool for Rust ──
    pool_data = encode_pool(
        prefix_weights=prefix_weights,
        prefix_families=prefix_families,
        prefix_tiers=prefix_tiers,
        prefix_req_levels=prefix_req_levels,
        suffix_weights=suffix_weights,
        suffix_families=suffix_families,
        suffix_tiers=suffix_tiers,
        suffix_req_levels=suffix_req_levels,
        target=target,
        ilvl=ilvl,
        max_prefixes=3,
        max_suffixes=3,
    )

    # ── Phase 4: Economy Prices (HOT — from poe.ninja cache) ──
    currency_prices: dict[str, float] = {}
    omen_prices: dict[str, float] = {}

    # Fetch all currency prices
    currency_rows = pdb.get_bulk_prices("currency", league)
    for row in currency_rows:
        mapped = _CURRENCY_NAME_MAP.get(row["name"])
        if mapped and row.get("chaos_value"):
            currency_prices[mapped] = row["chaos_value"]

    # Fetch omen prices (stored in "omen" category)
    omen_rows = pdb.get_bulk_prices("omen", league)
    for row in omen_rows:
        mapped = _OMEN_NAME_MAP.get(row["name"])
        if mapped and row.get("chaos_value"):
            omen_prices[mapped] = row["chaos_value"]

    # Also check "fragment" category as fallback
    fragment_rows = pdb.get_bulk_prices("fragment", league)
    for row in fragment_rows:
        mapped = _OMEN_NAME_MAP.get(row["name"])
        if mapped and row.get("chaos_value") and mapped not in omen_prices:
            omen_prices[mapped] = row["chaos_value"]

    # Default scouring cost (no real orb in PoE2 — represents "discard and start over")
    if "scouring" not in currency_prices:
        currency_prices["scouring"] = 0.5

    # ── Phase 4b: Per-target essence prices ──
    # Look up specific essence prices from the DB for each target mod.
    # Uses the essences table to match target family → essence name,
    # then looks up the price. Falls back to tier-level defaults.
    essence_prices = _resolve_essence_prices(pdb, league, item_class, target_mods)
    for key, price in essence_prices.items():
        currency_prices[key] = price

    # Default prices for common currencies not tracked by poe.ninja (too cheap)
    _DEFAULTS: dict[str, float] = {
        "transmute": 0.01,
        "augment": 0.01,
        "alchemy": 0.02,
        "regal": 0.02,
        "scouring": 0.5,
        "greater_transmute": 0.5,
        "greater_augment": 0.5,
        "greater_regal": 0.5,
        "greater_chaos": 1.0,
        "greater_exalted": 1.0,
        "perfect_augment": 2.0,
        "perfect_regal": 2.0,
        "perfect_chaos": 3.0,
        "perfect_exalted": 5.0,
        # Essence tier defaults (used if per-target lookup fails)
        "lesser_essence": 0.2,
        "normal_essence": 0.5,
        "greater_essence": 1.0,
        "perfect_essence": 10.0,
        # Reforge (3-to-1 recycling ~ 0.5c in materials)
        "reforge": 0.5,
    }
    for name, default_price in _DEFAULTS.items():
        if name not in currency_prices:
            currency_prices[name] = default_price

    # ── Phase 5: Base item prices (from cache, no trade API calls) ──
    # Try to find the base item price from ninja
    base_white = 1.0  # default: white bases are nearly free
    base_magic_with: dict[str, float] = {}
    base_fractured_with: dict[str, float] = {}
    trade_finished = float("inf")

    # Look for base type prices in the "bases" category
    # The item_class is like "Gloves_int" — we need the base name
    base_rows = pdb.get_bulk_prices("bases", league)
    for row in base_rows:
        if row.get("chaos_value") and row["chaos_value"] > 0:
            # Simple heuristic: if the base name contains our item class keywords
            name_lower = row["name"].lower()
            # TODO: proper base name resolution from item_class
            if row["chaos_value"] < base_white * 10:
                base_white = max(base_white, 1.0)

    # Estimate trade price for finished item (rough: check uniques category for similar)
    # This is a placeholder — real implementation would use trade API search
    # For now, leave at infinity (verdict will always be CRAFT until we fetch trade data)
    # The CLI/MCP layer can provide trade_finished from a live search

    prices = PriceCache(
        currency=currency_prices,
        omen=omen_prices,
        base_white=base_white,
        base_magic_with=base_magic_with,
        base_fractured_with=base_fractured_with,
        trade_finished=trade_finished,
    )

    rune_info = f" | Runes: {', '.join(rune_pools)} (+{rune_mod_count} mods)" if rune_pools else ""
    log.info(
        f"Preflight: {item_class} ilvl{ilvl} | "
        f"Pool: {len(prefix_weights)}P + {len(suffix_weights)}S mods | "
        f"Prices: {len(currency_prices)} currencies, {len(omen_prices)} omens | "
        f"Targets: {[t.family for t in targets]}{rune_info}"
    )

    return pool_data, prices, target


# ── Essence Price Resolution ─────────────────────────────────────────────────

# Map item_class slug → item slot category for essence DB lookups
_CLASS_TO_SLOT: dict[str, str] = {
    "Gloves": "Gloves",
    "Boots": "Boots",
    "Helmet": "Helmet",
    "Body_Armours": "Body Armour",
    "Shields": "Shield",
    "Bucklers": "Shield",
    "Amulets": "Amulet",
    "Rings": "Ring",
    "Belts": "Belt",
    "Bows": "Bow",
    "Crossbows": "Crossbow",
    "Wands": "Wand",
    "Sceptres": "Sceptre",
    "Staves": "Staff",
    "Foci": "Focus",
    "Claws": "Claw",
    "Daggers": "Dagger",
}


def _resolve_essence_prices(
    pdb,
    league: str,
    item_class: str,
    target_mods: list[tuple[str, str, int]],
) -> dict[str, float]:
    """Look up per-target essence prices from the DB.

    For each target mod, finds the matching essence (by stat_text overlap)
    at each tier (Lesser, Normal, Greater) and looks up its market price.

    Returns dict with keys like "lesser_essence", "normal_essence", "greater_essence"
    set to the cheapest matching essence across all targets.
    """
    import sqlite3
    import os

    db_path = os.environ.get("POE2_CRAFT_DB", "data/poe2_craft.db")
    if not os.path.exists(db_path):
        return {}

    # Determine slot from item_class (strip attribute suffix like _int, _str_dex)
    base_class = item_class.split("_")[0]
    slot = _CLASS_TO_SLOT.get(base_class, "")
    if not slot:
        return {}

    result: dict[str, float] = {}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Get all essence prices from the prices table
        essence_prices: dict[str, float] = {}
        rows = conn.execute(
            "SELECT name, chaos_value FROM prices WHERE category = 'essence' AND chaos_value > 0"
        ).fetchall()
        for row in rows:
            essence_prices[row["name"]] = row["chaos_value"]

        # For each essence tier, find the cheapest applicable essence
        for tier_label, price_key in [
            ("Lesser", "lesser_essence"),
            ("Normal", "normal_essence"),
            ("Greater", "greater_essence"),
        ]:
            # Find all essences at this tier for the slot
            essence_rows = conn.execute(
                "SELECT DISTINCT name FROM essences "
                "WHERE tier = ? AND effect_type = 'upgrade' AND item_slots LIKE ?",
                (tier_label, f"%{slot}%"),
            ).fetchall()

            tier_prices: list[float] = []
            for erow in essence_rows:
                ename = erow["name"]
                if ename in essence_prices:
                    tier_prices.append(essence_prices[ename])

            if tier_prices:
                # Use the median price for this tier (representative of the market)
                tier_prices.sort()
                result[price_key] = tier_prices[len(tier_prices) // 2]
                log.debug(f"Essence {price_key}: {result[price_key]:.4f}c "
                         f"(median of {len(tier_prices)} essences)")

        conn.close()
    except Exception as e:
        log.warning(f"Essence price lookup failed: {e}")

    return result
