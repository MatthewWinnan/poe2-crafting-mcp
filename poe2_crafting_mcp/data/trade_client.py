"""
GGG official trade2 API client for PoE2 live price lookups.

Endpoints used:
  POST /api/trade2/search/<league>  — search by name/type, returns listing IDs
  GET  /api/trade2/fetch/<ids>      — fetch listing details (price, item info)

Rate limit: ~6 requests per 5s, 45 per 60s. We enforce a 1.5s delay between
search calls. Fetch calls consume the same budget — we batch 10 IDs per fetch.

No authentication required for read-only public trade searches.
"""
from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_BASE = "https://www.pathofexile.com/api/trade2"

# Map human-readable slot names → trade2 API category filter values.
# Keys are lowercase; values are the "option" string for type_filters.category.
SLOT_TO_CATEGORY: dict[str, str] = {
    # Armour
    "gloves":          "armour.gloves",
    "boots":           "armour.boots",
    "helmet":          "armour.helmet",
    "helm":            "armour.helmet",
    "body armour":     "armour.chest",
    "body":            "armour.chest",
    "chest":           "armour.chest",
    "shield":          "armour.shield",
    "quiver":          "armour.quiver",
    "focus":           "armour.focus",
    "buckler":         "armour.buckler",
    # Accessories
    "ring":            "accessory.ring",
    "amulet":          "accessory.amulet",
    "belt":            "accessory.belt",
    # Flasks
    "flask":           "flask",
    "life flask":      "flask.life",
    "mana flask":      "flask.mana",
    "charm":           "flask.charm",
    # Weapons — one-handed
    "sword":           "weapon.onesword",
    "one hand sword":  "weapon.onesword",
    "axe":             "weapon.oneaxe",
    "one hand axe":    "weapon.oneaxe",
    "mace":            "weapon.onemace",
    "one hand mace":   "weapon.onemace",
    "flail":           "weapon.flail",
    "claw":            "weapon.claw",
    "dagger":          "weapon.dagger",
    "sceptre":         "weapon.sceptre",
    "wand":            "weapon.wand",
    "talisman":        "weapon.talisman",
    # Weapons — two-handed
    "two hand sword":  "weapon.twosword",
    "two hand axe":    "weapon.twoaxe",
    "two hand mace":   "weapon.twomace",
    "bow":             "weapon.bow",
    "staff":           "weapon.staff",
    "crossbow":        "weapon.crossbow",
    "spear":           "weapon.spear",
    "quarterstaff":    "weapon.warstaff",
    "warstaff":        "weapon.warstaff",
    # Gems
    "gem":             "gem",
    "skill gem":       "gem.activegem",
    "support gem":     "gem.supportgem",
    "meta gem":        "gem.metagem",
    # Jewels
    "jewel":           "jewel",
    # Map / endgame
    "waystone":        "map.waystone",
    "tablet":          "map.tablet",
    "map fragment":    "map.fragment",
    "logbook":         "map.logbook",
    "breachstone":     "map.breachstone",
    "barya":           "map.barya",
    "pinnacle key":    "map.bosskey",
    "ultimatum key":   "map.ultimatum",
    # Currency subtypes
    "omen":            "currency.omen",
    "currency rune":   "currency.rune",
    "soul core":       "currency.soulcore",
    "idol":            "currency.idol",
    "card":            "card",
    "relic":           "sanctum.relic",
}
_TIMEOUT         = 10    # seconds
_SEARCH_DELAY    = 1.5   # seconds between search calls (rate-limit safety)
_FETCH_BATCH     = 10    # IDs per fetch call (API max is 10)
_DEFAULT_SAMPLE  = 5     # listings to fetch for price estimation

# Map trade2 API rarity values (int or string) → PoB/clipboard rarity names
_RARITY_NAMES: dict[int | str, str] = {
    0: "Normal",  1: "Magic",  2: "Rare",  3: "Unique",
    "normal": "Normal", "magic": "Magic", "rare": "Rare", "unique": "Unique",
}

# Map trade category strings → PoB slot names (used for simulate_trade_item hints)
CATEGORY_TO_POB_SLOT: dict[str, str] = {
    "armour.gloves":  "Gloves",
    "armour.boots":   "Boots",
    "armour.helmet":  "Helmet",
    "armour.chest":   "Body Armour",
    "armour.shield":  "Weapon 2",
    "armour.focus":   "Weapon 2",
    "armour.buckler": "Weapon 2",
    "armour.quiver":  "Weapon 2",
    "accessory.ring": "Ring 1",
    "accessory.amulet": "Amulet",
    "accessory.belt": "Belt",
    "weapon.onesword":  "Weapon 1",
    "weapon.twosword":  "Weapon 1",
    "weapon.oneaxe":    "Weapon 1",
    "weapon.twoaxe":    "Weapon 1",
    "weapon.onemace":   "Weapon 1",
    "weapon.twomace":   "Weapon 1",
    "weapon.flail":     "Weapon 1",
    "weapon.bow":       "Weapon 1",
    "weapon.crossbow":  "Weapon 1",
    "weapon.staff":     "Weapon 1",
    "weapon.warstaff":  "Weapon 1",
    "weapon.quarterstaff": "Weapon 1",
    "weapon.spear":     "Weapon 1",
    "weapon.wand":      "Weapon 1",
    "weapon.sceptre":   "Weapon 1",
    "weapon.dagger":    "Weapon 1",
    "weapon.claw":      "Weapon 1",
}


