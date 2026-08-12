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

# Trade API price_currency slugs → DB name in prices table.
# Used to convert listing prices (e.g. "3 transmute") into chaos equivalent.
_TRADE_CURRENCY_TO_DB: dict[str, str] = {
    "transmute": "Orb Of Transmutation",
    "aug": "Orb Of Augmentation",
    "chaos": "Chaos Orb",
    "divine": "Divine Orb",
    "exalted": "Exalted Orb",
    "regal": "Regal Orb",
    "alch": "Orb Of Alchemy",
    "annul": "Orb Of Annulment",
    "vaal": "Vaal Orb",
    "chance": "Orb Of Chance",
    "frac": "Fracturing Orb",
    "mirror": "Mirror Of Kalandra",
    "artificer": "Artificers Orb",
    "armourer": "Armourers Scrap",
    "blacksmith": "Blacksmiths Whetstone",
    "gemcutter": "Gemcutters Prism",
    "glassblower": "Glassblowers Bauble",
    "perfect-transmute": "Perfect Orb of Transmutation",
    "greater-transmute": "Greater Orb of Transmutation",
    "greater-aug": "Greater Orb of Augmentation",
    "greater-regal": "Greater Regal Orb",
    "greater-chaos": "Greater Chaos Orb",
    "greater-exalted": "Greater Exalted Orb",
    "perfect-aug": "Perfect Orb of Augmentation",
    "perfect-regal": "Perfect Regal Orb",
    "perfect-chaos": "Perfect Chaos Orb",
    "perfect-exalted": "perfect Exalted Orb",
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
    "Omen of Light": "light",
}

# Jewels have 2 prefixes + 2 suffixes (not the standard 3+3)
_JEWEL_CLASSES = frozenset({
    "Diamond", "Emerald", "Ruby", "Sapphire",
    "Time-Lost_Diamond", "Time-Lost_Emerald", "Time-Lost_Ruby", "Time-Lost_Sapphire",
})


def _max_affixes(item_class: str) -> int:
    """Return max prefixes (or suffixes) for an item class."""
    return 2 if item_class in _JEWEL_CLASSES else 3


