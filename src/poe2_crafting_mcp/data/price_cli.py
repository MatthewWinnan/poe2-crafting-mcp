"""
poe2-price — economy CLI for PoE2 price lookups and item searches.

Usage:
    poe2-price status                         # data freshness + active league
    poe2-price league                         # detect current league from poe.ninja
    poe2-price refresh [--league NAME]        # fetch fresh prices from poe.ninja
    poe2-price rate <name>                    # currency / fragment price
    poe2-price item <name> [--cat CATEGORY]  # unique / base / gem price
    poe2-price list <category>               # all cached prices for a category
    poe2-price search <stat> [OPTIONS]       # find items by stat, show with prices

Examples:
    poe2-price status
    poe2-price league
    poe2-price refresh
    poe2-price rate "Divine Orb"
    poe2-price rate "Lesser Essence of Electricity"
    poe2-price item "Kaom's Heart"
    poe2-price item "Titan Greaves" --cat base
    poe2-price item "Titan Greaves" --base --rarity magic   # magic bases only
    poe2-price item "Titan Greaves" --base --rarity rare    # rare bases only
    poe2-price list currency
    poe2-price list unique --limit 20
    poe2-price search "maximum life" --type unique --slot ring
    poe2-price search "lightning damage" --type unique
    poe2-price search "energy shield" --type base --slot "Body Armour"
    poe2-price search "energy shield" --type base --live --rarity magic  # magic base prices

    poe2-price stats --refresh                                    # fetch ~6000 stat IDs
    poe2-price stats --search "energy shield"                     # find stat ID for ES
    poe2-price trade "energy shield" --slot gloves --rarity magic # magic gloves with ES
    poe2-price trade "energy shield" --slot gloves --tier 1       # T1 ES min value auto-looked up
    poe2-price trade "maximum life" --slot ring --rarity rare --min 80
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


def _fmt_price_row(row: dict, indent: int = 2) -> None:
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

    print(f"{pad}{_BOLD}{name}{_RESET}  {cat_color}[{cat}]{_RESET}")
    print(f"{pad}  {_fmt_chaos(chaos)}{_fmt_divine(divine)}  "
          f"{_DIM}{count:,} listings{_RESET}")


def _fmt_price_inline(row: dict) -> str:
    """Single-line price string for search result annotations."""
    chaos  = row.get("chaos_value")
    divine = row.get("divine_value")
    count  = row.get("listing_count", 0)
    price  = _fmt_chaos(chaos) + _fmt_divine(divine)
    return f"{price}  {_DIM}({count:,} listings){_RESET}"


# ── Trade result formatter ────────────────────────────────────────────────────

def _fmt_trade_result(result: dict) -> None:
    """Pretty-print a TradeClient.estimate_price() result."""
    if not result.get("found"):
        err = result.get("error") or result.get("note") or "Not found"
        print(f"  {_RED}{err}{_RESET}")
        return

    name     = result.get("name", "?")
    total    = result.get("total_listings", 0)
    sample   = result.get("sample_size", 0)
    min_p    = result.get("min_price", {})
    med_p    = result.get("median_price", {})

    print(_h(f"Live Price — {name}"))
    print(f"  {_DIM}Total listings:{_RESET} {total:,}  {_DIM}(sampled {sample}){_RESET}")
    if min_p:
        amt = min_p["amount"]; cur = min_p["currency"]
        print(f"  {_BOLD}Min:   {_RESET}{_CYAN}{amt} {cur}{_RESET}")
    if med_p:
        amt = med_p["amount"]; cur = med_p["currency"]
        print(f"  {_BOLD}Median:{_RESET}{_YELLOW}{amt} {cur}{_RESET}")
    if result.get("trade_url"):
        print(f"  {_DIM}Trade:{_RESET}  {_BLUE}{result['trade_url']}{_RESET}")
    if result.get("note"):
        print(f"  {_DIM}{result['note']}{_RESET}")

    listings = result.get("listings", [])
    if listings:
        print(f"\n  {_DIM}Sample listings:{_RESET}")
        for lst in listings[:8]:
            rarity = lst.get("rarity", "")
            ilvl   = lst.get("ilvl", "")
            base   = lst.get("base_type", "")
            acc    = lst.get("account", "")
            amt    = lst.get("price_amount", "?")
            cur    = lst.get("price_currency", "")
            ilvl_str = f"  {_DIM}ilvl {ilvl}{_RESET}" if ilvl else ""
            base_str = f"  {_DIM}{base}{_RESET}" if base else ""
            print(f"    {_CYAN}{amt} {cur}{_RESET}{ilvl_str}{base_str}  {_DIM}{acc}{_RESET}")


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
    trade_ids = [c[4] for c in CURRENCIES if c[4]]

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
    print(f"  {_DIM}Note: item prices (uniques/bases/gems) not available via poe.ninja PoE2 API.{_RESET}")
    return 0


def cmd_rate(args: argparse.Namespace) -> int:
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase()
    league = args.league or pdb.get_active_league() or ""
    if not league:
        print(f"{_RED}No active league. Run: poe2-price league{_RESET}", file=sys.stderr)
        return 1

    name = " ".join(args.name)

    # Try exact match on currency/fragment first
    row = None
    for cat in ("currency", "fragment"):
        row = pdb.get_price(name, league, cat)
        if row:
            break

    if not row:
        results = pdb.search_prices(name, league, limit=8)
        currency_results = [r for r in results if r["category"] in ("currency", "fragment")]
        if not currency_results:
            print(f"{_RED}'{name}' not found in price cache.{_RESET}")
            print(f"{_DIM}Run: poe2-price refresh{_RESET}")
            return 1
        if len(currency_results) == 1:
            row = currency_results[0]
        else:
            print(_h(f"Currency matches for '{name}'"))
            for r in currency_results:
                _fmt_price_row(r)
                print()
            return 0

    print(_h("Currency Rate"))
    _fmt_price_row(row)
    fetched = row.get("fetched_at", "")[:19].replace("T", " ")
    if fetched:
        print(f"  {_DIM}cached: {fetched} UTC{_RESET}")
    return 0


def cmd_item(args: argparse.Namespace) -> int:
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

    _fmt_trade_result(result)
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

    print(_h(f"{category.title()} prices — {league}"))
    print(f"  {_DIM}Showing {len(rows)} of {total} items, sorted by listing count{_RESET}\n")

    for row in rows:
        chaos  = row.get("chaos_value")
        divine = row.get("divine_value")
        count  = row.get("listing_count", 0)
        name   = row.get("name", "?")
        price  = _fmt_chaos(chaos) + _fmt_divine(divine)
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
    stat_filter: dict = {"id": chosen["stat_id"]}
    if min_val is not None:
        stat_filter["min"] = min_val
    if args.max_val is not None:
        stat_filter["max"] = args.max_val

    rarity = args.rarity
    ilvl_min = args.ilvl_min

    print(f"  {_DIM}Searching: rarity={rarity}, ilvl≥{ilvl_min}"
          + (f", category={category}" if category else "")
          + (f", min={min_val}" if min_val is not None else "")
          + f"…{_RESET}\n")

    try:
        result = TradeClient().estimate_trade_price(
            league,
            stat_filters=[stat_filter],
            category=category,
            rarity=rarity,
            ilvl_min=ilvl_min,
            sample=args.sample,
        )
    except TradeError as e:
        print(f"{_RED}Trade API error: {e}{_RESET}", file=sys.stderr)
        return 1

    _fmt_trade_result(result)
    return 0


def _lookup_tier_min(keyword: str, tier: int, slot: str = "") -> float | None:
    """
    Look up the minimum stat value for a given mod tier from the game DB.

    Queries item_mods FTS for the keyword, groups by mod group, sorts by
    stat_min DESC (T1 = highest value), and returns the value at tier index.
    """
    try:
        from poe2_crafting_mcp.data.database import PoBDatabase
        db = PoBDatabase()
    except (FileNotFoundError, Exception):
        return None

    try:
        # FTS search item_mods for this keyword
        safe_kw = keyword.replace('"', '""')
        rows = db._conn.execute(
            "SELECT m.group_name, m.stat_min, m.weight_keys"
            " FROM item_mods m"
            " JOIN item_mods_fts f ON m.rowid = f.rowid"
            " WHERE f.stat_text MATCH ?"
            "   AND m.stat_min IS NOT NULL"
            "   AND m.category = 'Item'"
            " ORDER BY m.stat_min DESC",
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

    # Deduplicate: find the best-matching group (highest T1 value)
    seen: dict[str, float] = {}
    for r in rows:
        gn = r["group_name"] or ""
        if gn not in seen:
            seen[gn] = r["stat_min"]

    if not seen:
        return None

    best_group = max(seen, key=lambda g: seen[g])

    # Collect all tiers for this group, sorted best → worst
    tier_rows = sorted(
        [r for r in rows if (r["group_name"] or "") == best_group],
        key=lambda r: r["stat_min"],
        reverse=True,
    )

    idx = tier - 1
    if idx < 0 or idx >= len(tier_rows):
        idx = min(len(tier_rows) - 1, max(0, idx))

    return tier_rows[idx]["stat_min"]


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

    # rate
    p_rate = sub.add_parser("rate", help="Look up a currency or fragment price")
    p_rate.add_argument("name", nargs="+", help="Currency name, e.g. 'Divine Orb'")

    # item
    p_item = sub.add_parser("item", help="Look up live trade price for an item")
    p_item.add_argument("name", nargs="+", help="Item name, e.g. \"Kaom's Heart\" or base name")
    p_item.add_argument("--cat", "-c", default="",
                        help="Category hint: unique, base, gem")
    p_item.add_argument("--base", action="store_true",
                        help="Treat name as a base item type (not a unique)")
    p_item.add_argument("--ilvl-min", type=int, default=80,
                        help="Minimum item level for base searches (default 80)")
    p_item.add_argument("--rarity", "-r", default="nonunique",
                        choices=["nonunique", "normal", "magic", "rare", "any"],
                        help="Rarity filter for base searches (default: nonunique)")

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
                         help="Stat type hint for disambiguation: explicit, implicit, pseudo")
    p_trade.add_argument("--sample", type=int, default=5,
                         help="Listings to fetch for price estimate (default 5)")

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
        "status":  cmd_status,
        "league":  cmd_league,
        "refresh": cmd_refresh,
        "rate":    cmd_rate,
        "item":    cmd_item,
        "list":    cmd_list,
        "search":  cmd_search,
        "stats":   cmd_stats,
        "trade":   cmd_trade,
    }

    handler = handlers.get(args.cmd)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args) or 0)


if __name__ == "__main__":
    main()