import re as _re

_WIKI_LINK_RE = _re.compile(r'\[(?:[^\]|]*\|)?([^\]]+)\]')


def _strip_wiki_links(text: str) -> str:
    """Convert [InternalName|DisplayName] → DisplayName, [Name] → Name."""
    return _WIKI_LINK_RE.sub(r'\1', text)


def _mod_text(m: object) -> str:
    """
    Extract human-readable text from a mod entry.

    PoE2 trade2 API returns mods as dicts: {description, domain, hash, mods:[...]}.
    PoE1-style and test fixtures use plain strings.
    Both are supported.
    """
    if isinstance(m, str):
        return _strip_wiki_links(m)
    if isinstance(m, dict):
        raw = m.get("description") or m.get("text") or m.get("line") or str(m)
        return _strip_wiki_links(str(raw))
    return str(m)


def _mod_tier(m: object) -> str:
    """Extract tier label from a mod dict (e.g. 'P1', 'S2'), or '' if not available."""
    if isinstance(m, dict):
        inner = m.get("mods") or []
        if inner and isinstance(inner[0], dict):
            return str(inner[0].get("tier", ""))
    return ""


def _mod_hash(m: object) -> str:
    """
    Extract the normalised stat ID from a mod dict.

    The API sends 'hash': 'stat.explicit.stat_4052037485'.
    We strip the leading 'stat.' so it matches our trade stat IDs.
    """
    if isinstance(m, dict):
        h = m.get("hash", "")
        if h.startswith("stat."):
            h = h[5:]
        return h
    return ""


def _trade_item_to_pob_text(item: dict) -> str:
    """
    Convert a trade2 API item JSON dict to PoB/in-game clipboard item text.

    Handles the PoE2 trade2 format where:
    - explicitMods/implicitMods/etc. are dicts: {description, hash, mods:[{tier,...}]}
    - Property and requirement names use wiki link syntax [Internal|Display]
    """
    lines: list[str] = []
    sep = "--------"

    # ── Rarity & name lines ───────────────────────────────────────────────────
    raw_rarity = item.get("rarity", 1)
    rarity_str = _RARITY_NAMES.get(raw_rarity, "Magic")
    lines.append(f"Rarity: {rarity_str}")

    name      = _strip_wiki_links((item.get("name") or "").strip())
    type_line = _strip_wiki_links((item.get("typeLine") or "").strip())
    base_type = _strip_wiki_links((item.get("baseType") or type_line).strip())

    if rarity_str in ("Rare", "Unique") and name:
        lines.append(name)
        lines.append(type_line or base_type)
    else:
        lines.append(type_line or base_type)

    lines.append(sep)

    # ── Properties (Energy Shield, Armour, DPS, APS, Quality, …) ─────────────
    props: list[dict] = item.get("properties") or []
    prop_lines: list[str] = []
    for prop in props:
        prop_name = _strip_wiki_links(prop.get("name", ""))
        values    = prop.get("values") or []
        disp      = prop.get("displayMode", 0)
        if not values:
            # Skip bare category labels like "Gloves" (type 109)
            if prop.get("type") == 109:
                continue
            prop_lines.append(prop_name)
            continue
        val_str = ", ".join(str(v[0]) for v in values)
        aug     = " (augmented)" if any(len(v) > 1 and v[1] == 1 for v in values) else ""
        if disp == 1:
            prop_lines.append(f"{val_str} {prop_name}{aug}")
        else:
            prop_lines.append(f"{prop_name}: {val_str}{aug}")
    if prop_lines:
        lines.extend(prop_lines)
        lines.append(sep)

    # ── Requirements ──────────────────────────────────────────────────────────
    reqs: list[dict] = item.get("requirements") or []
    if reqs:
        lines.append("Requirements:")
        for req in reqs:
            req_name = _strip_wiki_links(req.get("name", ""))
            req_vals = req.get("values") or []
            if req_vals:
                lines.append(f"{req_name}: {req_vals[0][0]}")
        lines.append(sep)

    # ── Sockets (PoE2 rune/bone sockets) ─────────────────────────────────────
    sockets: list[dict] = item.get("sockets") or []
    if sockets:
        socket_str = " ".join(s.get("sColour", "S") for s in sockets)
        lines.append(f"Sockets: {socket_str}")
        lines.append(sep)

    # ── Item Level ────────────────────────────────────────────────────────────
    ilvl = item.get("ilvl")
    if ilvl is not None:
        lines.append(f"Item Level: {ilvl}")
        lines.append(sep)

    # ── Enchant mods ──────────────────────────────────────────────────────────
    enchant_mods = item.get("enchantMods") or []
    if enchant_mods:
        for m in enchant_mods:
            lines.append(f"{_mod_text(m)} (enchant)")
        lines.append(sep)

    # ── Implicit mods ─────────────────────────────────────────────────────────
    implicit_mods = item.get("implicitMods") or []
    if implicit_mods:
        for m in implicit_mods:
            lines.append(_mod_text(m))
        lines.append(sep)

    # ── Explicit / fractured / crafted / rune / desecrated mods ──────────────
    explicit_mods   = item.get("explicitMods")    or []
    fractured_mods  = item.get("fracturedMods")   or []
    crafted_mods    = item.get("craftedMods")     or []
    rune_mods       = item.get("runeMods")        or []
    desecrated_mods = item.get("desecrated_mods") or item.get("desecratedMods") or []

    for m in explicit_mods:
        lines.append(_mod_text(m))
    for m in fractured_mods:
        lines.append(f"{_mod_text(m)} (fractured)")
    for m in crafted_mods:
        lines.append(f"{_mod_text(m)} (crafted)")
    for m in rune_mods:
        lines.append(f"{_mod_text(m)} (rune)")
    for m in desecrated_mods:
        lines.append(f"{_mod_text(m)} (desecrated)")

    # ── Special flags ─────────────────────────────────────────────────────────
    if item.get("corrupted"):
        lines.append(sep)
        lines.append("Corrupted")
    if fractured_mods or item.get("fractured"):
        lines.append("Fractured Item")
    if item.get("mirrored"):
        lines.append(sep)
        lines.append("Mirrored")

    return "\n".join(lines)