def preflight(
    item_class: str,
    ilvl: int,
    target_mods: list[tuple[str, str, int]],
    db_path: str | None = None,
    rune_pools: list[str] | None = None,
    base_name: str | None = None,
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
        base_name: optional specific base item name (e.g. "Stitched Gloves").
            When provided, trade lookups search for this exact base instead of
            the generic item category, giving more accurate scour/buy prices.

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

    # ── Phase 1c: Fetch Essence Pool (separate tier data) ──
    # Essences guarantee a mod from the essence pool, which has different
    # tiers than the normal pool. We pass this separately so the Rust
    # evaluator uses the correct tiers for essence actions.
    ess_prefix_families: list[int] = []
    ess_prefix_tiers: list[int] = []
    ess_suffix_families: list[int] = []
    ess_suffix_tiers: list[int] = []

    ess_result = pdb.get_craftable_mods(item_class, ilvl, pool="essence")
    for group in ess_result.get("prefixes", []):
        fam_id = get_family_id(group["family"])
        for tier_idx, tier in enumerate(group["tiers"]):
            ess_prefix_families.append(fam_id)
            ess_prefix_tiers.append(tier_idx + 1)
    for group in ess_result.get("suffixes", []):
        fam_id = get_family_id(group["family"])
        for tier_idx, tier in enumerate(group["tiers"]):
            ess_suffix_families.append(fam_id)
            ess_suffix_tiers.append(tier_idx + 1)

    # ── Phase 1d: Fetch Alloy Pool (separate from essence/perfect_essence) ──
    alloy_prefix_families: list[int] = []
    alloy_prefix_tiers: list[int] = []
    alloy_suffix_families: list[int] = []
    alloy_suffix_tiers: list[int] = []

    alloy_result = pdb.get_craftable_mods(item_class, ilvl, pool="alloy")
    for group in alloy_result.get("prefixes", []):
        fam_id = get_family_id(group["family"])
        for tier_idx, tier in enumerate(group["tiers"]):
            alloy_prefix_families.append(fam_id)
            alloy_prefix_tiers.append(tier_idx + 1)
    for group in alloy_result.get("suffixes", []):
        fam_id = get_family_id(group["family"])
        for tier_idx, tier in enumerate(group["tiers"]):
            alloy_suffix_families.append(fam_id)
            alloy_suffix_tiers.append(tier_idx + 1)

    # ── Phase 1e: Fetch Desecrated Pool (for target detection) ──
    # We need to know which targets come from the desecrated pool so the
    # decomposer uses desecrate+reveal instead of exalt/essence.
    desecrated_result = pdb.get_craftable_mods(item_class, ilvl, pool="desecrated")
    desecrated_families: set[str] = set()
    desecrated_prefix_families: set[str] = set()
    desecrated_suffix_families: set[str] = set()
    for group in desecrated_result.get("prefixes", []):
        desecrated_families.add(group["family"])
        desecrated_prefix_families.add(group["family"])
        # Also register family IDs for desecrated mods (needed for target matching)
        get_family_id(group["family"])
    for group in desecrated_result.get("suffixes", []):
        desecrated_families.add(group["family"])
        desecrated_suffix_families.add(group["family"])
        get_family_id(group["family"])

    # Build set of normal pool families for detection
    normal_families: set[str] = set()
    for group in pool_result["prefixes"]:
        normal_families.add(group["family"])
    for group in pool_result["suffixes"]:
        normal_families.add(group["family"])

    # ── Phase 2: Build CraftTarget with resolved IDs ──
    targets: list[ModTarget] = []
    for family_name, affix_type, max_tier in target_mods:
        fam_id = get_family_id(family_name)

        # Detect which pool this target belongs to
        if family_name in normal_families:
            pool_source = "normal"
        elif family_name in desecrated_families:
            pool_source = "desecrated"
            log.info(f"Target '{family_name}' is a desecrated (abyss) mod → desecrate+reveal")
        else:
            pool_source = "normal"  # fallback, may not be craftable
            log.warning(f"Target '{family_name}' not found in normal or desecrated pool")

        targets.append(ModTarget(family_name, fam_id, affix_type, max_tier, pool_source))

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
        max_prefixes=_max_affixes(item_class),
        max_suffixes=_max_affixes(item_class),
        essence_prefix_families=ess_prefix_families or None,
        essence_prefix_tiers=ess_prefix_tiers or None,
        essence_suffix_families=ess_suffix_families or None,
        essence_suffix_tiers=ess_suffix_tiers or None,
        alloy_prefix_families=alloy_prefix_families or None,
        alloy_prefix_tiers=alloy_prefix_tiers or None,
        alloy_suffix_families=alloy_suffix_families or None,
        alloy_suffix_tiers=alloy_suffix_tiers or None,
        desecrated_prefix_pool_size=len(desecrated_prefix_families),
        desecrated_suffix_pool_size=len(desecrated_suffix_families),
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

    # ── Phase 4c: Abyss bone prices (desecrate cost) ──
    # Desecrate uses a bone at the Well of Souls. Fetch the cheapest common
    # bone price from the "abyss" category. Reveal is free (just picking).
    abyss_rows = pdb.get_bulk_prices("abyss", league)
    bone_prices = []
    for row in abyss_rows:
        name = row.get("name", "")
        val = row.get("chaos_value")
        # Only count craftable bones (Jawbone/Rib/Collarbone), not gazes/crania
        if val and val > 0 and any(b in name for b in ("Jawbone", "Rib", "Collarbone")):
            bone_prices.append(val)
    if bone_prices:
        bone_prices.sort()
        # Use the median of the 3 cheapest bones as representative cost
        cheapest = bone_prices[:3]
        desecrate_price = cheapest[len(cheapest) // 2]
    else:
        desecrate_price = 0.5  # fallback

    # Default prices for common currencies not tracked by poe.ninja (too cheap)
    _DEFAULTS: dict[str, float] = {
        "transmute": 0.01,
        "augment": 0.01,
        "alchemy": 0.02,
        "regal": 0.02,
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
        "alloy": 5.0,
        # Abyss: desecrate uses a bone, reveal is free (picking from options)
        "desecrate": desecrate_price,
        "reveal": 0.0,
    }
    for name, default_price in _DEFAULTS.items():
        if name not in currency_prices:
            currency_prices[name] = default_price

    # ── Phase 5: Trade API price lookups (best-effort) ──
    # Three lookups:
    #   1. base_white: white base item of the right type
    #   2. base_magic_with: magic items with each target mod (for buy_magic pricing)
    #   3. trade_finished: rare items with ALL target mods (for CRAFT vs BUY verdict)
    base_white = 1.0
    base_magic_with: dict[str, float] = {}
    base_fractured_with: dict[str, float] = {}
    trade_finished = float("inf")

    trade_prices = _lookup_trade_prices(
        pdb, league, item_class, ilvl, target_mods, targets,
        base_name=base_name,
    )
    if trade_prices.get("base_white"):
        base_white = max(trade_prices["base_white"], 0.5)
    if trade_prices.get("base_magic_with"):
        # Floor magic prices: buying a specific-mod magic item is never free.
        # Minimum = base_white (you still need the base) + a small crafting fee.
        magic_floor = base_white + 0.5
        base_magic_with = {
            k: max(v, magic_floor) for k, v in trade_prices["base_magic_with"].items()
        }
    if trade_prices.get("trade_finished"):
        # A finished rare with multiple target mods is never cheaper than
        # its base. Use a reasonable floor based on target count.
        n_targets = len(targets)
        finished_floor = base_white * max(n_targets, 2)
        trade_finished = max(trade_prices["trade_finished"], finished_floor)

    # Scouring = buying a new white base (no Orb of Scouring in PoE2)
    currency_prices["scouring"] = base_white
    # Reforge = 2 spare bases consumed
    currency_prices["reforge"] = base_white * 2

    prices = PriceCache(
        currency=currency_prices,
        omen=omen_prices,
        base_white=base_white,
        base_magic_with=base_magic_with,
        base_fractured_with=base_fractured_with,
        trade_finished=trade_finished,
        trade_urls=trade_prices.get("trade_urls", {}),
    )

    rune_info = f" | Runes: {', '.join(rune_pools)} (+{rune_mod_count} mods)" if rune_pools else ""
    log.info(
        f"Preflight: {item_class} ilvl{ilvl} | "
        f"Pool: {len(prefix_weights)}P + {len(suffix_weights)}S mods | "
        f"Prices: {len(currency_prices)} currencies, {len(omen_prices)} omens | "
        f"Targets: {[t.family for t in targets]}{rune_info}"
    )

    return pool_data, prices, target


# ── Display Info Lookup ──────────────────────────────────────────────────────

def lookup_display_info(
    item_class: str,
    target_mods: list[tuple[str, str, int]],
    db_path: str | None = None,
) -> dict:
    """Look up human-readable names for CLI display.

    Returns dict with:
        item_class_name: e.g. "Energy Shield Gloves" (from item_bases)
        example_base: e.g. "Stitched Gloves" (a representative base)
        mod_descriptions: {family: stat_text} e.g. {"ArcaneSurgeOnCrit": "(10-15)% chance to ..."}
    """
    import os
    import sqlite3

    db_path = db_path or os.environ.get("POE2_CRAFT_DB", "data/poe2_craft.db")
    if not os.path.exists(db_path):
        return {"item_class_name": item_class, "example_base": "", "mod_descriptions": {}}

    result: dict = {"item_class_name": item_class, "example_base": "", "mod_descriptions": {}}

    try:
        conn = sqlite3.connect(db_path)

        # Resolve item_class → slot + sub_type from item_bases
        # item_class like "Gloves_int" → tags contain "int_armour", slot = "Gloves"
        # item_class like "Amulets" → slot = "Amulet"
        attr_map = {"int": "int_armour", "str": "str_armour", "dex": "dex_armour",
                     "str_int": "str_int_armour", "str_dex": "str_dex_armour",
                     "dex_int": "dex_int_armour", "str_dex_int": "str_dex_int_armour"}

        # Split into base slot + optional attribute suffix
        # "Body_Armours_str_int" → base="Body_Armours", attr="str_int"
        # "Gloves_int" → base="Gloves", attr="int"
        # "Amulets" → base="Amulets", attr=""
        # "One_Hand_Swords" → base="One_Hand_Swords", attr=""
        attr_tag = ""
        base_slot = item_class
        for suffix, tag in sorted(attr_map.items(), key=lambda x: -len(x[0])):
            if item_class.endswith(f"_{suffix}"):
                base_slot = item_class[:-(len(suffix) + 1)]
                attr_tag = tag
                break

        # Map item_class base to DB slot name
        _SLOT_MAP = {
            "Gloves": "Gloves", "Boots": "Boots", "Helmets": "Helmet",
            "Body_Armours": "Body Armour", "Shields": "Shield", "Bucklers": "Shield",
            "Amulets": "Amulet", "Rings": "Ring", "Belts": "Belt",
            "Bows": "Bow", "Crossbows": "Crossbow", "Wands": "Wand",
            "Sceptres": "Sceptre", "Staves": "Staff", "Foci": "Focus",
            "Claws": "Claw", "Daggers": "Dagger", "Spears": "Spear",
            "Flails": "Flail", "Quarterstaves": "Staff", "Quivers": "Quiver",
            "One_Hand_Swords": "One Hand Sword", "One_Hand_Axes": "One Hand Axe",
            "One_Hand_Maces": "One Hand Mace", "Two_Hand_Swords": "Two Hand Sword",
            "Two_Hand_Axes": "Two Hand Axe", "Two_Hand_Maces": "Two Hand Mace",
            "Traps": "Trap", "Talismans": "Talisman",
            "Ruby": "Jewel", "Sapphire": "Jewel", "Diamond": "Jewel",
            "Emerald": "Jewel", "Time-Lost_Ruby": "Jewel",
            "Time-Lost_Sapphire": "Jewel", "Time-Lost_Diamond": "Jewel",
            "Time-Lost_Emerald": "Jewel",
        }
        db_slot = _SLOT_MAP.get(base_slot, base_slot)

        if db_slot == "Jewel":
            # Jewel item_classes ARE the jewel type (Ruby, Sapphire, Diamond, etc.)
            result["item_class_name"] = base_slot.replace("_", " ") + " Jewel"
            row = None
        elif attr_tag:
            # Use quoted JSON match to avoid "dex_armour" matching "str_dex_armour"
            row = conn.execute(
                "SELECT name, slot, sub_type FROM item_bases "
                'WHERE slot = ? AND tags LIKE ? AND tags NOT LIKE \'%runeforged%\' '
                "ORDER BY req_level DESC LIMIT 1",
                (db_slot, f'%"{attr_tag}"%'),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT name, slot, sub_type FROM item_bases "
                "WHERE slot = ? AND tags NOT LIKE '%runeforged%' "
                "ORDER BY req_level DESC LIMIT 1",
                (db_slot,),
            ).fetchone()

        if row:
            result["example_base"] = row[0]
            sub = row[2] or ""
            result["item_class_name"] = f"{sub} {row[1]}" if sub else row[1]

        # Look up stat_text for each target mod at the requested tier
        # Also detect desecrated-only mods (no tiers)
        result["desecrated_families"] = set()
        for family, affix_type, tier in target_mods:
            # Check normal pool first, then desecrated
            normal_rows = conn.execute(
                "SELECT stat_text FROM mod_weights "
                "WHERE mod_family = ? AND item_class = ? AND affix_type = ? "
                "AND pool = 'normal' ORDER BY req_level DESC",
                (family, item_class, affix_type),
            ).fetchall()
            if normal_rows:
                idx = min(tier - 1, len(normal_rows) - 1)
                result["mod_descriptions"][family] = normal_rows[idx][0]
            else:
                # Check desecrated pool
                des_row = conn.execute(
                    "SELECT stat_text FROM mod_weights "
                    "WHERE mod_family = ? AND item_class = ? AND affix_type = ? "
                    "AND pool = 'desecrated' LIMIT 1",
                    (family, item_class, affix_type),
                ).fetchone()
                if des_row:
                    result["desecrated_families"].add(family)
                    result["mod_descriptions"][family] = des_row[0]

        conn.close()
    except Exception:
        pass

    return result


# ── Trade API Price Lookups ──────────────────────────────────────────────────

import re

# Map item_class slug → trade2 API category value
_CLASS_TO_TRADE_CATEGORY: dict[str, str] = {
    "Gloves": "armour.gloves", "Boots": "armour.boots",
    "Helmets": "armour.helmet", "Body_Armours": "armour.chest",
    "Shields": "armour.shield", "Bucklers": "armour.buckler",
    "Amulets": "accessory.amulet", "Rings": "accessory.ring",
    "Belts": "accessory.belt", "Bows": "weapon.bow",
    "Crossbows": "weapon.crossbow", "Wands": "weapon.wand",
    "Sceptres": "weapon.sceptre", "Staves": "weapon.staff",
    "Foci": "armour.focus", "Claws": "weapon.claw",
    "Daggers": "weapon.dagger", "Spears": "weapon.spear",
    "Flails": "weapon.flail", "Quarterstaves": "weapon.warstaff",
    "Quivers": "armour.quiver", "Talismans": "weapon.talisman",
    "Traps": "weapon.crossbow",
    "One_Hand_Swords": "weapon.onesword", "One_Hand_Axes": "weapon.oneaxe",
    "One_Hand_Maces": "weapon.onemace", "Two_Hand_Swords": "weapon.twosword",
    "Two_Hand_Axes": "weapon.twoaxe", "Two_Hand_Maces": "weapon.twomace",
}


def _item_class_to_trade_category(item_class: str) -> str | None:
    """Map optimizer item_class slug to trade2 API category value."""
    # Strip attribute suffix: "Gloves_int" → "Gloves", "Body_Armours_str_int" → "Body_Armours"
    attr_suffixes = ["str_dex_int", "str_int", "str_dex", "dex_int", "str", "dex", "int"]
    base = item_class
    for suffix in attr_suffixes:
        if item_class.endswith(f"_{suffix}"):
            base = item_class[:-(len(suffix) + 1)]
            break
    return _CLASS_TO_TRADE_CATEGORY.get(base)


def _stat_text_to_trade_pattern(stat_text: str) -> str:
    """Normalize DB stat_text to trade API pattern.

    "Adds (37-55) to (63-94) Physical Damage" → "Adds # to # Physical Damage"
    "+(15-20)% to Fire Resistance" → "#% to Fire Resistance"
    "+5 to Level of all Melee Skills" → "# to Level of all Melee Skills"
    """
    # Replace (min-max) ranges with #
    pattern = re.sub(r'\(\d+(?:\.\d+)?-\d+(?:\.\d+)?\)', '#', stat_text)
    # Replace standalone numbers with # (but not inside words)
    pattern = re.sub(r'(?<![a-zA-Z])\d+(?:\.\d+)?(?![a-zA-Z])', '#', pattern)
    # Strip leading + (trade API uses bare #)
    pattern = re.sub(r'^\+#', '#', pattern)
    pattern = re.sub(r' \+#', ' #', pattern)
    return pattern


def _resolve_trade_stat_filter(
    pdb,
    item_class: str,
    family: str,
    affix_type: str,
    max_tier: int = 0,
    pool_source: str = "normal",
) -> dict | None:
    """Resolve a mod family to a trade API stat filter dict.

    Returns {"id": "explicit.stat_XXX", "min": N} or None.
    The "min" key is set to the lowest roll of the requested tier so the
    trade search only matches items with that tier or better.

    Uses the correct stat_type prefix:
    - normal pool → "explicit.stat_XXX"
    - desecrated pool → "desecrated.stat_XXX"
    """
    import sqlite3
    import os

    db_path = os.environ.get("POE2_CRAFT_DB", "data/poe2_craft.db")
    try:
        conn = sqlite3.connect(db_path)
        # Get all tiers for this family, ordered T1 (best) first
        rows = conn.execute(
            "SELECT stat_text, pool FROM mod_weights "
            "WHERE mod_family = ? AND item_class = ? AND affix_type = ? "
            "AND pool IN ('normal', 'desecrated') "
            "ORDER BY req_level DESC",
            (family, item_class, affix_type),
        ).fetchall()
        if not rows:
            conn.close()
            return None

        # Use first row for pattern + pool detection
        pattern = _stat_text_to_trade_pattern(rows[0][0])
        actual_pool = rows[0][1]

        # Trade API uses different stat_type prefixes per pool source
        stat_type = "desecrated" if actual_pool == "desecrated" else "explicit"
        trade_row = conn.execute(
            "SELECT stat_id FROM trade_stats "
            "WHERE stat_text = ? AND stat_type = ? LIMIT 1",
            (pattern, stat_type),
        ).fetchone()
        conn.close()
        if not trade_row:
            return None

        result: dict = {"id": trade_row[0]}

        # Extract min value from the requested tier's stat_text
        if max_tier > 0 and max_tier <= len(rows):
            tier_text = rows[max_tier - 1][0]  # T1=index 0, T2=index 1, ...
            min_val = _extract_stat_min(tier_text)
            if min_val is not None:
                result["min"] = min_val

        return result
    except Exception:
        pass
    return None


def _extract_stat_min(stat_text: str) -> float | None:
    """Extract the minimum numeric value from a stat_text.

    "(36-41) to maximum Energy Shield" → 36
    "+(85-99) to maximum Life" → 85
    "Adds (37-55) to (63-94) Physical Damage" → 37
    "(10-15)% chance to ..." → 10
    "+2 to Level of all Melee Skills" → 2
    """
    # Range pattern: (X-Y)
    m = re.search(r'\((-?[\d.]+)-[\d.]+\)', stat_text)
    if m:
        return float(m.group(1))
    # Flat value: "+N ..." or "N% ..." at start of text
    m = re.match(r'^\+?(-?[\d.]+)', stat_text)
    if m:
        return float(m.group(1))
    return None


def _trade_price_to_chaos(
    price_info: dict,
    chaos_rates: dict[str, float],
) -> float | None:
    """Convert a trade API price {amount, currency} to chaos equivalent.

    chaos_rates maps trade API currency slugs (e.g. "transmute") to chaos value
    per unit. Returns None if the currency is unknown.
    """
    amount = price_info.get("amount", 0)
    currency = price_info.get("currency", "")
    if not amount or not currency:
        return None
    if currency == "chaos":
        return float(amount)
    rate = chaos_rates.get(currency)
    if rate is None:
        log.debug(f"Trade: unknown currency '{currency}', cannot convert to chaos")
        return None
    return float(amount) * rate


def _build_chaos_rates(pdb, league: str) -> dict[str, float]:
    """Build a map from trade API currency slugs to chaos value per unit.

    Uses the prices table (poe.ninja data) to look up chaos_value for each
    currency, keyed by the trade API slug from _TRADE_CURRENCY_TO_DB.
    """
    rates: dict[str, float] = {"chaos": 1.0}
    currency_rows = pdb.get_bulk_prices("currency", league)
    # Build DB name → chaos_value lookup
    db_chaos: dict[str, float] = {}
    for row in currency_rows:
        if row.get("chaos_value"):
            db_chaos[row["name"]] = row["chaos_value"]
    # Map trade slugs to chaos values
    for slug, db_name in _TRADE_CURRENCY_TO_DB.items():
        if db_name in db_chaos:
            rates[slug] = db_chaos[db_name]
    return rates


def _lookup_trade_prices(
    pdb,
    league: str,
    item_class: str,
    ilvl: int,
    target_mods: list[tuple[str, str, int]],
    targets: list[ModTarget],
    base_name: str | None = None,
) -> dict:
    """Look up live trade prices for base items and target mods.

    Args:
        base_name: specific base item name (e.g. "Stitched Gloves").
            When provided, the white base lookup searches for this exact base
            instead of the generic category, giving a more accurate price.

    Returns dict with optional keys:
        base_white: float — median price of white base (in chaos)
        base_magic_with: dict[str, float] — magic item price per target family (in chaos)
        trade_finished: float — finished rare item with all targets (in chaos)

    All prices are converted to chaos equivalent using poe.ninja exchange rates.
    All lookups are best-effort; failures return empty dict.
    """
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError

    result: dict = {}
    category = _item_class_to_trade_category(item_class)
    if (not category and not base_name) or not league:
        return result

    try:
        tc = TradeClient()
    except Exception:
        return result

    chaos_rates = _build_chaos_rates(pdb, league)

    # ── 1. White base price ──
    try:
        if base_name:
            # Specific base: search by exact name for accurate pricing
            est = tc.estimate_price(
                league, base_name=base_name,
                ilvl_min=ilvl, rarity="normal", sample=5,
            )
        else:
            # Generic category search
            est = tc.estimate_trade_price(
                league, stat_filters=[], category=category,
                rarity="normal", ilvl_min=ilvl, sample=5,
            )
        if est.get("found") and est.get("median_price"):
            base_price = _trade_price_to_chaos(est["median_price"], chaos_rates)
            if base_price and base_price > 0:
                result["base_white"] = base_price
                cur = est["median_price"].get("currency", "?")
                amt = est["median_price"].get("amount", 0)
                label = base_name or "white base"
                log.info(f"Trade: {label} = {amt} {cur} → {base_price:.4f}c")
        if est.get("trade_url"):
            result.setdefault("trade_urls", {})["base_white"] = est["trade_url"]
    except Exception as e:
        log.debug(f"Trade: white base lookup failed: {e}")

    # ── 2. Magic items with each target mod (for buy_magic pricing) ──
    # Only look up normal-pool targets (desecrated mods can't be on trade items)
    magic_prices: dict[str, float] = {}
    for t in targets:
        if t.pool_source != "normal":
            continue
        stat_filter = _resolve_trade_stat_filter(
            pdb, item_class, t.family, t.affix_type, max_tier=t.max_tier,
        )
        if not stat_filter:
            log.debug(f"Trade: no stat_id for {t.family}, skipping magic price lookup")
            continue
        try:
            est = tc.estimate_trade_price(
                league,
                stat_filters=[stat_filter],
                category=category,
                rarity="magic",
                sample=5,
            )
            if est.get("found") and est.get("median_price"):
                price = _trade_price_to_chaos(est["median_price"], chaos_rates)
                if price and price > 0:
                    magic_prices[t.family] = price
                    cur = est["median_price"].get("currency", "?")
                    amt = est["median_price"].get("amount", 0)
                    log.info(f"Trade: magic {t.family} = {amt} {cur} → {price:.4f}c")
        except Exception as e:
            log.debug(f"Trade: magic {t.family} lookup failed: {e}")

    if magic_prices:
        result["base_magic_with"] = magic_prices

    # ── 3. Finished rare item with ALL target mods ──
    # Include both normal and desecrated targets (desecrated items appear on trade)
    all_stat_filters = []
    for t in targets:
        stat_filter = _resolve_trade_stat_filter(
            pdb, item_class, t.family, t.affix_type,
            max_tier=t.max_tier, pool_source=t.pool_source,
        )
        if stat_filter:
            all_stat_filters.append(stat_filter)

    has_desecrated = any(t.pool_source == "desecrated" for t in targets)
    if all_stat_filters:
        try:
            finished_kwargs: dict = {
                "category": category,
                "rarity": "nonunique",
            }
            if has_desecrated:
                finished_kwargs["desecrated"] = True
            est = tc.estimate_trade_price(
                league,
                stat_filters=all_stat_filters,
                stats_type="and",
                sample=5,
                **finished_kwargs,
            )
            if est.get("found") and est.get("median_price"):
                price = _trade_price_to_chaos(est["median_price"], chaos_rates)
                if price and price > 0:
                    result["trade_finished"] = price
                    cur = est["median_price"].get("currency", "?")
                    amt = est["median_price"].get("amount", 0)
                    log.info(f"Trade: finished item = {amt} {cur} → {price:.2f}c "
                             f"({est.get('total_listings', 0)} listings)")
            if est.get("trade_url"):
                result.setdefault("trade_urls", {})["trade_finished"] = est["trade_url"]
        except Exception as e:
            log.debug(f"Trade: finished item lookup failed: {e}")

    return result


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
