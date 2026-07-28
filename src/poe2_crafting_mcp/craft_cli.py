"""
poe2-craft — standalone CLI for PoE2 crafting data management.

Usage:
    poe2-craft status              # check all DB statuses + current league
    poe2-craft seed [--force]      # seed stale/missing DBs in correct order
    poe2-craft seed --only etl     # seed only a specific data source
    poe2-craft mcp                 # start the MCP server (stdio)

Examples:
    poe2-craft status              # see what's fresh, stale, or missing
    poe2-craft seed                # auto-seed everything that needs it
    poe2-craft seed --skip-wiki    # seed without wiki fetching
    poe2-craft seed --only prices  # refresh just prices
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


# ── ANSI helpers ──────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[90m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"


def _h(title: str) -> str:
    return f"{_BOLD}{_CYAN}{title}{_RESET}"


# ── Status ────────────────────────────────────────────────────────────────────

_STATUS_ICONS = {
    "fresh":        f"{_GREEN}fresh{_RESET}",
    "stale":        f"{_YELLOW}stale{_RESET}",
    "stale_ttl":    f"{_YELLOW}stale (ttl){_RESET}",
    "stale_league": f"{_YELLOW}stale (league){_RESET}",
    "stale_age":    f"{_YELLOW}stale (age){_RESET}",
    "missing":      f"{_RED}missing{_RESET}",
    "never_run":    f"{_RED}never run{_RESET}",
    "never_seeded": f"{_RED}never seeded{_RESET}",
    "unknown":      f"{_DIM}unknown{_RESET}",
}


def _fmt_status(s: str) -> str:
    return _STATUS_ICONS.get(s, s)


def _get_pdb():
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    return PriceDatabase()


def _detect_league(pdb) -> str | None:
    """Try to get active league from DB or auto-detect from poe.ninja."""
    league = pdb.get_active_league()
    if league:
        return league
    try:
        from poe2_crafting_mcp.data.economy import NinjaClient
        league = NinjaClient().get_current_league()
        pdb.set_active_league(league)
        return league
    except Exception:
        return None


def _gather_status(pdb, league: str | None) -> dict:
    """Collect status for all data sources."""
    result: dict = {"league": league}

    # ETL
    if league:
        result["etl"] = pdb.etl_status(league)
    else:
        etl_ran = pdb.get_meta("etl_ran_at")
        result["etl"] = {"status": "never_run" if not etl_ran else "fresh"}

    # Mod weights
    result["mod_weights"] = pdb.mod_weight_status()

    # Concepts
    result["concepts"] = pdb.concept_status()

    # Item descriptions
    result["item_descriptions"] = pdb.item_desc_status()

    # Prices
    if league:
        result["prices"] = pdb.price_cache_status(league)
    else:
        result["prices"] = {"status": "unknown"}

    # Essences (check essences table count)
    try:
        ess_count = pdb._conn.execute(
            "SELECT COUNT(*) FROM essences"
        ).fetchone()[0]
        result["essences"] = {"status": "fresh" if ess_count > 0 else "never_seeded",
                              "total": ess_count}
    except Exception:
        result["essences"] = {"status": "never_seeded", "total": 0}

    return result


def cmd_status(argv: list[str]) -> int:
    """Check all DB statuses and show current league."""
    p = argparse.ArgumentParser(
        prog="poe2-craft status",
        description="Check freshness of all data sources and show current league.",
    )
    p.add_argument("--json", action="store_true", help="Output as JSON")
    args = p.parse_args(argv)

    pdb = _get_pdb()
    league = _detect_league(pdb)
    status = _gather_status(pdb, league)

    if args.json:
        import json
        print(json.dumps(status, indent=2, default=str))
        return 0

    print()
    print(f"  {_h('League')}     {league or f'{_RED}not detected{_RESET}'}")
    print()

    # Table format
    rows = [
        ("ETL (PoB data)", status["etl"]),
        ("Mod weights",    status["mod_weights"]),
        ("Essences",       status["essences"]),
        ("Concepts",       status["concepts"]),
        ("Item desc",      status["item_descriptions"]),
        ("Prices",         status["prices"]),
    ]

    for label, info in rows:
        st = info.get("status", "unknown")
        icon = _fmt_status(st)
        extra = ""
        total = info.get("total")
        if total is not None:
            extra += f"  {_DIM}({total}){_RESET}"
        age = info.get("age_days") or info.get("age_minutes")
        if age is not None:
            unit = "d" if "age_days" in info else "m"
            extra += f"  {_DIM}{age:.1f}{unit} ago{_RESET}"
        print(f"  {label:<18} {icon}{extra}")

    # Summary
    stale = [label for label, info in rows
             if info.get("status") not in ("fresh", "unknown")]
    if stale:
        print(f"\n  {_YELLOW}Stale/missing: {', '.join(stale)}{_RESET}")
        print(f"  {_DIM}Run: poe2-craft seed{_RESET}")
    else:
        print(f"\n  {_GREEN}All data sources are up to date.{_RESET}")

    print()
    return 0


# ── Seed ──────────────────────────────────────────────────────────────────────

_SEED_ORDER = ["etl", "mod_weights", "essences", "concepts", "item_descriptions", "prices"]

_SEED_LABELS = {
    "etl": "ETL (PoB game data)",
    "mod_weights": "Mod weights (poe2db)",
    "essences": "Essences (poe2db)",
    "concepts": "Concepts (built-ins + wiki)",
    "item_descriptions": "Item descriptions (built-ins + wiki)",
    "prices": "Prices (poe.ninja)",
}


def _seed_etl(pdb, dry_run: bool = False) -> None:
    if dry_run:
        print(f"    {_YELLOW}Would run ETL pipeline{_RESET}")
        return
    print(f"    {_DIM}Running ETL pipeline...{_RESET}", flush=True)
    from poe2_crafting_mcp.data.etl import run as run_etl
    counts = run_etl()
    total = sum(counts.values())
    print(f"    {_GREEN}Done: {total} rows across {len(counts)} tables{_RESET}")


def _seed_mod_weights(pdb, dry_run: bool = False) -> None:
    from poe2_crafting_mcp.data.poe2db_client import Poe2DbClient, ALL_ITEM_CLASSES
    if dry_run:
        print(f"    {_YELLOW}Would fetch {len(ALL_ITEM_CLASSES)} item classes from poe2db.tw{_RESET}")
        return
    client = Poe2DbClient()
    total_mods = 0
    failed = []
    n = len(ALL_ITEM_CLASSES)
    print(f"    {_DIM}Fetching {n} item classes from poe2db.tw (~{n * 3}s)...{_RESET}", flush=True)
    for i, item_class in enumerate(ALL_ITEM_CLASSES):
        if i > 0:
            time.sleep(2.5)
        try:
            mods = client.fetch_mods(item_class)
            if mods:
                pdb.upsert_mod_weights(item_class, mods)
                total_mods += len(mods)
            pct = (i + 1) / n * 100
            if (i + 1) % 10 == 0 or i == n - 1:
                print(f"    {_DIM}  [{pct:.0f}%] {item_class}: {len(mods)} mods{_RESET}", flush=True)
        except Exception as e:
            failed.append(f"{item_class}: {e}")
    pdb.set_meta("mod_weights_seeded_at", pdb._now_iso())
    pdb._conn.commit()
    print(f"    {_GREEN}Done: {total_mods} mods{_RESET}")
    if failed:
        print(f"    {_RED}Failed: {len(failed)}{_RESET}")


def _seed_essences(pdb, dry_run: bool = False) -> None:
    if dry_run:
        print(f"    {_YELLOW}Would fetch essences from poe2db.tw{_RESET}")
        return
    from poe2_crafting_mcp.data.poe2db_client import Poe2DbClient
    client = Poe2DbClient()
    print(f"    {_DIM}Fetching essences from poe2db.tw...{_RESET}", flush=True)
    essences = client.fetch_essences()
    if essences:
        pdb._conn.execute("DELETE FROM essences")
        for ess in essences:
            pdb._conn.execute(
                "INSERT OR REPLACE INTO essences "
                "(name, tier, base_name, effect_type, item_slots, stat_text, stat_min, stat_max) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ess["name"], ess["tier"], ess["base_name"], ess["effect_type"],
                 ess["item_slots"], ess["stat_text"], ess.get("stat_min"), ess.get("stat_max")),
            )
        pdb._conn.commit()
    print(f"    {_GREEN}Done: {len(essences)} essence effects{_RESET}")


def _seed_concepts(pdb, skip_wiki: bool = False, dry_run: bool = False) -> None:
    from poe2_crafting_mcp.data.concepts import CONCEPTS
    if dry_run:
        print(f"    {_YELLOW}Would seed {len(CONCEPTS)} concepts{_RESET}")
        return
    n = pdb.upsert_concepts_bulk(CONCEPTS)
    print(f"    {n} concepts from built-ins.")

    if not skip_wiki:
        print(f"    {_DIM}Fetching from poe2wiki.net...{_RESET}", flush=True)
        from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
        wiki = Poe2WikiClient()
        fetched, skipped = wiki.seed_concepts_from_db(pdb)
        try:
            pdb._conn.execute("INSERT INTO concepts_fts(concepts_fts) VALUES('rebuild')")
            pdb._conn.commit()
        except Exception:
            pass
        print(f"    {_GREEN}Done: {fetched} from wiki ({skipped} skipped){_RESET}")


def _seed_item_descriptions(pdb, skip_wiki: bool = False, dry_run: bool = False) -> None:
    from poe2_crafting_mcp.data.item_descriptions import ITEM_DESCRIPTIONS
    if dry_run:
        print(f"    {_YELLOW}Would seed {len(ITEM_DESCRIPTIONS)} item descriptions{_RESET}")
        return
    n = pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)
    print(f"    {n} descriptions from built-ins.")

    if not skip_wiki:
        from poe2_crafting_mcp.data.database import PoBDatabase
        from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
        from poe2_crafting_mcp.data.general_items import all_exchange_item_names

        try:
            db = PoBDatabase()
        except FileNotFoundError:
            print(f"    {_RED}Cannot fetch wiki items — ETL DB not found. Run ETL first.{_RESET}")
            return

        currency_rows = db.search_currencies(limit=5000)
        base_rows = db.search_bases(limit=5000)
        seen: set[str] = set()
        names: list[str] = []
        for r in list(currency_rows) + list(base_rows):
            n_name = r["name"]
            if n_name not in seen:
                seen.add(n_name)
                names.append(n_name)
        for n_name in all_exchange_item_names():
            if n_name not in seen:
                seen.add(n_name)
                names.append(n_name)

        n_batches = (len(names) + 49) // 50
        print(f"    {_DIM}Fetching {len(names)} items from wiki ({n_batches} batches)...{_RESET}",
              flush=True)
        wiki = Poe2WikiClient()
        items = wiki.fetch_items(names)
        for item in items:
            pdb.upsert_item_desc(**item)
        try:
            pdb._conn.execute(
                "INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES('rebuild')")
            pdb._conn.commit()
        except Exception:
            pass
        print(f"    {_GREEN}Done: {len(items)} from wiki{_RESET}")


def _seed_prices(pdb, dry_run: bool = False) -> None:
    if dry_run:
        print(f"    {_YELLOW}Would fetch prices from poe.ninja{_RESET}")
        return
    league = _detect_league(pdb)
    if not league:
        print(f"    {_RED}Cannot detect league — skipping prices{_RESET}")
        return

    from poe2_crafting_mcp.data.economy import NinjaClient, GENERAL_ITEM_TYPES
    from poe2_crafting_mcp.data.currencies import CURRENCIES

    client = NinjaClient()
    pdb.set_active_league(league)

    print(f"    {_DIM}Fetching from poe.ninja ({league})...{_RESET}", flush=True)

    # ── Currency exchange rates (orbs, quality, other) ────────────────────────
    _CURRENCY_EXCHANGE_CATS = {"Orb", "Quality", "Other"}
    trade_ids = [c[4] for c in CURRENCIES if c[4] and c[1] in _CURRENCY_EXCHANGE_CATS]
    try:
        rows = client.fetch_currency_rates(league, trade_ids)
        if rows:
            pdb.upsert_prices(rows, league)
    except Exception as e:
        print(f"    {_YELLOW}Currency rates failed: {e}{_RESET}")

    # ── General exchange categories (essences, runes, omens, etc.) ────────────
    for item_type, label in GENERAL_ITEM_TYPES:
        try:
            gen_rows = client.fetch_exchange_category(league, item_type)
            if gen_rows:
                pdb.upsert_prices(gen_rows, league)
        except Exception as e:
            print(f"    {_YELLOW}{label} failed: {e}{_RESET}")

    # Fill chaos values from divine rates
    try:
        pdb.fill_chaos_from_divine(league)
    except Exception:
        pass  # non-critical

    total = pdb._conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    print(f"    {_GREEN}Done: {total} prices for {league}{_RESET}")


_SEEDERS = {
    "etl": _seed_etl,
    "mod_weights": _seed_mod_weights,
    "essences": _seed_essences,
    "concepts": _seed_concepts,
    "item_descriptions": _seed_item_descriptions,
    "prices": _seed_prices,
}


def cmd_seed(argv: list[str]) -> int:
    """Seed stale or missing data sources in the correct order."""
    p = argparse.ArgumentParser(
        prog="poe2-craft seed",
        description="Seed all stale or missing data sources in the correct order.",
    )
    p.add_argument("--force", action="store_true",
                   help="Re-seed all sources even if fresh")
    p.add_argument("--only", default="",
                   help=f"Seed only: {', '.join(_SEED_ORDER)}")
    p.add_argument("--skip-wiki", action="store_true",
                   help="Skip wiki fetching for concepts and item descriptions")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be done")
    args = p.parse_args(argv)

    pdb = _get_pdb()
    league = _detect_league(pdb)
    status = _gather_status(pdb, league)

    if args.only:
        targets = [args.only]
        if args.only not in _SEEDERS:
            print(f"{_RED}Unknown source '{args.only}'. "
                  f"Options: {', '.join(_SEED_ORDER)}{_RESET}")
            return 1
    else:
        targets = _SEED_ORDER

    print()
    if league:
        print(f"  {_h('League')}  {league}")
    print()

    seeded = 0
    t0 = time.time()

    for source in targets:
        info = status.get(source, {})
        st = info.get("status", "unknown")
        needs_seed = st not in ("fresh",) or args.force or args.only

        label = _SEED_LABELS.get(source, source)

        if not needs_seed:
            print(f"  {_GREEN}[skip]{_RESET} {label} — already fresh")
            continue

        print(f"  {_BOLD}[seed]{_RESET} {label} ({_fmt_status(st)})")

        seeder = _SEEDERS[source]
        # Pass skip_wiki for concepts and item_descriptions
        if source in ("concepts", "item_descriptions"):
            seeder(pdb, skip_wiki=args.skip_wiki, dry_run=args.dry_run)
        else:
            seeder(pdb, dry_run=args.dry_run)

        seeded += 1

    elapsed = time.time() - t0
    print()
    if args.dry_run:
        print(f"  {_YELLOW}Dry run — no changes made.{_RESET}")
    elif seeded == 0:
        print(f"  {_GREEN}Everything is already fresh. Use --force to re-seed.{_RESET}")
    else:
        print(f"  {_GREEN}Seeded {seeded} source(s) in {elapsed:.1f}s{_RESET}")
    print()
    return 0


# ── Help ──────────────────────────────────────────────────────────────────────

HELP_TEXT = f"""{_BOLD}poe2-craft{_RESET} — PoE2 crafting data manager