# Map poe.ninja currency IDs → display symbols
_CURRENCY_SYMBOLS: dict[str, str] = {
    "divine":    "d",
    "exalted":   "ex",
    "chaos":     "c",
    "transmute": "t",
    "augment":   "aug",
    "regal":     "regal",
    "annulment": "ann",
    "vaal":      "vaal",
}


def _rng(min_val: Any, max_val: Any = None) -> dict | None:
    """Build a {min, max} range dict, omitting None values. Returns None if both absent."""
    d: dict[str, Any] = {}
    if min_val is not None:
        d["min"] = min_val
    if max_val is not None:
        d["max"] = max_val
    return d or None


def _opt(value: str | None) -> dict | None:
    return {"option": value} if value is not None else None


def _bool_opt(value: bool | None) -> dict | None:
    return {"option": "true" if value else "false"} if value is not None else None


def build_api_filters(
    *,
    # type_filters
    category: str | None = None,
    rarity: str | None = None,
    ilvl_min: int | None = None,
    ilvl_max: int | None = None,
    quality_min: int | None = None,
    quality_max: int | None = None,
    # equipment_filters
    ar_min: int | None = None, ar_max: int | None = None,
    ev_min: int | None = None, ev_max: int | None = None,
    es_min: int | None = None, es_max: int | None = None,
    ward_min: int | None = None, ward_max: int | None = None,
    block_min: int | None = None, block_max: int | None = None,
    spirit_min: int | None = None,
    rune_sockets_min: int | None = None,
    dps_min: float | None = None, dps_max: float | None = None,
    pdps_min: float | None = None, pdps_max: float | None = None,
    edps_min: float | None = None, edps_max: float | None = None,
    aps_min: float | None = None, aps_max: float | None = None,
    crit_min: float | None = None, crit_max: float | None = None,
    reload_time_max: float | None = None,
    damage_min: float | None = None, damage_max: float | None = None,
    # req_filters
    req_level_max: int | None = None,
    req_str_max: int | None = None,
    req_dex_max: int | None = None,
    req_int_max: int | None = None,
    # misc_filters (None = unset, True/"true", False/"false")
    corrupted: bool | None = None,
    fractured_item: bool | None = None,
    identified: bool | None = None,
    desecrated: bool | None = None,
    mirrored: bool | None = None,
    crafted: bool | None = None,
    veiled: bool | None = None,
    twice_corrupted: bool | None = None,
    sanctified: bool | None = None,
    mutated: bool | None = None,
    gem_level_min: int | None = None,
    gem_level_max: int | None = None,
    gem_sockets_min: int | None = None,
    gem_sockets_max: int | None = None,
    area_level_min: int | None = None,
    area_level_max: int | None = None,
    stack_size_min: int | None = None,
    stack_size_max: int | None = None,
    affix_count_min: int | None = None,
    affix_count_max: int | None = None,
    # map_filters
    map_tier_min: int | None = None,
    map_tier_max: int | None = None,
    map_iir_min: int | None = None,
    map_packsize_min: int | None = None,
    map_magic_monsters_min: int | None = None,
    map_rare_monsters_min: int | None = None,
    # trade_filters
    indexed: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    price_currency: str | None = None,
    account: str | None = None,
    sale_type: str | None = None,
) -> dict[str, Any]:
    """
    Build the ``query.filters`` dict for a trade2 search request.

    All parameters are optional — only non-None values are included.
    Returns an empty dict if nothing is specified.

    Filter groups:
      type_filters      — category, rarity, ilvl, quality
      equipment_filters — ar/ev/es/ward/block/spirit/rune_sockets/dps/pdps/edps/aps/crit
      req_filters       — req_level/str/dex/int (max values)
      misc_filters      — corrupted, fractured_item, identified, desecrated, mirrored,
                          crafted, veiled, twice_corrupted, gem_level, gem_sockets,
                          area_level, stack_size
      map_filters       — map_tier, map_iir, map_packsize, map_magic_monsters, map_rare_monsters
      trade_filters     — indexed, price, account, sale_type
    """
    filters: dict[str, Any] = {}

    # ── type_filters ─────────────────────────────────────────────────────────
    type_f: dict[str, Any] = {}
    if category is not None:
        type_f["category"] = {"option": category}
    if rarity is not None:
        type_f["rarity"] = {"option": rarity}
    if (v := _rng(ilvl_min, ilvl_max)) is not None:
        type_f["ilvl"] = v
    if (v := _rng(quality_min, quality_max)) is not None:
        type_f["quality"] = v
    if type_f:
        filters["type_filters"] = {"filters": type_f}

    # ── equipment_filters ─────────────────────────────────────────────────────
    equip_f: dict[str, Any] = {}
    for key, mn, mx in [
        ("ar",      ar_min,     ar_max),
        ("ev",      ev_min,     ev_max),
        ("es",      es_min,     es_max),
        ("ward",    ward_min,   ward_max),
        ("block",   block_min,  block_max),
        ("dps",     dps_min,    dps_max),
        ("pdps",    pdps_min,   pdps_max),
        ("edps",    edps_min,   edps_max),
        ("aps",     aps_min,    aps_max),
        ("crit",    crit_min,   crit_max),
        ("damage",  damage_min, damage_max),
    ]:
        if (v := _rng(mn, mx)) is not None:
            equip_f[key] = v
    if spirit_min is not None:
        equip_f["spirit"] = {"min": spirit_min}
    if rune_sockets_min is not None:
        equip_f["rune_sockets"] = {"min": rune_sockets_min}
    if reload_time_max is not None:
        equip_f["reload_time"] = {"max": reload_time_max}
    if equip_f:
        filters["equipment_filters"] = {"filters": equip_f}

    # ── req_filters ────────────��──────────────────────────────────────────────
    req_f: dict[str, Any] = {}
    if req_level_max is not None:
        req_f["lvl"] = {"max": req_level_max}
    if req_str_max is not None:
        req_f["str"] = {"max": req_str_max}
    if req_dex_max is not None:
        req_f["dex"] = {"max": req_dex_max}
    if req_int_max is not None:
        req_f["int"] = {"max": req_int_max}
    if req_f:
        filters["req_filters"] = {"filters": req_f}

    # ── misc_filters ───────────���──────────────────────────────────────────────
    misc_f: dict[str, Any] = {}
    for key, val in [
        ("corrupted",        corrupted),
        ("fractured_item",   fractured_item),
        ("identified",       identified),
        ("desecrated",       desecrated),
        ("mirrored",         mirrored),
        ("crafted",          crafted),
        ("veiled",           veiled),
        ("twice_corrupted",  twice_corrupted),
        ("sanctified",       sanctified),
        ("mutated",          mutated),
    ]:
        if (v := _bool_opt(val)) is not None:
            misc_f[key] = v
    if (v := _rng(gem_level_min, gem_level_max)) is not None:
        misc_f["gem_level"] = v
    if (v := _rng(gem_sockets_min, gem_sockets_max)) is not None:
        misc_f["gem_sockets"] = v
    if (v := _rng(area_level_min, area_level_max)) is not None:
        misc_f["area_level"] = v
    if (v := _rng(stack_size_min, stack_size_max)) is not None:
        misc_f["stack_size"] = v
    # NOTE: affix_count_min/max is NOT sent to the trade2 API (rejected as invalid filter).
    # It is handled as a client-side filter in estimate_trade_price().
    if misc_f:
        filters["misc_filters"] = {"filters": misc_f}

    # ── map_filters ─────────��──────────────────────────────��──────────────────
    map_f: dict[str, Any] = {}
    if (v := _rng(map_tier_min, map_tier_max)) is not None:
        map_f["map_tier"] = v
    if map_iir_min is not None:
        map_f["map_iir"] = {"min": map_iir_min}
    if map_packsize_min is not None:
        map_f["map_packsize"] = {"min": map_packsize_min}
    if map_magic_monsters_min is not None:
        map_f["map_magic_monsters"] = {"min": map_magic_monsters_min}
    if map_rare_monsters_min is not None:
        map_f["map_rare_monsters"] = {"min": map_rare_monsters_min}
    if map_f:
        filters["map_filters"] = {"filters": map_f}

    # ── trade_filters ─────────────────────────────────────────────────────────
    trade_f: dict[str, Any] = {}
    if indexed is not None:
        trade_f["indexed"] = {"option": indexed}
    if sale_type is not None:
        trade_f["sale_type"] = {"option": sale_type}
    if account is not None:
        trade_f["account"] = {"input": account}
    price_d: dict[str, Any] = {}
    if price_min is not None:
        price_d["min"] = price_min
    if price_max is not None:
        price_d["max"] = price_max
    if price_currency is not None:
        price_d["option"] = price_currency
    if price_d:
        trade_f["price"] = price_d
    if trade_f:
        filters["trade_filters"] = {"filters": trade_f}

    return filters


