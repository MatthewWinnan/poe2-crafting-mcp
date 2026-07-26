"""
poe2-price — economy CLI for PoE2 price lookups and item searches.

Usage:
    poe2-price status                           # data freshness + active league
    poe2-price league                           # detect current league from poe.ninja
    poe2-price refresh [--league NAME]          # fetch fresh prices from poe.ninja
    poe2-price general <name>                   # currency / fragment / rune / omen price
    poe2-price equipment <name> [OPTIONS]       # unique item or equipment base price
    poe2-price atlas <name>                     # atlas tablet price
    poe2-price list <category>                  # all cached prices for a category
    poe2-price search <stat> [OPTIONS]          # find items by stat, show with prices

Examples:
    poe2-price status
    poe2-price league
    poe2-price refresh
    poe2-price general "Divine Orb"
    poe2-price general "Lesser Essence of Electricity"
    poe2-price equipment "Winter's Bite"
    poe2-price equipment "Titan Greaves" --base --rarity magic
    poe2-price equipment "Titan Greaves" --base --rarity rare
    poe2-price atlas "Augmented Pinnacle Tablet"
    poe2-price list currency
    poe2-price list unique --limit 20
    poe2-price search "maximum life" --type unique --slot ring
    poe2-price search "energy shield" --type base --slot "Body Armour"

    poe2-price stats --refresh                                      # fetch ~6000 stat IDs
    poe2-price stats --search "energy shield"                       # find stat ID for ES
    poe2-price trade "energy shield" --slot gloves --rarity magic   # magic gloves with ES
    poe2-price trade "energy shield" --slot gloves --tier 1
    poe2-price trade "maximum life" --slot ring --rarity rare --min 80
    poe2-price trade "movement speed" --slot boots --fractured --not-corrupted
    poe2-price trade "energy shield" --slot helmet --tier 1 --indexed 1day
    poe2-price trade "cold damage" --slot staff --rarity rare --dps-min 200
    poe2-price trade "dexterity" --slot ring --gem-level-min 20 --slot "skill gem"
    poe2-price trade "map quantity" --slot waystone --map-tier-min 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── ANSI helpers ──────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[90m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_BLUE   = "\033[34m"
_PURPLE = "\033[35m"
_RED    = "\033[31m"
_ORANGE = "\033[38;5;208m"


def _disable_color() -> None:
    global _RESET, _BOLD, _DIM, _YELLOW, _CYAN, _GREEN, _BLUE, _PURPLE, _RED, _ORANGE
    _RESET = _BOLD = _DIM = _YELLOW = _CYAN = _GREEN = _BLUE = _PURPLE = _RED = _ORANGE = ""


def _h(text: str) -> str:
    pad = max(0, 52 - len(text))
    return f"{_BOLD}{_YELLOW}── {text} {'─'*pad}{_RESET}"


def _status_icon(status: str) -> str:
    icons = {
        "fresh":        f"{_GREEN}✓ fresh{_RESET}",
        "stale_ttl":    f"{_YELLOW}⚠ stale (TTL){_RESET}",
        "stale_league": f"{_RED}✗ wrong league{_RESET}",
        "stale_age":    f"{_YELLOW}⚠ old data{_RESET}",
        "missing":      f"{_RED}✗ not cached{_RESET}",
        "never_run":    f"{_RED}✗ never run{_RESET}",
        "unknown":      f"{_DIM}? unknown{_RESET}",
    }
    return icons.get(status, status)


# ── Price formatters ──────────────────────────────────────────────────────────

def _fmt_chaos(chaos: float | None) -> str:
    if chaos is None:
        return f"{_DIM}—{_RESET}"
    if chaos >= 100:
        return f"{_YELLOW}{_BOLD}{chaos:.0f}c{_RESET}"
    if chaos >= 1:
        return f"{_CYAN}{chaos:.1f}c{_RESET}"
    return f"{_DIM}{chaos:.2f}c{_RESET}"


def _fmt_divine(divine: float | None) -> str:
    if divine is None or divine < 0.01:
        return ""
    return f"  {_YELLOW}({divine:.2f}d){_RESET}"


def _fmt_exalt(exalt: float | None) -> str:
    if exalt is None or exalt < 0.01 or exalt > 999:
        return ""
    return f"  {_GREEN}({exalt:.2f}ex){_RESET}"


def _get_exalt_rate(pdb: object, league: str) -> float | None:
    """Return the chaos value of one Exalted Orb, or None if uncached."""
    try:
        row = pdb.get_price("Exalted Orb", league, "currency")
        if row and row.get("chaos_value"):
            return float(row["chaos_value"])
    except Exception:
        pass
    return None


def _fmt_price_row(row: dict, indent: int = 2, exalt_rate: float | None = None) -> None:
    pad = " " * indent
    name = row.get("name", "?")
    cat  = row.get("category", "")
    cat_color = {
        "currency": _CYAN, "fragment": _BLUE,
        "unique": _PURPLE, "base": _GREEN, "gem": _ORANGE,
    }.get(cat, _DIM)
    chaos  = row.get("chaos_value")
    divine = row.get("divine_value")
    count  = row.get("listing_count", 0)

    exalt = (chaos / exalt_rate) if (chaos and exalt_rate) else None

    print(f"{pad}{_BOLD}{name}{_RESET}  {cat_color}[{cat}]{_RESET}")
    print(f"{pad}  {_fmt_chaos(chaos)}{_fmt_divine(divine)}{_fmt_exalt(exalt)}  "
          f"{_DIM}{count:,} listings{_RESET}")


def _fmt_price_inline(row: dict, exalt_rate: float | None = None) -> str:
    """Single-line price string for search result annotations."""
    chaos  = row.get("chaos_value")
    divine = row.get("divine_value")
    count  = row.get("listing_count", 0)
    exalt  = (chaos / exalt_rate) if (chaos and exalt_rate) else None
    price  = _fmt_chaos(chaos) + _fmt_divine(divine) + _fmt_exalt(exalt)
    return f"{price}  {_DIM}({count:,} listings){_RESET}"


# ── Trade result formatter ────────────────────────────────────────────────────

def _fmt_trade_result(result: dict, exalt_rate: float | None = None,
                      divine_rate: float | None = None,
                      show_items: bool = False) -> None:
    """Pretty-print a TradeClient.estimate_price() result."""
    if not result.get("found"):
        err = result.get("error") or result.get("note") or "Not found"
        print(f"  {_RED}{err}{_RESET}")
        if result.get("trade_url"):
            print(f"  {_DIM}Verify:{_RESET}  {_BLUE}{result['trade_url']}{_RESET}")
        return

    def _to_chaos(amt: float, cur: str) -> float | None:
        if cur in ("chaos", "chaos_orb"):
            return amt
        if cur in ("divine", "divine_orb") and divine_rate:
            return amt * divine_rate
        return None

    def _exalt_suffix(amt: float, cur: str) -> str:
        chaos = _to_chaos(amt, cur)
        if chaos and exalt_rate:
            ex = chaos / exalt_rate
            return _fmt_exalt(ex)
        return ""

    name     = result.get("name", "?")
    total    = result.get("total_listings", 0)
    sample   = result.get("sample_size", 0)
    min_p    = result.get("min_price", {})
    med_p    = result.get("median_price", {})

    print(_h(f"Live Price — {name}"))
    print(f"  {_DIM}Total listings:{_RESET} {total:,}  {_DIM}(sampled {sample}){_RESET}")
    if min_p:
        amt = min_p["amount"]; cur = min_p["currency"]
        print(f"  {_BOLD}Min:   {_RESET}{_CYAN}{amt} {cur}{_RESET}"
              + _exalt_suffix(amt, cur))
    if med_p:
        amt = med_p["amount"]; cur = med_p["currency"]
        print(f"  {_BOLD}Median:{_RESET}{_YELLOW}{amt} {cur}{_RESET}"
              + _exalt_suffix(amt, cur))
    if result.get("trade_url"):
        print(f"  {_DIM}Trade:{_RESET}  {_BLUE}{result['trade_url']}{_RESET}")
    if result.get("note"):
        print(f"  {_DIM}{result['note']}{_RESET}")

    listings = result.get("listings", [])
    if listings:
        print(f"\n  {_DIM}Sample listings:{_RESET}")
        for i, lst in enumerate(listings[:8], 1):
            rarity    = lst.get("rarity", "")
            ilvl      = lst.get("ilvl", "")
            name      = lst.get("name", "")
            base      = lst.get("base_type", "")
            acc       = lst.get("account", "")
            amt       = lst.get("price_amount", "?")
            cur       = lst.get("price_currency", "")
            corrupted = lst.get("corrupted", False)
            fractured = lst.get("fractured", False)
            display   = name or base or "?"
            ilvl_str  = f" ilvl {ilvl}" if ilvl else ""
            flags     = (" [C]" if corrupted else "") + (" [F]" if fractured else "")
            ex_str    = _exalt_suffix(float(amt), cur) if isinstance(amt, (int, float)) else ""
            print(f"    {_DIM}#{i}{_RESET}  {_BOLD}{display}{_RESET}{_DIM}{ilvl_str}{flags}{_RESET}"
                  f"  {_CYAN}{amt} {cur}{_RESET}{ex_str}  {_DIM}{acc}{_RESET}")
            if show_items:
                mods = lst.get("mods", {})
                sections = [
                    ("enchant",   "enchant"),
                    ("implicit",  "implicit"),
                    ("explicit",  ""),
                    ("fractured", "fractured"),
                    ("crafted",   "crafted"),
                    ("rune",      "rune"),
                    ("desecrated","desecrated"),
                ]
                printed_any = False
                for field, label in sections:
                    for entry in mods.get(field, []):
                        # entry is {text, tier} dict or plain string (legacy)
                        if isinstance(entry, dict):
                            mod_text = entry.get("text", "")
                            tier_str = entry.get("tier", "")
                        else:
                            mod_text, tier_str = str(entry), ""
                        tier_tag  = f" {_DIM}[{tier_str}]{_RESET}" if tier_str else ""
                        label_tag = f" {_DIM}({label}){_RESET}" if label else ""
                        print(f"         {mod_text}{tier_tag}{label_tag}")
                        printed_any = True
                if printed_any:
                    print()


# ── Subcommand implementations ────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.data.economy import NinjaClient, EconomyError

    pdb = PriceDatabase()
    active_league = pdb.get_active_league()

    if not active_league:
        print(f"{_DIM}No active league set — detecting from poe.ninja…{_RESET}")
        try:
            active_league = NinjaClient().get_current_league()
            pdb.set_active_league(active_league)
        except EconomyError as e:
            print(f"{_RED}Could not reach poe.ninja: {e}{_RESET}", file=sys.stderr)

    print(_h("Data Status"))
    print(f"  {_BOLD}Active league:{_RESET}  {_YELLOW}{active_league or '(not set)'}{_RESET}")

    if active_league:
        ps = pdb.price_cache_status(active_league)
        es = pdb.etl_status(active_league)

        age_min = ps.get("age_minutes")
        age_str = f"  {_DIM}({age_min:.0f} min ago){_RESET}" if age_min is not None else ""
        pl = ps.get("league") or "—"
        print(f"  {_BOLD}Prices:{_RESET}         {_status_icon(ps['status'])}{age_str}")
        print(f"  {_DIM}  cached league:{_RESET}  {pl}")

        age_days = es.get("age_days")
        age_ds   = f"  {_DIM}({age_days:.1f} days ago){_RESET}" if age_days is not None else ""
        el = es.get("league") or "—"
        print(f"  {_BOLD}Game data (ETL):{_RESET} {_status_icon(es['status'])}{age_ds}")
        print(f"  {_DIM}  cached league:{_RESET}  {el}")

        if ps["status"] != "fresh":
            print(f"\n  {_YELLOW}→ Run: poe2-price refresh{_RESET}")
        if es["status"] in ("stale_league", "never_run"):
            print(f"  {_YELLOW}→ Run: PYTHONPATH=src python -m poe2_crafting_mcp.data.etl{_RESET}")
    return 0


def cmd_league(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.economy import NinjaClient, EconomyError
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    print(f"{_DIM}Querying poe.ninja…{_RESET}")
    try:
        client = NinjaClient()
        leagues = client.get_leagues()
        current = client.get_current_league()
    except EconomyError as e:
        print(f"{_RED}Error: {e}{_RESET}", file=sys.stderr)
        return 1

    pdb = PriceDatabase()
    pdb.set_active_league(current)

    print(_h("Active Leagues"))
    for league in leagues:
        name = league.get("name", "?")
        hc   = f"  {_DIM}[HC]{_RESET}" if league.get("hardcore") else ""
        idx  = f"  {_DIM}indexed{_RESET}" if league.get("indexed") else ""
        marker = f"  {_GREEN}← current{_RESET}" if name == current else ""
        bold = _BOLD if name == current else ""
        print(f"  {bold}{name}{_RESET}{hc}{idx}{marker}")

    print(f"\n  {_DIM}Active league set to:{_RESET} {_YELLOW}{current}{_RESET}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    import time
    from poe2_crafting_mcp.data.economy import NinjaClient, EconomyError
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase()
    client = NinjaClient()

    league = args.league or pdb.get_active_league() or ""
    if not league:
        print(f"{_DIM}Detecting current league…{_RESET}")
        try:
            league = client.get_current_league()
        except EconomyError as e:
            print(f"{_RED}Error: {e}{_RESET}", file=sys.stderr)
            return 1

    pdb.set_active_league(league)
    print(f"Fetching prices for {_YELLOW}{league}{_RESET}…")

    from poe2_crafting_mcp.data.currencies import CURRENCIES
    # Only items under the poe.ninja "Currency" exchange type (Orbs + Quality + Other).
    # Runes/Essences/SoulCores/Catalysts/Fragments/Distilled use their own types and
    # are fetched separately below via EXCHANGE_SLUGS.
    _CURRENCY_EXCHANGE_CATS = {"Orb", "Quality", "Other"}
    trade_ids = [c[4] for c in CURRENCIES if c[4] and c[1] in _CURRENCY_EXCHANGE_CATS]

    print(f"  Fetching {len(trade_ids)} currencies…")
    fetched = 0
    errors  = 0

    def _progress(current: int, total: int, name: str) -> None:
        nonlocal fetched
        # Print a dot every 10 fetches
        if current % 10 == 0 or current == total:
            print(f"  {_DIM}  {current}/{total}{_RESET}", end="\r", flush=True)

    t0 = time.monotonic()
    try:
        rows = client.fetch_currency_rates(league, trade_ids, progress_cb=_progress)
    except EconomyError as e:
        print(f"\n{_RED}Error: {e}{_RESET}", file=sys.stderr)
        return 1

    print()  # newline after progress
    pdb.upsert_prices(rows, league)
    duration = time.monotonic() - t0
    print(f"\n{_GREEN}✓ {len(rows)} currency prices cached in {duration:.1f}s{_RESET}")

    # ── General exchange categories (per-item exchange endpoint) ─────────────
    from poe2_crafting_mcp.data.general_items import EXCHANGE_SLUGS
    total_general = 0
    print()
    for item_type, slugs in EXCHANGE_SLUGS.items():
        if not slugs:
            continue
        print(f"  Fetching {item_type}…", end=" ", flush=True)
        t1 = time.monotonic()
        gen_rows = client.fetch_exchange_items(league, item_type, slugs)
        if gen_rows:
            pdb.upsert_prices(gen_rows, league)
            total_general += len(gen_rows)
            print(f"{_GREEN}{len(gen_rows)} items{_RESET}  {_DIM}({time.monotonic()-t1:.1f}s){_RESET}")
        else:
            print(f"{_DIM}no data{_RESET}")

    # Fill chaos_value for exchange items (divine_value was stored, chaos was None)
    filled = pdb.fill_chaos_from_divine(league)
    if filled:
        print(f"  {_DIM}(filled chaos values for {filled} exchange items){_RESET}")

    print(f"\n{_GREEN}✓ {total_general} general exchange prices cached{_RESET}")

    # ── Equipment + Atlas (stash bulk endpoint) ───────────────────────────────
    from poe2_crafting_mcp.data.economy import STASH_ITEM_TYPES
    total_items = 0
    print()
    for item_type, label in STASH_ITEM_TYPES:
        print(f"  Fetching {label}…", end=" ", flush=True)
        t1 = time.monotonic()
        item_rows = client.fetch_item_overview(league, item_type)
        if item_rows:
            pdb.upsert_prices(item_rows, league)
            total_items += len(item_rows)
            print(f"{_GREEN}{len(item_rows)} items{_RESET}  {_DIM}({time.monotonic()-t1:.1f}s){_RESET}")
        else:
            print(f"{_DIM}no data{_RESET}")

    print(f"\n{_GREEN}✓ {total_items} equipment/atlas prices cached{_RESET}")
    return 0


def cmd_general(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase()
    league = args.league or pdb.get_active_league() or ""
    if not league:
        print(f"{_RED}No active league. Run: poe2-price league{_RESET}", file=sys.stderr)
        return 1

    name = " ".join(args.name)

    _GENERAL_CATS = (
        "currency", "fragment", "rune", "essence", "soul_core",
        "catalyst", "liquid_emotion", "uncut_gem", "lineage_gem",
        "abyss", "idol", "omen", "expedition", "verisium",
    )

    # Try exact match across all general categories
    row = None
    for cat in _GENERAL_CATS:
        row = pdb.get_price(name, league, cat)
        if row:
            break

    if not row:
        results = pdb.search_prices(name, league, limit=8)
        currency_results = [r for r in results if r["category"] in _GENERAL_CATS]
        if not currency_results:
            print(f"{_RED}'{name}' not found in price cache.{_RESET}")
            print(f"{_DIM}Run: poe2-price refresh{_RESET}")
            return 1
        if len(currency_results) == 1:
            row = currency_results[0]
        else:
            exalt_rate = _get_exalt_rate(pdb, league)
            print(_h(f"General matches for '{name}'"))
            for r in currency_results:
                _fmt_price_row(r, exalt_rate=exalt_rate)
                print()
            return 0

    exalt_rate = _get_exalt_rate(pdb, league)
    print(_h("General Price"))
    _fmt_price_row(row, exalt_rate=exalt_rate)
    # Show description if available (from CURRENCIES effect or EXCHANGE_DESCRIPTIONS)
    trade_id = row.get("trade_id") or ""
    if trade_id:
        try:
            from poe2_crafting_mcp.data.general_items import _slug_to_description
            desc = _slug_to_description(trade_id)
            if desc:
                print(f"  {_DIM}{desc}{_RESET}")
        except Exception:
            pass
    fetched = row.get("fetched_at", "")[:19].replace("T", " ")
    if fetched:
        print(f"  {_DIM}cached: {fetched} UTC{_RESET}")
    return 0


_EQUIPMENT_CATS = (
    "unique_weapon", "unique_armour", "unique_accessory",
    "unique_flask", "unique_charm", "unique_jewel", "unique_relic",
)
_ATLAS_CATS = ("unique_tablet", "precursor_tablet")
_ALL_UNIQUE_CATS = _EQUIPMENT_CATS + _ATLAS_CATS


def _lookup_cached_unique(pdb: object, name: str, league: str,
                          categories: tuple) -> dict | None:
    """Search price cache across a set of categories for a named item."""
    for cat in categories:
        row = pdb.get_price(name, league, cat)
        if row:
            return row
    # Fuzzy fallback: search by name prefix
    results = pdb.search_prices(name, league, limit=5)
    for r in results:
        if r["category"] in categories:
            return r
    return None


def cmd_equipment(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError

    pdb = PriceDatabase()
    league = args.league or pdb.get_active_league() or ""
    if not league:
        print(f"{_RED}No active league. Run: poe2-price league{_RESET}", file=sys.stderr)
        return 1

    name    = " ".join(args.name)
    cat     = args.cat or ""
    is_base = cat == "base" or args.base

    exalt_rate  = _get_exalt_rate(pdb, league)
    divine_row  = pdb.get_price("Divine Orb", league, "currency")
    divine_rate = float(divine_row["chaos_value"]) if divine_row and divine_row.get("chaos_value") else None

    # Check cache first (covers all unique categories including atlas).
    # Only use cached data if it has a real price and non-zero listings.
    if not is_base:
        cached = _lookup_cached_unique(pdb, name, league, _ALL_UNIQUE_CATS)
        has_price = (
            cached is not None
            and (cached.get("chaos_value") or cached.get("divine_value"))
            and (cached.get("listing_count") or 0) > 0
        )
        if has_price:
            print(_h(f"Cached Price — {name}"))
            _fmt_price_row(cached, exalt_rate=exalt_rate)
            fetched = cached.get("fetched_at", "")[:19].replace("T", " ")
            if fetched:
                print(f"  {_DIM}cached: {fetched} UTC{_RESET}")
            if cached["category"] in _ATLAS_CATS:
                print(f"  {_DIM}Tip: use 'poe2-price atlas' for atlas items{_RESET}")
            return 0

    # Fall back to live trade API
    client = TradeClient()
    rarity = getattr(args, "rarity", "nonunique") or "nonunique"
    print(f"{_DIM}Querying trade API for '{name}'…{_RESET}")

    try:
        if is_base:
            result = client.estimate_price(
                league, base_name=name, ilvl_min=args.ilvl_min, rarity=rarity
            )
        else:
            result = client.estimate_price(league, name=name)
    except TradeError as e:
        print(f"{_RED}Trade API error: {e}{_RESET}", file=sys.stderr)
        return 1

    _fmt_trade_result(result, exalt_rate=exalt_rate, divine_rate=divine_rate)
    return 0


def cmd_atlas(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError

    pdb = PriceDatabase()
    league = args.league or pdb.get_active_league() or ""
    if not league:
        print(f"{_RED}No active league. Run: poe2-price league{_RESET}", file=sys.stderr)
        return 1

    name    = " ".join(args.name)
    rarity  = getattr(args, "rarity", "any") or "any"
    ilvl    = getattr(args, "ilvl_min", 0) or 0

    exalt_rate  = _get_exalt_rate(pdb, league)
    divine_row  = pdb.get_price("Divine Orb", league, "currency")
    divine_rate = float(divine_row["chaos_value"]) if divine_row and divine_row.get("chaos_value") else None

    # Check cache first — only if it has a real price and non-zero listings
    cached = _lookup_cached_unique(pdb, name, league, _ATLAS_CATS)
    has_price = (
        cached is not None
        and (cached.get("chaos_value") or cached.get("divine_value"))
        and (cached.get("listing_count") or 0) > 0
    )
    if has_price:
        print(_h(f"Cached Price — {name}"))
        _fmt_price_row(cached, exalt_rate=exalt_rate)
        fetched = cached.get("fetched_at", "")[:19].replace("T", " ")
        if fetched:
            print(f"  {_DIM}cached: {fetched} UTC{_RESET}")
        return 0

    client = TradeClient()
    print(f"{_DIM}Querying trade API for '{name}'…{_RESET}")

    try:
        result = client.estimate_price(league, name=name)
    except TradeError as e:
        result = {"found": False, "error": str(e)}

    # If unique search failed with an "Unknown item" error, fall back to an
    # Irradiated Tablet base search — for magic/rare augmented/precursor tablets.
    # "Irradiated Tablet" is the trade API base type for all PoE2 atlas tablets.
    if not result.get("found"):
        err = result.get("error", "")
        if "Unknown item" in err or not result.get("found"):
            print(f"{_DIM}  (not a unique tablet — searching Irradiated Tablet base…){_RESET}")
            try:
                result = client.estimate_price(
                    league,
                    base_name="Irradiated Tablet",
                    rarity=rarity,
                    ilvl_min=ilvl,
                )
            except TradeError as e:
                result = {"found": False, "error": str(e)}

    _fmt_trade_result(result, exalt_rate=exalt_rate, divine_rate=divine_rate)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    valid = {"currency", "fragment", "unique", "base", "gem"}
    category = args.category.lower()
    if category not in valid:
        print(f"{_RED}Category must be one of: {', '.join(sorted(valid))}{_RESET}",
              file=sys.stderr)
        return 1

    pdb = PriceDatabase()
    league = args.league or pdb.get_active_league() or ""
    if not league:
        print(f"{_RED}No active league. Run: poe2-price league{_RESET}", file=sys.stderr)
        return 1

    rows = pdb.get_bulk_prices(category, league)
    if not rows:
        print(f"{_RED}No '{category}' prices cached for {league}.{_RESET}")
        print(f"{_DIM}Run: poe2-price refresh{_RESET}")
        return 1

    limit = args.limit
    total = len(rows)
    rows = rows[:limit]

    exalt_rate = _get_exalt_rate(pdb, league)

    print(_h(f"{category.title()} prices — {league}"))
    print(f"  {_DIM}Showing {len(rows)} of {total} items, sorted by listing count{_RESET}\n")

    for row in rows:
        chaos  = row.get("chaos_value")
        divine = row.get("divine_value")
        count  = row.get("listing_count", 0)
        name   = row.get("name", "?")
        exalt  = (chaos / exalt_rate) if (chaos and exalt_rate) else None
        price  = _fmt_chaos(chaos) + _fmt_divine(divine) + _fmt_exalt(exalt)
        print(f"  {_BOLD}{name:<40}{_RESET} {price}  {_DIM}{count:,}{_RESET}")

    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """
    Search game DB for items matching a stat keyword, then attach prices.

    Types searched:
    - unique: searches uniques table by mod text
    - base:   searches item_bases table by name/tag keyword
    - gem:    searches gems table by name
    - (blank): searches all three
    """
    from poe2_crafting_mcp.data.database import PoBDatabase
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    try:
        game_db = PoBDatabase()
    except FileNotFoundError as e:
        print(f"{_RED}Error: {e}{_RESET}", file=sys.stderr)
        return 1

    pdb = PriceDatabase()
    league = args.league or pdb.get_active_league() or ""
    no_prices = not league

    keyword = " ".join(args.keyword)
    slot    = args.slot
    limit   = args.limit
    types   = [t.strip().lower() for t in args.type.split(",")] if args.type else ["unique", "base", "gem"]

    found_any = False

    # ── Uniques ───────────────────────────────────────────────────────────────
    if "unique" in types:
        results = game_db.search_uniques(slot=slot, keyword=keyword, limit=limit)
        if results:
            found_any = True
            print(_h(f"Unique items matching '{keyword}'"))
            for u in results:
                name      = u.get("name", "?")
                base_type = u.get("base_type", "")
                source    = u.get("source", "")

                # Extract stat lines from raw_text that match the keyword
                raw   = u.get("raw_text") or ""
                lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                # Skip header (name + base), variant/source metadata
                import re as _re
                stat_lines = []
                skip_prefixes = ("Variant:", "League:", "Source:", "Implicits:",
                                 "Explicit", "{variant", "Requires", "Quality")
                for ln in lines[2:]:
                    if any(ln.startswith(p) for p in skip_prefixes):
                        continue
                    if ln.startswith("{variant"):
                        ln = ln.split("}", 1)[-1]
                    # Strip PoB internal tags like {tags:life} or {range:0.5}
                    ln = _re.sub(r"\{[^}]+\}", "", ln).strip()
                    if ln:
                        stat_lines.append(ln)
                # Highlight lines that match the keyword
                kw_lower = keyword.lower()
                relevant = [ln for ln in stat_lines if kw_lower in ln.lower()]
                other    = [ln for ln in stat_lines if kw_lower not in ln.lower()]

                # Price lookup
                price_str = ""
                if not no_prices and args.live:
                    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError
                    try:
                        r = TradeClient().estimate_price(league, name=name)
                        if r.get("found") and r.get("min_price"):
                            mp = r["min_price"]
                            price_str = f"  {_CYAN}{mp['amount']} {mp['currency']}{_RESET}"
                            price_str += f" {_DIM}({r['total_listings']:,} listings){_RESET}"
                        else:
                            price_str = f"  {_DIM}(no listings){_RESET}"
                    except TradeError:
                        price_str = f"  {_DIM}(trade error){_RESET}"

                print(f"  {_PURPLE}{_BOLD}{name}{_RESET}  {_DIM}{base_type}{_RESET}{price_str}")
                if source:
                    print(f"    {_DIM}Source: {source}{_RESET}")
                for ln in relevant[:4]:
                    print(f"    {_YELLOW}{ln}{_RESET}")
                for ln in other[:3]:
                    print(f"    {_DIM}{ln}{_RESET}")
                if len(stat_lines) > len(relevant[:4]) + len(other[:3]):
                    remaining = len(stat_lines) - len(relevant[:4]) - len(other[:3])
                    print(f"    {_DIM}… +{remaining} more stats{_RESET}")
                print()

    # ── Bases ─────────────────────────────────────────────────────────────────
    if "base" in types:
        results = game_db.search_bases(slot=slot, keyword=keyword, limit=limit)
        if results:
            found_any = True
            print(_h(f"Item bases matching '{keyword}'"))
            for b in results:
                name   = b.get("name", "?")
                bslot  = b.get("slot", "")
                sub    = b.get("sub_type", "")
                ilvl   = b.get("req_level", 0)

                defence = []
                if b.get("armour"):        defence.append(f"AR {b['armour']}")
                if b.get("evasion"):       defence.append(f"EV {b['evasion']}")
                if b.get("energy_shield"): defence.append(f"ES {b['energy_shield']}")
                if b.get("ward"):          defence.append(f"WA {b['ward']}")
                def_str = "  ".join(defence) if defence else "—"

                price_str = ""
                if not no_prices and args.live:
                    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError
                    try:
                        r = TradeClient().estimate_price(
                            league, base_name=name, ilvl_min=args.ilvl_min,
                            rarity=getattr(args, "rarity", "nonunique"),
                        )
                        if r.get("found") and r.get("min_price"):
                            mp = r["min_price"]
                            price_str = f"  {_CYAN}{mp['amount']} {mp['currency']}{_RESET}"
                            price_str += f" {_DIM}({r['total_listings']:,} listings, ilvl≥{args.ilvl_min}){_RESET}"
                        else:
                            price_str = f"  {_DIM}(no listings ilvl≥{args.ilvl_min}){_RESET}"
                    except TradeError:
                        price_str = f"  {_DIM}(trade error){_RESET}"

                print(f"  {_GREEN}{_BOLD}{name}{_RESET}  {_DIM}{bslot} · {sub}{_RESET}{price_str}")
                print(f"    {_DIM}iLvl req:{_RESET} {ilvl}  {_DIM}Defence:{_RESET} {def_str}")
                print()

    # ── Gems ──────────────────────────────────────────────────────────────────
    if "gem" in types:
        results = game_db.search_gems(keyword=keyword, limit=limit)
        if results:
            found_any = True
            print(_h(f"Gems matching '{keyword}'"))
            for g in results:
                name       = g.get("name", "?")
                gem_type   = g.get("gem_type", "")
                is_support = g.get("is_support", False)
                tags       = g.get("tag_string", "")
                label      = f"{_BLUE}[Support]{_RESET}" if is_support else f"{_GREEN}[Active]{_RESET}"

                price_str = ""
                if not no_prices and args.live:
                    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError
                    try:
                        r = TradeClient().estimate_price(league, name=name)
                        if r.get("found") and r.get("min_price"):
                            mp = r["min_price"]
                            price_str = f"  {_CYAN}{mp['amount']} {mp['currency']}{_RESET}"
                            price_str += f" {_DIM}({r['total_listings']:,} listings){_RESET}"
                        else:
                            price_str = f"  {_DIM}(no listings){_RESET}"
                    except TradeError:
                        price_str = f"  {_DIM}(trade error){_RESET}"

                print(f"  {_BOLD}{name}{_RESET}  {label}  {_DIM}{gem_type}{_RESET}{price_str}")
                if tags:
                    print(f"    {_DIM}Tags: {tags}{_RESET}")
                print()

    if not found_any:
        print(f"No items found for '{keyword}'.")
        if slot:
            print(f"{_DIM}Tip: try without --slot, or check slot spelling (e.g. Ring, Gloves, 'Body Armour'){_RESET}")

    if no_prices:
        print(f"\n{_DIM}No prices shown — run: poe2-price refresh{_RESET}")

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """
    Fetch and cache trade2 stat IDs from the GGG trade API.

    With no arguments: show cache status and sample entries.
    With --refresh: re-fetch all stat IDs from the API (~6000 entries, ~2s).
    With --search KEYWORD: search the cached stats by text.
    """
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError

    pdb = PriceDatabase()
    count = pdb.trade_stats_count()
    fetched_at = pdb.trade_stats_fetched_at()

    if args.search:
        if count == 0:
            print(f"{_RED}No stat IDs cached. Run: poe2-price stats --refresh{_RESET}",
                  file=sys.stderr)
            return 1
        keyword = " ".join(args.search)
        results = pdb.search_trade_stats(keyword, stat_type=args.stat_type, limit=args.limit)
        print(_h(f"Stat IDs matching '{keyword}'"))
        for r in results:
            sid  = r["stat_id"]
            text = r["stat_text"]
            stype = r["stat_type"]
            print(f"  {_CYAN}{sid}{_RESET}")
            print(f"    {_BOLD}{text}{_RESET}  {_DIM}[{stype}]{_RESET}")
        if not results:
            print(f"  {_DIM}No matches. Try a different keyword.{_RESET}")
        return 0

    if args.refresh:
        print(f"{_DIM}Fetching trade stat IDs from GGG trade API…{_RESET}")
        try:
            stats = TradeClient().fetch_stats()
        except TradeError as e:
            print(f"{_RED}Error: {e}{_RESET}", file=sys.stderr)
            return 1
        n = pdb.upsert_trade_stats(stats)
        print(f"{_GREEN}✓ {n:,} stat IDs cached{_RESET}")
        # Show a quick breakdown by type
        by_type: dict[str, int] = {}
        for s in stats:
            by_type[s["stat_type"]] = by_type.get(s["stat_type"], 0) + 1
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {_DIM}{t}: {c}{_RESET}")
        return 0

    # Default: status
    print(_h("Trade Stat ID Cache"))
    if count == 0:
        print(f"  {_RED}No stat IDs cached.{_RESET}")
        print(f"  {_YELLOW}→ Run: poe2-price stats --refresh{_RESET}")
    else:
        age_str = ""
        if fetched_at:
            from poe2_crafting_mcp.data.price_db import PriceDatabase as _P
            age_s = _P._age_seconds(fetched_at)
            age_h = age_s / 3600
            age_str = f"  {_DIM}({age_h:.1f}h ago){_RESET}"
        print(f"  {_GREEN}✓ {count:,} stat IDs cached{_RESET}{age_str}")
        print(f"  {_DIM}Use: poe2-price stats --search <keyword>{_RESET}")
        print(f"  {_DIM}Use: poe2-price stats --refresh  (to re-fetch){_RESET}")
    return 0


def cmd_trade(args: argparse.Namespace) -> int:
    """
    Search the trade site for items with a specific stat (e.g. T1 energy shield).

    Resolves the stat name to a trade stat ID, then searches with filters:
      slot + rarity + ilvl + stat min/max value.

    Requires trade stat IDs to be cached first:
      poe2-price stats --refresh
    """
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    from poe2_crafting_mcp.data.trade_client import TradeClient, TradeError, SLOT_TO_CATEGORY

    pdb = PriceDatabase()

    # ── Check stat cache ──────────────────────────────────────────────────────
    if pdb.trade_stats_count() == 0:
        print(f"{_RED}Stat ID cache is empty. Run first:{_RESET}")
        print(f"  poe2-price stats --refresh")
        return 1

    keyword  = " ".join(args.stat)
    league   = args.league or pdb.get_active_league() or ""
    slot_raw = args.slot.lower() if args.slot else ""

    if not league:
        print(f"{_RED}No active league. Run: poe2-price league{_RESET}", file=sys.stderr)
        return 1

    # ── Resolve stat ID ───────────────────────────────────────────────────────
    # Armour slots have local mods (flat ES, flat AR, flat EV) — prefer (Local) variants
    _armour_slots = {"gloves", "boots", "helmet", "helm", "body armour", "body", "chest",
                     "shield", "focus", "buckler"}
    prefer_local = slot_raw in _armour_slots

    stat_type_filter = args.stat_type or "explicit"
    matches = pdb.search_trade_stats(
        keyword, stat_type=stat_type_filter, limit=5, prefer_local=prefer_local
    )
    if not matches:
        # Retry without type filter
        matches = pdb.search_trade_stats(keyword, limit=5, prefer_local=prefer_local)
    if not matches:
        print(f"{_RED}No stat IDs found for '{keyword}'.{_RESET}")
        print(f"{_DIM}Try: poe2-price stats --search '{keyword}'{_RESET}")
        return 1

    # Show which stat we matched (first result), let user override with --stat-id
    chosen = matches[0]
    if args.stat_id:
        # User specified exact ID — look it up
        override = pdb.get_trade_stat(args.stat_id)
        if not override:
            print(f"{_RED}Stat ID '{args.stat_id}' not found in cache.{_RESET}", file=sys.stderr)
            return 1
        chosen = override

    print(_h(f"Stat search — {league}"))
    print(f"  {_BOLD}Stat:{_RESET}    {chosen['stat_text']}")
    print(f"  {_BOLD}ID:{_RESET}      {_DIM}{chosen['stat_id']}{_RESET}")

    if len(matches) > 1 and not args.stat_id:
        print(f"  {_DIM}Other matches (use --stat-id to pick):{_RESET}")
        for m in matches[1:4]:
            print(f"    {_DIM}{m['stat_id']}  {m['stat_text']}{_RESET}")
    print()

    # ── Resolve slot → category ───────────────────────────────────────────────
    category: str | None = None
    if slot_raw:
        category = SLOT_TO_CATEGORY.get(slot_raw)
        if not category:
            # Try prefix match
            for k, v in SLOT_TO_CATEGORY.items():
                if k.startswith(slot_raw) or slot_raw.startswith(k):
                    category = v
                    break
        if not category:
            print(f"{_YELLOW}Warning: unknown slot '{args.slot}'. "
                  f"Searching all item types.{_RESET}")
            print(f"  {_DIM}Valid slots: {', '.join(SLOT_TO_CATEGORY)}{_RESET}")

    # ── Resolve tier → min value ──────────────────────────────────────────────
    min_val: float | None = args.min_val
    if args.tier is not None and min_val is None:
        min_val = _lookup_tier_min(keyword, args.tier, slot_raw)
        if min_val is not None:
            print(f"  {_DIM}T{args.tier} min value from game DB:{_RESET} {_CYAN}{min_val}{_RESET}\n")
        else:
            print(f"  {_YELLOW}Could not find T{args.tier} value in game DB."
                  f" Searching without value floor.{_RESET}\n")

    # ── Build stat filter + search ────────────────────────────────────────────
    import json as _json

    # Parse multi-stat / stat group args
    extra_stat_filters: list[dict] = []
    for raw in getattr(args, "extra_stat_filters", []):
        try:
            extra_stat_filters.append(_json.loads(raw))
        except _json.JSONDecodeError as exc:
            print(f"{_RED}Invalid --stat-filter JSON: {raw!r} — {exc}{_RESET}", file=sys.stderr)
            return 1

    stat_groups: list[dict] | None = None
    raw_groups = getattr(args, "stat_groups_json", [])
    if raw_groups:
        stat_groups = []
        for raw in raw_groups:
            try:
                stat_groups.append(_json.loads(raw))
            except _json.JSONDecodeError as exc:
                print(f"{_RED}Invalid --stat-group JSON: {raw!r} — {exc}{_RESET}", file=sys.stderr)
                return 1

    stats_type: str = getattr(args, "stats_type", "and") or "and"
    stats_min_count: int | None = getattr(args, "stats_min_count", None)

    # Build primary stat filter (skip if stat_groups overrides everything)
    stat_filter: dict = {"id": chosen["stat_id"]}
    if min_val is not None:
        stat_filter["min"] = min_val
    if args.max_val is not None:
        stat_filter["max"] = args.max_val

    # Combine primary + extra into all_stat_filters (ignored when stat_groups given)
    all_stat_filters: list[dict] | None
    if stat_groups:
        all_stat_filters = None  # stat_groups overrides
    else:
        all_stat_filters = [stat_filter] + extra_stat_filters

    rarity   = args.rarity
    ilvl_min = args.ilvl_min

    # Collect optional item property filters
    filter_kwargs: dict = {
        "category": category,
        "rarity":   rarity if rarity != "any" else None,
        "ilvl_min": ilvl_min if ilvl_min else None,
        "ilvl_max":           getattr(args, "ilvl_max", None),
        "quality_min":        getattr(args, "quality_min", None),
        "rune_sockets_min":   getattr(args, "rune_sockets_min", None),
        "corrupted":          getattr(args, "corrupted", None),
        "fractured_item":     getattr(args, "fractured", None),
        "identified":         getattr(args, "identified", None),
        "gem_level_min":      getattr(args, "gem_level_min", None),
        "gem_level_max":      getattr(args, "gem_level_max", None),
        "map_tier_min":       getattr(args, "map_tier_min", None),
        "map_tier_max":       getattr(args, "map_tier_max", None),
        "indexed":            getattr(args, "indexed", None),
        "price_max":          getattr(args, "price_max", None),
        "price_currency":     getattr(args, "price_currency", None),
        "account":            getattr(args, "account", None),
    }
    # Strip None values so build_api_filters skips them
    filter_kwargs = {k: v for k, v in filter_kwargs.items() if v is not None}

    desc_parts = [f"rarity={rarity}", f"ilvl≥{ilvl_min}"]
    if category:
        desc_parts.append(f"category={category}")
    if min_val is not None:
        desc_parts.append(f"min={min_val}")
    if extra_stat_filters:
        desc_parts.append(f"+{len(extra_stat_filters)} extra stats")
    if stat_groups:
        desc_parts.append(f"{len(stat_groups)} stat groups")
    if stats_type != "and":
        desc_parts.append(f"stats_type={stats_type}")
    for fk in ("corrupted", "fractured_item", "indexed", "gem_level_min", "map_tier_min"):
        if fk in filter_kwargs:
            desc_parts.append(f"{fk}={filter_kwargs[fk]}")
    print(f"  {_DIM}Searching: {', '.join(desc_parts)}…{_RESET}\n")

    try:
        result = TradeClient().estimate_trade_price(
            league,
            stat_filters=all_stat_filters,
            stats_type=stats_type,
            stats_min_count=stats_min_count,
            stat_groups=stat_groups,
            sample=args.sample,
            **filter_kwargs,
        )
    except TradeError as e:
        print(f"{_RED}Trade API error: {e}{_RESET}", file=sys.stderr)
        return 1

    exalt_rate  = _get_exalt_rate(pdb, league)
    divine_row  = pdb.get_price("Divine Orb", league, "currency")
    divine_rate = float(divine_row["chaos_value"]) if divine_row and divine_row.get("chaos_value") else None
    _fmt_trade_result(result, exalt_rate=exalt_rate, divine_rate=divine_rate,
                      show_items=getattr(args, "items", False))
    return 0


def _lookup_tier_min(keyword: str, tier: int, slot: str = "") -> float | None:
    """
    Look up the minimum stat value for a given mod tier from the game DB.

    Queries item_mods FTS for the keyword, groups by mod group, and returns
    the effective min value at the requested tier.

    Handles 2-range mods like "Adds X to Y Lightning damage": the DB stores
    the min-damage range (X) as stat_min, but the trade site filters by the
    max-damage value (Y). We extract Y from stat_text for these mods.
    """
    import re as _re

    try:
        from poe2_crafting_mcp.data.database import PoBDatabase
        db = PoBDatabase()
    except (FileNotFoundError, Exception):
        return None

    try:
        # FTS search item_mods for this keyword
        safe_kw = keyword.replace('"', '""')
        rows = db._conn.execute(
            "SELECT m.group_name, m.stat_text, m.stat_min, m.stat_max,"
            "       m.req_level, m.weight_keys"
            " FROM item_mods m"
            " JOIN item_mods_fts f ON m.rowid = f.rowid"
            " WHERE f.stat_text MATCH ?"
            "   AND m.stat_min IS NOT NULL"
            "   AND m.category = 'Item'"
            " ORDER BY m.req_level DESC, m.stat_min DESC",
            (safe_kw,),
        ).fetchall()
    except Exception:
        return None

    if not rows:
        return None

    # If slot given, filter by weight_keys containing the slot tag
    if slot:
        slot_tag = _slot_to_pob_tag(slot)
        if slot_tag:
            filtered = [r for r in rows if slot_tag in (r["weight_keys"] or "")]
            if filtered:
                rows = filtered

    # Deduplicate: find best-matching group by highest req_level (T1 = highest ilvl)
    seen_group: dict[str, int] = {}
    for r in rows:
        gn = r["group_name"] or ""
        if gn not in seen_group:
            seen_group[gn] = r["req_level"] or 0

    if not seen_group:
        return None

    best_group = max(seen_group, key=lambda g: seen_group[g])

    # Collect all tiers for this group, sorted by req_level DESC (T1 first)
    tier_rows = sorted(
        [r for r in rows if (r["group_name"] or "") == best_group],
        key=lambda r: (r["req_level"] or 0, r["stat_min"] or 0),
        reverse=True,
    )

    idx = tier - 1
    if idx < 0 or idx >= len(tier_rows):
        idx = min(len(tier_rows) - 1, max(0, idx))

    row = tier_rows[idx]

    # For 2-range mods "Adds X to (A-B) Damage", the trade site filters by the
    # max-damage value (A). Extract A from stat_text if present.
    text = row["stat_text"] or ""
    m = _re.search(r'\bto \((\d+)[-–]\d+\)', text)
    if m:
        return float(m.group(1))

    return row["stat_min"]


def _slot_to_pob_tag(slot: str) -> str:
    """Map a slot name to a PoB item tag used in weight_keys."""
    mapping = {
        "gloves": "gloves", "boots": "boots", "helmet": "helmet", "helm": "helmet",
        "body armour": "body_armour", "chest": "body_armour", "body": "body_armour",
        "ring": "ring", "amulet": "amulet", "belt": "belt",
        "shield": "shield", "quiver": "quiver",
    }
    return mapping.get(slot.lower(), "")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="poe2-price",
        description="PoE2 price lookup and item search with poe.ninja data.",
    )
    parser.add_argument("--league", "-L", default="",
                        help="Override league (default: use stored active league)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colour output")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # status
    sub.add_parser("status", help="Show data freshness and active league")

    # league
    sub.add_parser("league", help="Detect current league from poe.ninja")

    # refresh
    p_refresh = sub.add_parser("refresh", help="Fetch fresh prices from poe.ninja")
    p_refresh.add_argument("--league", "-L", default="",
                           help="League to fetch (default: auto-detect)")

    # general
    p_general = sub.add_parser("general", help="Look up a currency / fragment / rune / omen price")
    p_general.add_argument("name", nargs="+", help="Item name, e.g. 'Divine Orb', 'Aldur\\'s Legacy'")

    # equipment
    p_equipment = sub.add_parser("equipment", help="Look up live trade price for a unique or base item")
    p_equipment.add_argument("name", nargs="+", help="Item name, e.g. \"Winter's Bite\" or base name")
    p_equipment.add_argument("--cat", "-c", default="",
                             help="Category hint: unique, base, gem")
    p_equipment.add_argument("--base", action="store_true",
                             help="Treat name as a base item type (not a unique)")
    p_equipment.add_argument("--ilvl-min", type=int, default=80,
                             help="Minimum item level for base searches (default 80)")
    p_equipment.add_argument("--rarity", "-r", default="nonunique",
                             choices=["nonunique", "normal", "magic", "rare", "any"],
                             help="Rarity filter for base searches (default: nonunique)")

    # atlas
    p_atlas = sub.add_parser("atlas", help="Look up live trade price for an atlas tablet")
    p_atlas.add_argument("name", nargs="+", help="Tablet name or description, e.g. 'Visions of Paradise', 'Precursor Tablet'")
    p_atlas.add_argument("--rarity", "-r", default="any",
                         choices=["any", "magic", "rare", "unique"],
                         help="Rarity for non-unique tablet searches (default: any)")
    p_atlas.add_argument("--ilvl-min", type=int, default=0,
                         help="Minimum item level for base tablet searches (default 0)")

    # list
    p_list = sub.add_parser("list", help="List all prices for a category")
    p_list.add_argument("category",
                        choices=["currency", "fragment", "unique", "base", "gem"],
                        help="Price category")
    p_list.add_argument("--limit", "-l", type=int, default=30,
                        help="Max items to show (default 30)")

    # stats
    p_stats = sub.add_parser("stats", help="Manage the trade stat ID cache")
    p_stats.add_argument("--refresh", action="store_true",
                         help="Re-fetch all stat IDs from the GGG trade API")
    p_stats.add_argument("--search", nargs="+", metavar="KEYWORD",
                         help="Search cached stat IDs by text")
    p_stats.add_argument("--stat-type", default="",
                         help="Filter by type: explicit, implicit, pseudo (default: all)")
    p_stats.add_argument("--limit", "-l", type=int, default=10,
                         help="Max results for --search (default 10)")

    # trade
    p_trade = sub.add_parser(
        "trade",
        help="Search trade site for items with a specific stat (e.g. T1 energy shield)",
    )
    p_trade.add_argument("stat", nargs="+",
                         help="Stat keyword to search, e.g. 'energy shield', 'maximum life'")
    p_trade.add_argument("--slot", "-s", default="",
                         help="Item slot: gloves, boots, helmet, ring, amulet, belt, etc.")
    p_trade.add_argument("--rarity", "-r", default="magic",
                         choices=["magic", "rare", "normal", "nonunique", "any"],
                         help="Rarity filter (default: magic)")
    p_trade.add_argument("--ilvl-min", type=int, default=80,
                         help="Minimum item level (default 80)")
    p_trade.add_argument("--tier", "-t", type=int, default=None,
                         help="Mod tier — auto-looks up min value from game DB (T1=best)")
    p_trade.add_argument("--min", dest="min_val", type=float, default=None,
                         help="Explicit minimum stat value (overrides --tier)")
    p_trade.add_argument("--max", dest="max_val", type=float, default=None,
                         help="Maximum stat value")
    p_trade.add_argument("--stat-id", default="",
                         help="Override: use this exact trade stat ID instead of searching")
    p_trade.add_argument("--stat-type", default="",
                         help="Stat type hint: explicit, implicit, fractured, pseudo")
    p_trade.add_argument("--sample", type=int, default=5,
                         help="Listings to fetch for price estimate (default 5)")
    p_trade.add_argument("--ilvl-max", type=int, default=None,
                         help="Maximum item level")
    p_trade.add_argument("--quality-min", type=int, default=None,
                         help="Minimum quality %%")
    p_trade.add_argument("--rune-sockets", dest="rune_sockets_min", type=int, default=None,
                         help="Minimum number of rune sockets")
    p_trade.add_argument("--corrupted", dest="corrupted",
                         action="store_true", default=None,
                         help="Only corrupted items")
    p_trade.add_argument("--not-corrupted", dest="corrupted",
                         action="store_false",
                         help="Only non-corrupted items")
    p_trade.add_argument("--fractured", dest="fractured",
                         action="store_true", default=None,
                         help="Only fractured items (has a fractured mod)")
    p_trade.add_argument("--identified", dest="identified",
                         action="store_true", default=None,
                         help="Only identified items")
    p_trade.add_argument("--not-identified", dest="identified",
                         action="store_false",
                         help="Only unidentified items")
    p_trade.add_argument("--gem-level-min", type=int, default=None,
                         help="Minimum gem level (for gem searches)")
    p_trade.add_argument("--gem-level-max", type=int, default=None,
                         help="Maximum gem level")
    p_trade.add_argument("--map-tier-min", type=int, default=None,
                         help="Minimum waystone/map tier")
    p_trade.add_argument("--map-tier-max", type=int, default=None,
                         help="Maximum waystone/map tier")
    p_trade.add_argument("--indexed", default=None,
                         choices=["1hour", "3hours", "12hours", "1day", "3days",
                                  "1week", "2weeks", "1month"],
                         help="Only show listings posted within this time window")
    p_trade.add_argument("--price-max", type=float, default=None,
                         help="Maximum price (in --price-currency units)")
    p_trade.add_argument("--price-currency", default=None,
                         choices=["divine", "exalted", "chaos", "regal", "vaal",
                                  "transmute", "augment"],
                         help="Currency for --price-max (default: divine)")
    p_trade.add_argument("--account", default=None,
                         help="Filter by seller account name")
    p_trade.add_argument("--items", action="store_true", default=False,
                         help="Show full mod list for each listing (not just price)")
    # Multi-stat / stat groups
    p_trade.add_argument("--stat-filter", dest="extra_stat_filters", metavar="JSON",
                         action="append", default=[],
                         help='Additional stat filter as JSON, e.g. \'{"id":"explicit.stat_XXX","min":30}\'. '
                              'Repeatable — each --stat-filter adds one more stat to the query group.')
    p_trade.add_argument("--stats-type", dest="stats_type", default="and",
                         choices=["and", "if", "count", "not", "weight"],
                         help="How to match the stat group: and=all must match, count=N of M, etc. (default: and)")
    p_trade.add_argument("--stats-min-count", dest="stats_min_count", type=int, default=None,
                         help="For --stats-type=count, minimum number of stats that must match")
    p_trade.add_argument("--stat-group", dest="stat_groups_json", metavar="JSON",
                         action="append", default=[],
                         help='Independent stat group as JSON: \'{"type":"and","filters":[{"id":"...","min":30}]}\'. '
                              'Repeatable. When used, overrides --stat-filter/--stats-type/--stats-min-count.')

    # search
    p_search = sub.add_parser(
        "search",
        help="Find items by stat keyword and show prices",
    )
    p_search.add_argument("keyword", nargs="+",
                          help="Stat keyword, e.g. 'maximum life', 'lightning damage'")
    p_search.add_argument("--type", "-t", default="",
                          help="Item type filter: unique, base, gem (comma-separated, default all)")
    p_search.add_argument("--slot", "-s", default="",
                          help="Slot filter for bases/uniques, e.g. Ring, Gloves, 'Body Armour'")
    p_search.add_argument("--limit", "-l", type=int, default=10,
                          help="Max results per type (default 10)")
    p_search.add_argument("--live", action="store_true",
                          help="Fetch live prices from trade API (slower, 1 request per item)")
    p_search.add_argument("--ilvl-min", type=int, default=80,
                          help="Min ilvl for base item price lookup (default 80)")
    p_search.add_argument("--rarity", "-r", default="nonunique",
                          choices=["nonunique", "normal", "magic", "rare", "any"],
                          help="Rarity filter for base live lookups (default: nonunique)")

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        _disable_color()

    handlers = {
        "status":    cmd_status,
        "league":    cmd_league,
        "refresh":   cmd_refresh,
        "general":   cmd_general,
        "equipment": cmd_equipment,
        "atlas":     cmd_atlas,
        "list":      cmd_list,
        "search":    cmd_search,
        "stats":     cmd_stats,
        "trade":     cmd_trade,
    }

    handler = handlers.get(args.cmd)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args) or 0)


if __name__ == "__main__":
    main()