{_BOLD}Commands:{_RESET}
  {_CYAN}status{_RESET}           Check all data sources and current league
  {_CYAN}seed{_RESET}             Seed stale/missing data in correct order
  {_CYAN}seed --force{_RESET}     Re-seed all data sources
  {_CYAN}seed --only X{_RESET}    Seed only: etl, mod_weights, essences, concepts, item_descriptions, prices
  {_CYAN}mcp{_RESET}              Start the MCP server (stdio transport)

{_BOLD}Data sources{_RESET} (seed order):
  1. ETL            PoB vendor data → bases, mods, gems, uniques, nodes, currencies
  2. Mod weights    poe2db.tw → spawn weights per item class
  3. Essences       poe2db.tw → essence-guaranteed mods per slot
  4. Concepts       built-ins + poe2wiki.net → game mechanic definitions
  5. Item desc      built-ins + poe2wiki.net → item/currency descriptions
  6. Prices         poe.ninja → current economy prices

{_BOLD}Options:{_RESET}
  --skip-wiki      Skip wiki fetching (concepts + item descriptions)
  --dry-run        Show what would be done without writing
  --json           (status) Output as JSON
  --force          (seed) Re-seed even if fresh
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(HELP_TEXT)
        sys.exit(0)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "status":
        sys.exit(cmd_status(rest))
    elif cmd == "seed":
        sys.exit(cmd_seed(rest))
    elif cmd == "mcp":
        from poe2_crafting_mcp.server import main as mcp_main
        mcp_main()
    else:
        print(f"{_RED}Unknown command: {cmd}{_RESET}")
        print(f"Run {_BOLD}poe2-craft --help{_RESET} for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