def _build_stats_block(
    stat_filters: list[dict] | None,
    stats_type: str,
    stats_min_count: int | None,
    stat_groups: list[dict] | None,
) -> list[dict]:
    """
    Build the ``query.stats`` list for a trade2 search request.

    Two modes:
      stat_groups provided  → each group becomes one stats block (type/filters/min_count from group)
      otherwise             → stat_filters + stats_type + stats_min_count become one block

    stat_groups format:
      [{"filters": [{"id": ..., "min"?: ..., "max"?: ...}], "type"?: "and", "min_count"?: int}]
    """
    def _to_api_filters(raw_filters: list[dict]) -> list[dict]:
        result = []
        for sf in raw_filters:
            entry: dict[str, Any] = {"id": sf["id"], "disabled": False}
            value: dict[str, Any] = {}
            if sf.get("min") is not None:
                value["min"] = sf["min"]
            if sf.get("max") is not None:
                value["max"] = sf["max"]
            if value:
                entry["value"] = value
            result.append(entry)
        return result

    if stat_groups:
        blocks = []
        for group in stat_groups:
            api_filters = _to_api_filters(group.get("filters", []))
            if not api_filters:
                continue
            gtype = group.get("type", "and")
            block: dict[str, Any] = {"type": gtype, "filters": api_filters}
            mc = group.get("min_count")
            if gtype == "count" and mc is not None:
                block["value"] = {"min": mc}
            blocks.append(block)
        return blocks

    api_filters = _to_api_filters(stat_filters or [])
    if not api_filters:
        return []
    block = {"type": stats_type, "filters": api_filters}
    if stats_type == "count" and stats_min_count is not None:
        block["value"] = {"min": stats_min_count}
    return [block]


def _lookup_unique_base(name: str) -> str | None:
    """Look up the base type of a unique item from the game DB."""
    try:
        from poe2_crafting_mcp.data.database import PoBDatabase
        db = PoBDatabase()
        row = db._conn.execute(
            "SELECT base_type FROM uniques WHERE name = ? LIMIT 1", (name,)
        ).fetchone()
        return row["base_type"] if row else None
    except Exception:
        return None


class TradeError(Exception):
    """Raised when a GGG trade2 API call fails."""


class TradeClient:
    """
    Thin wrapper around the PoE2 trade2 API for live item price lookups.

    Respects rate limits via delays. Returns plain dicts — no HTTP types leak.
    """

    def __init__(self) -> None:
        self._last_search_at: float = 0.0

    # ── Internal ─────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent":   "poe2-crafting-mcp/1.0 (github: poe2-crafting-mcp)",
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def _post(self, path: str, body: dict) -> Any:
        url = f"{_BASE}/{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            try:
                err = json.loads(body_bytes).get("error", {})
                msg = err.get("message", str(e))
            except Exception:
                msg = str(e)
            raise TradeError(f"HTTP {e.code}: {msg}") from e
        except urllib.error.URLError as e:
            raise TradeError(f"Network error: {e.reason}") from e

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        qs = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{_BASE}/{path}{qs}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise TradeError(f"HTTP {e.code} from trade API") from e
        except urllib.error.URLError as e:
            raise TradeError(f"Network error: {e.reason}") from e

    def _rate_limit_wait(self) -> None:
        elapsed = time.monotonic() - self._last_search_at
        if elapsed < _SEARCH_DELAY:
            time.sleep(_SEARCH_DELAY - elapsed)
        self._last_search_at = time.monotonic()

    # ── Static Data ───────────────────────────────────────────────────────────

    def fetch_stats(self) -> list[dict]:
        """
        Fetch all explicit/implicit/pseudo stat entries from the trade2 API.

        Returns a list of {stat_id, stat_text, stat_type} dicts ready for
        PriceDatabase.upsert_trade_stats().

        This is a one-time setup call (~1-2s, ~6000 entries). Cache the
        result via PriceDatabase — no need to call more than once per session.
        """
        resp = self._get("data/stats")
        stats: list[dict] = []
        for group in resp.get("result", []):
            stat_type = group.get("label", "Explicit").lower()
            for entry in group.get("entries", []):
                sid  = entry.get("id", "")
                text = entry.get("text", "")
                if sid and text:
                    stats.append({
                        "stat_id":   sid,
                        "stat_text": text,
                        "stat_type": stat_type,
                    })
        return stats

    # ── Search ────────────────────────────────────────────────────────────────

    def search_unique(self, league: str, name: str) -> tuple[str, list[str]]:
        """
        Search for a unique item by name. Returns (search_id, result_ids).

        result_ids is sorted by price ascending (cheapest first).
        """
        # Look up base type from game DB to satisfy the trade API requirement
        # that unique searches include both name + type.
        base_type = _lookup_unique_base(name)

        self._rate_limit_wait()
        query: dict = {
            "status": {"option": "securable"},
            "name": name,
        }
        if base_type:
            query["type"] = base_type

        resp = self._post(f"search/poe2/{urllib.parse.quote(league)}", {
            "query": query,
            "sort": {"price": "asc"},
        })
        if "error" in resp:
            raise TradeError(resp["error"].get("message", str(resp["error"])))
        return resp["id"], resp.get("result", [])

    def search_base(
        self,
        league: str,
        base_name: str,
        ilvl_min: int = 80,
        rarity: str = "nonunique",
    ) -> tuple[str, list[str]]:
        """
        Search for a base item by exact type name + minimum item level.

        rarity: "nonunique" (default) | "normal" | "magic" | "rare" | "any"
        Returns (search_id, result_ids) sorted by price ascending.
        """
        self._rate_limit_wait()
        filters: dict[str, Any] = {
            "equipment_filters": {
                "filters": {
                    "ilvl": {"min": ilvl_min},
                }
            }
        }
        if rarity and rarity != "any":
            filters["type_filters"] = {
                "filters": {
                    "rarity": {"option": rarity},
                }
            }

        resp = self._post(f"search/poe2/{urllib.parse.quote(league)}", {
            "query": {
                "status": {"option": "securable"},
                "type": base_name,
                "filters": filters,
                "stats": [],
            },
            "sort": {"price": "asc"},
        })
        if "error" in resp:
            raise TradeError(resp["error"].get("message", str(resp["error"])))
        return resp["id"], resp.get("result", [])

    def search_trade(
        self,
        league: str,
        stat_filters: list[dict] | None = None,
        stats_type: str = "and",
        stats_min_count: int | None = None,
        stat_groups: list[dict] | None = None,
        **filter_kwargs: Any,
    ) -> tuple[str, list[str]]:
        """
        Search the trade site by stat filters and/or item property filters.

        Single-group mode (stat_filters):
          stat_filters: [{"id": "explicit.stat_XXX", "min"?: float, "max"?: float}]
          stats_type:   "and" | "if" | "count" | "not" | "weight"
          stats_min_count: min matching stats for stats_type="count"

        Multi-group mode (stat_groups, overrides stat_filters):
          stat_groups: [
            {"filters": [{"id": ..., "min"?: ..., "max"?: ...}],
             "type"?: "and",
             "min_count"?: int},
            ...
          ]
          Each entry becomes an independent stats block in the query.

        **filter_kwargs: any parameters accepted by build_api_filters()
          (category, rarity, ilvl_min/max, quality, ar/ev/es, corrupted, etc.)

        Returns (search_id, result_ids) sorted by price ascending.
        """
        self._rate_limit_wait()
        filters = build_api_filters(**filter_kwargs)
        stats_block = _build_stats_block(stat_filters, stats_type, stats_min_count, stat_groups)
        resp = self._post(f"search/poe2/{urllib.parse.quote(league)}", {
            "query": {
                "status": {"option": "securable"},
                "filters": filters,
                "stats": stats_block,
            },
            "sort": {"price": "asc"},
        })
        if "error" in resp:
            raise TradeError(resp["error"].get("message", str(resp["error"])))
        return resp["id"], resp.get("result", [])

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def fetch_listings(self, search_id: str, result_ids: list[str]) -> list[dict]:
        """
        Fetch listing details for the given IDs, batching in groups of _FETCH_BATCH (10).

        Returns list of dicts with:
          name, base_type, rarity, ilvl, corrupted, fractured,
          price_amount, price_currency, account,
          mods: {implicit, explicit, fractured, crafted, enchant, rune},
          item_text: PoB/clipboard format — pass directly to equip_item().
        """
        if not result_ids:
            return []
        results = []
        for batch_start in range(0, len(result_ids), _FETCH_BATCH):
            batch = result_ids[batch_start : batch_start + _FETCH_BATCH]
            ids_str = ",".join(batch)
            resp = self._get(f"fetch/{ids_str}", {"query": search_id, "realm": "poe2"})
            for r in resp.get("result", []):
                item    = r.get("item", {})
                listing = r.get("listing", {})
                price   = listing.get("price", {})
                results.append({
                    "name":           item.get("name", ""),
                    "base_type":      item.get("baseType", ""),
                    "rarity":         _RARITY_NAMES.get(item.get("rarity", 1), "Magic"),
                    "ilvl":           item.get("ilvl", 0),
                    "corrupted":      item.get("corrupted", False),
                    "fractured":      bool(item.get("fracturedMods") or item.get("fractured")),
                    "price_amount":   price.get("amount"),
                    "price_currency": price.get("currency", ""),
                    "account":        listing.get("account", {}).get("name", ""),
                    "mods": {
                        k: [
                            {"text": _mod_text(m), "tier": _mod_tier(m), "hash": _mod_hash(m)}
                            if isinstance(m, dict) else {"text": _mod_text(m), "tier": "", "hash": ""}
                            for m in (item.get(field) or [])
                        ]
                        for k, field in [
                            ("implicit",    "implicitMods"),
                            ("explicit",    "explicitMods"),
                            ("fractured",   "fracturedMods"),
                            ("crafted",     "craftedMods"),
                            ("enchant",     "enchantMods"),
                            ("rune",        "runeMods"),
                            ("desecrated",  "desecratedMods"),
                        ]
                    },
                    "item_text": _trade_item_to_pob_text(item),
                })
        return results

    # ── Price Estimation ──────────────────────────────────────────────────────

    def estimate_price(
        self,
        league: str,
        name: str | None = None,
        base_name: str | None = None,
        ilvl_min: int = 80,
        rarity: str = "nonunique",
        sample: int = _DEFAULT_SAMPLE,
    ) -> dict:
        """
        Get a price estimate for a unique item or base item.

        Provide `name` for uniques, `base_name` for item bases.
        rarity: "nonunique" | "normal" | "magic" | "rare" | "any" (for base searches)
        Returns a result dict with trade_url, min_price, median_price, listings, etc.

        Returns:
            {
              found: bool,
              name: str,
              total_listings: int,
              sample_size: int,
              min_price: {amount, currency},
              median_price: {amount, currency},
              trade_url: str,
              listings: [{name, base_type, ilvl, price_amount, price_currency}, ...],
              note: str (if any issue),
            }
        """
        try:
            if name:
                try:
                    search_id, ids = self.search_unique(league, name)
                except TradeError as e:
                    # "Unknown item name/base type" → not a unique item.
                    # Fall back to a direct type search.
                    if "Unknown item" in str(e):
                        search_id, ids = self.search_base(
                            league, name, ilvl_min=0, rarity="any"
                        )
                    else:
                        raise
            elif base_name:
                search_id, ids = self.search_base(
                    league, base_name, ilvl_min=ilvl_min, rarity=rarity
                )
            else:
                raise TradeError("Must provide name or base_name")
        except TradeError as e:
            return {"found": False, "error": str(e)}

        trade_url = (
            f"https://www.pathofexile.com/trade2/search/"
            f"{urllib.parse.quote(league)}/{search_id}"
        )

        total = len(ids)
        if total == 0:
            return {
                "found": False,
                "name": name or base_name,
                "total_listings": 0,
                "trade_url": trade_url,
                "note": "No listings found on trade.",
            }

        listings = self.fetch_listings(search_id, ids[:sample])

        # Extract numeric prices — try to normalise to the dominant currency
        prices_by_currency: dict[str, list[float]] = {}
        for lst in listings:
            amt = lst.get("price_amount")
            cur = lst.get("price_currency", "")
            if amt is not None and cur:
                prices_by_currency.setdefault(cur, []).append(float(amt))

        # Pick the most common currency
        if not prices_by_currency:
            return {
                "found": True,
                "name": name or base_name,
                "total_listings": total,
                "sample_size": len(listings),
                "trade_url": trade_url,
                "listings": listings,
                "note": "Could not extract prices from listings.",
            }

        dominant_cur = max(prices_by_currency, key=lambda c: len(prices_by_currency[c]))
        prices = sorted(prices_by_currency[dominant_cur])
        min_price = prices[0]
        median_price = statistics.median(prices)

        return {
            "found": True,
            "name": name or base_name,
            "total_listings": total,
            "sample_size": len(listings),
            "min_price":    {"amount": min_price,    "currency": dominant_cur},
            "median_price": {"amount": median_price, "currency": dominant_cur},
            "trade_url": trade_url,
            "listings": listings,
        }

    def estimate_trade_price(
        self,
        league: str,
        stat_filters: list[dict] | None = None,
        stats_type: str = "and",
        stats_min_count: int | None = None,
        stat_groups: list[dict] | None = None,
        sample: int = _DEFAULT_SAMPLE,
        affix_filter: str | None = None,
        affix_count_min: int | None = None,
        affix_count_max: int | None = None,
        **filter_kwargs: Any,
    ) -> dict:
        """
        Estimate the price of items matching stat filters and/or property filters.

        stat_filters: [{id, min?, max?}]  — explicit stat IDs with optional bounds.
        stats_type: "and" | "if" | "count" | "not" | "weight"
        stats_min_count: for stats_type="count", minimum number of matching stats
        stat_groups: list of {filters, type?, min_count?} for multiple stat blocks
        affix_filter: optional stat_id (e.g. "explicit.stat_4052037485") — after
            fetching, keep only listings that contain this stat in any mod slot.
            Useful for client-side affix verification when the trade query is broad.
        affix_count_min/max: client-side filter on total affix count (explicit + fractured).
            Useful to find magic items with exactly 1 affix, e.g. affix_count_max=1.
            NOTE: not sent to the trade2 API (unsupported), applied post-fetch.
        **filter_kwargs: passed directly to build_api_filters() — see search_trade() docstring.

        Returns the same shape as estimate_price():
            {found, total_listings, min_price, median_price, trade_url, listings, ...}
        """
        label = filter_kwargs.get("category") or "any slot"
        try:
            search_id, ids = self.search_trade(
                league, stat_filters,
                stats_type=stats_type, stats_min_count=stats_min_count,
                stat_groups=stat_groups,
                **filter_kwargs,
            )
        except TradeError as e:
            return {"found": False, "error": str(e)}

        trade_url = (
            f"https://www.pathofexile.com/trade2/search/"
            f"{urllib.parse.quote(league)}/{search_id}"
        )

        total = len(ids)
        if total == 0:
            return {
                "found": False,
                "category": label,
                "rarity": filter_kwargs.get("rarity", ""),
                "total_listings": 0,
                "trade_url": trade_url,
                "note": "No listings found matching these stat filters.",
            }

        listings = self.fetch_listings(search_id, ids[:sample])

        # Client-side affix filter: keep only listings containing the given stat_id
        if affix_filter:
            _MOD_SLOTS = ("explicit", "fractured", "crafted", "implicit", "enchant")
            filtered_listings = []
            for lst in listings:
                mods = lst.get("mods") or {}
                matched = any(
                    mod.get("hash") == affix_filter
                    for slot in _MOD_SLOTS
                    for mod in (mods.get(slot) or [])
                )
                if matched:
                    filtered_listings.append(lst)
            listings = filtered_listings

        # Client-side affix count filter: count explicit + fractured mods
        if affix_count_min is not None or affix_count_max is not None:
            filtered_listings = []
            for lst in listings:
                mods = lst.get("mods") or {}
                count = len(mods.get("explicit") or []) + len(mods.get("fractured") or [])
                if affix_count_min is not None and count < affix_count_min:
                    continue
                if affix_count_max is not None and count > affix_count_max:
                    continue
                filtered_listings.append(lst)
            listings = filtered_listings

        prices_by_currency: dict[str, list[float]] = {}
        for lst in listings:
            amt = lst.get("price_amount")
            cur = lst.get("price_currency", "")
            if amt is not None and cur:
                prices_by_currency.setdefault(cur, []).append(float(amt))

        if not prices_by_currency:
            return {
                "found": True,
                "category": label,
                "rarity": filter_kwargs.get("rarity", ""),
                "total_listings": total,
                "sample_size": len(listings),
                "trade_url": trade_url,
                "listings": listings,
                "note": "Could not extract prices from listings.",
            }

        dominant_cur = max(prices_by_currency, key=lambda c: len(prices_by_currency[c]))
        prices = sorted(prices_by_currency[dominant_cur])
        min_price = prices[0]
        median_price = statistics.median(prices)

        return {
            "found": True,
            "category": label,
            "rarity": filter_kwargs.get("rarity", ""),
            "total_listings": total,
            "sample_size": len(listings),
            "min_price":    {"amount": min_price,    "currency": dominant_cur},
            "median_price": {"amount": median_price, "currency": dominant_cur},
            "trade_url": trade_url,
            "listings": listings,
        }
