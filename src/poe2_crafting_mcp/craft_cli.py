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


# ── Sim: Interactive Crafting ─────────────────────────────────────────────────

def cmd_sim(argv: list[str]) -> int:
    """Interactive crafting simulator with save/load item state."""
    import json as _json
    import random as _random

    p = argparse.ArgumentParser(
        prog="poe2-craft sim",
        description="Interactive crafting simulator. Apply currencies step-by-step.",
    )
    p.add_argument("base", nargs="?", help="Base item name (e.g. 'Gold Gloves') or item class")
    p.add_argument("--ilvl", type=int, default=82, help="Item level (default: 82)")
    p.add_argument("--load", type=str, help="Load item state from JSON file")
    p.add_argument("--seed", type=int, help="Random seed for reproducibility")
    args = p.parse_args(argv)

    if args.seed is not None:
        _random.seed(args.seed)

    from poe2_crafting_mcp.crafting.simulator import (
        CraftingSimulator, ItemState, ModInstance, CURRENCIES, OMENS,
        get_max_sockets_for_item_class,
    )
    from poe2_crafting_mcp.crafting.desecration import DesecrationEngine, BONES, get_bone_slot_for_item_class
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase()
    desecration = DesecrationEngine()
    history: list[dict] = []

    # ── Load or create item ───────────────────────────────────────────────────
    if args.load:
        filepath = args.load
        if filepath.endswith(".txt"):
            # Load from PoB text format
            from poe2_crafting_mcp.crafting.pob_export import pob_text_to_item_state
            with open(filepath) as f:
                text = f.read()
            item, base_name, item_name = pob_text_to_item_state(text)
            item_class = item.item_class
            ilvl = item.ilvl
            history = []
            print(f"  {_GREEN}Loaded PoB item from {filepath}{_RESET}")
        else:
            # Load from JSON
            with open(filepath) as f:
                state = _json.load(f)
            item_class = state["item_class"]
            ilvl = state["ilvl"]
            item = ItemState(
                item_class=item_class,
                ilvl=ilvl,
                rarity=state["rarity"],
                mods=[ModInstance(**m) for m in state["mods"]],
                corrupted=state.get("corrupted", False),
                essence_mod_family=state.get("essence_mod_family"),
                quality=state.get("quality", 0),
                sockets=state.get("sockets", []),
                max_sockets=state.get("max_sockets", 0),
                implicits=[ModInstance(**m) for m in state.get("implicits", [])],
            )
            history = state.get("history", [])
            base_name = state.get("base_name", item_class)
            print(f"  {_GREEN}Loaded item from {filepath}{_RESET}")
    elif args.base:
        # Resolve base name to item_class
        item_class = _resolve_item_class(pdb, args.base)
        if not item_class:
            print(f"{_RED}Cannot resolve '{args.base}' to an item class.{_RESET}")
            return 1
        ilvl = args.ilvl
        item = ItemState(
            item_class=item_class, ilvl=ilvl, rarity="Normal",
            max_sockets=get_max_sockets_for_item_class(item_class),
        )
        base_name = args.base
        print(f"  {_GREEN}Created: {base_name} ({item_class}, ilvl {ilvl}){_RESET}")
    else:
        print(f"{_RED}Provide a base name or --load file.{_RESET}")
        p.print_help()
        return 1

    # Create simulator with pools
    sim = CraftingSimulator.from_db(item_class, ilvl)
    sim.item = item

    # Currency usage tracker: {name: count}
    currency_used: dict[str, int] = {}

    def _track(name: str, count: int = 1) -> None:
        """Record currency/omen usage."""
        currency_used[name] = currency_used.get(name, 0) + count

    # ── REPL ──────────────────────────────────────────────────────────────────
    print()
    _print_item(item, base_name)
    print()
    print(f"  {_DIM}Commands: <currency> [--omens x,y] [--essence_family F] | desecrate <bone>"
          f" | save <file> | load <file> | pool | cost | history | help | quit{_RESET}")
    print()

    while True:
        try:
            line = input(f"{_CYAN}>{_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            break

        elif cmd == "help":
            _sim_help()

        elif cmd == "save":
            if len(parts) < 2:
                print(f"  {_RED}Usage: save <filename.json|.txt>{_RESET}")
                continue
            filepath = parts[1]
            if filepath.endswith(".txt"):
                # Save as PoB text format
                from poe2_crafting_mcp.crafting.pob_export import item_state_to_pob_text
                text = item_state_to_pob_text(item, base_name)
                with open(filepath, "w") as f:
                    f.write(text)
                print(f"  {_GREEN}Saved PoB text to {filepath}{_RESET}")
            else:
                # Save as JSON
                state = _serialize_item(item, base_name, item_class, ilvl, history)
                with open(filepath, "w") as f:
                    _json.dump(state, f, indent=2)
                print(f"  {_GREEN}Saved to {filepath}{_RESET}")

        elif cmd == "load":
            if len(parts) < 2:
                print(f"  {_RED}Usage: load <filename.json>{_RESET}")
                continue
            filepath = parts[1]
            try:
                with open(filepath) as f:
                    state = _json.load(f)
                item_class = state["item_class"]
                ilvl = state["ilvl"]
                item = ItemState(
                    item_class=item_class, ilvl=ilvl, rarity=state["rarity"],
                    mods=[ModInstance(**m) for m in state["mods"]],
                    corrupted=state.get("corrupted", False),
                    essence_mod_family=state.get("essence_mod_family"),
                    quality=state.get("quality", 0),
                    sockets=state.get("sockets", []),
                    max_sockets=state.get("max_sockets", 0),
                )
                sim = CraftingSimulator.from_db(item_class, ilvl)
                sim.item = item
                base_name = state.get("base_name", item_class)
                history = state.get("history", [])
                print(f"  {_GREEN}Loaded from {filepath}{_RESET}")
                _print_item(item, base_name)
            except Exception as e:
                print(f"  {_RED}Error loading: {e}{_RESET}")

        elif cmd == "history":
            if not history:
                print(f"  {_DIM}No history yet.{_RESET}")
            else:
                for i, h in enumerate(history, 1):
                    omens_str = f" +{','.join(h['omens'])}" if h.get("omens") else ""
                    extra = ""
                    if h.get("essence_family"):
                        extra += f" family={h['essence_family']}"
                    if h.get("bone"):
                        extra += f" bone={h['bone']}"
                    print(f"  {_DIM}{i}.{_RESET} {h['action']}{omens_str}{extra}")

        elif cmd == "stock":
            # Show reforge stock
            print(f"  {_BOLD}Reforge stock:{_RESET} {sim.reforge_stock} spare base(s)")
            if sim.reforge_stock >= 2:
                print(f"  {_GREEN}Can reforge (need 2 spares + current item){_RESET}")
            else:
                need = 2 - sim.reforge_stock
                print(f"  {_DIM}Need {need} more spare(s) to reforge{_RESET}")

        elif cmd == "cost":
            # Show total currencies consumed and estimated cost
            if not currency_used:
                print(f"  {_DIM}No currencies used yet.{_RESET}")
            else:
                # Map internal keys to price lookup names
                _PRICE_NAMES: dict[str, str] = {
                    "transmute": "Orb of Transmutation",
                    "greater_transmute": "Greater Orb of Transmutation",
                    "perfect_transmute": "Perfect Orb of Transmutation",
                    "augment": "Orb of Augmentation",
                    "greater_augment": "Greater Orb of Augmentation",
                    "perfect_augment": "Perfect Orb of Augmentation",
                    "alteration": "Orb of Alteration",
                    "regal": "Regal Orb",
                    "greater_regal": "Greater Regal Orb",
                    "perfect_regal": "Perfect Regal Orb",
                    "chaos": "Chaos Orb",
                    "greater_chaos": "Greater Chaos Orb",
                    "perfect_chaos": "Perfect Chaos Orb",
                    "exalted": "Exalted Orb",
                    "greater_exalted": "Greater Exalted Orb",
                    "perfect_exalted": "Perfect Exalted Orb",
                    "annulment": "Orb of Annulment",
                    "divine": "Divine Orb",
                    "vaal": "Vaal Orb",
                    "scour": "Orb of Scouring",
                    "fracturing": "Fracturing Orb",
                    "alchemy": "Orb of Alchemy",
                    "sinistral_exaltation": "Omen of Sinistral Exaltation",
                    "dextral_exaltation": "Omen of Dextral Exaltation",
                    "greater_exaltation": "Omen of Greater Exaltation",
                    "homogenising_exaltation": "Omen of Homogenising Exaltation",
                    "catalysing_exaltation": "Omen of Catalysing Exaltation",
                    "sinistral_annulment": "Omen of Sinistral Annulment",
                    "dextral_annulment": "Omen of Dextral Annulment",
                    "sinistral_erasure": "Omen of Sinistral Erasure",
                    "dextral_erasure": "Omen of Dextral Erasure",
                    "whittling": "Omen of Whittling",
                    "sinistral_crystallisation": "Omen of Sinistral Crystallisation",
                    "dextral_crystallisation": "Omen of Dextral Crystallisation",
                    "sinistral_coronation": "Omen of Sinistral Coronation",
                    "dextral_coronation": "Omen of Dextral Coronation",
                    "corruption": "Omen of Corruption",
                    "sanctification": "Omen of Sanctification",
                    "blessed": "Omen of the Blessed",
                    "blackblooded": "Omen of the Blackblooded",
                    "liege": "Omen of the Liege",
                    "sovereign": "Omen of the Sovereign",
                    "abyssal_echoes": "Omen of Abyssal Echoes",
                    "light": "Omen of Light",
                    # Bones
                    "preserved_jawbone": "Preserved Jawbone",
                    "preserved_rib": "Preserved Rib",
                    "preserved_collarbone": "Preserved Collarbone",
                    "preserved_cranium": "Preserved Cranium",
                    "preserved_vertebrae": "Preserved Vertebrae",
                    "ancient_jawbone": "Ancient Jawbone",
                    "ancient_rib": "Ancient Rib",
                    "ancient_collarbone": "Ancient Collarbone",
                    "gnawed_jawbone": "Gnawed Jawbone",
                    "gnawed_rib": "Gnawed Rib",
                    "gnawed_collarbone": "Gnawed Collarbone",
                }
                print(f"  {_BOLD}Currencies consumed:{_RESET}")
                total_cost = 0.0
                for name, count in sorted(currency_used.items()):
                    # Look up price by mapped name or raw name
                    lookup_name = _PRICE_NAMES.get(name, name)
                    price_row = pdb._conn.execute(
                        "SELECT chaos_value FROM prices WHERE name = ? COLLATE NOCASE LIMIT 1",
                        (lookup_name,),
                    ).fetchone()
                    if not price_row:
                        # Try without apostrophes
                        price_row = pdb._conn.execute(
                            "SELECT chaos_value FROM prices WHERE name = ? COLLATE NOCASE LIMIT 1",
                            (lookup_name.replace("'", ""),),
                        ).fetchone()
                    unit_price = price_row[0] if price_row else None
                    if unit_price:
                        line_cost = unit_price * count
                        total_cost += line_cost
                        print(f"    {lookup_name:38} ×{count:3}  @ {unit_price:.1f}c = {line_cost:.1f}c")
                    else:
                        print(f"    {lookup_name:38} ×{count:3}  @ ???")
                print(f"  {'─' * 55}")
                print(f"  {_BOLD}Total estimated cost: {total_cost:.1f} chaos{_RESET}")

        elif cmd == "stash":
            # Stash current item as reforge fodder, get fresh Normal
            sim.stash_for_reforge()
            item = sim.item
            history.append({"action": "stash", "omens": []})
            print(f"  {_DIM}Item stashed for reforging. Stock: {sim.reforge_stock}{_RESET}")
            print()
            _print_item(item, base_name)

        elif cmd == "buy_base":
            # Buy spare bases for reforge stock
            count = int(parts[1]) if len(parts) > 1 else 1
            sim.buy_base(count)
            history.append({"action": f"buy_base:{count}", "omens": []})
            print(f"  {_DIM}Bought {count} base(s). Stock: {sim.reforge_stock}{_RESET}")

        elif cmd == "pool":
            # Show available pool summary
            affix = parts[1] if len(parts) > 1 else ""
            min_lv_str = _parse_flag(parts, "--min")
            min_lv = int(min_lv_str) if min_lv_str else 0
            pool = sim.get_available_pool(
                min_mod_level=min_lv,
                gentype_only=1 if affix == "prefix" else 2 if affix == "suffix" else 0,
            )
            by_family: dict[str, list] = {}
            for m in pool:
                by_family.setdefault(m['family'], []).append(m)
            label = f"{affix + ' ' if affix else ''}pool"
            if min_lv:
                label += f" (min_lv={min_lv})"
            print(f"  {_BOLD}Available {label} ({len(pool)} tiers, {len(by_family)} families):{_RESET}")
            for fam, mods in sorted(by_family.items(), key=lambda x: -sum(m['weight'] for m in x[1])):
                total_w = sum(m['weight'] for m in mods)
                best_stat = mods[0]['stat_text'] if mods else ""
                print(f"    {fam:30} weight={total_w:5} ({len(mods)} tiers) {_DIM}{best_stat}{_RESET}")

        elif cmd in ("dpool", "desecrate-pool"):
            # Show desecration reveal pool (normal + desecrated-exclusive)
            affix = parts[1] if len(parts) > 1 else ""
            omens_str = _parse_flag(parts, "--omens")
            active_omens = omens_str.split(",") if omens_str else []

            # Determine affix type
            if affix in ("prefix", "suffix"):
                affix_type = affix
            else:
                affix_type = ""  # show both

            from poe2_crafting_mcp.crafting.desecration import DesecrationEngine as _DE
            _de = _DE()
            
            for at in ([affix_type] if affix_type else ["prefix", "suffix"]):
                pool = _de.get_reveal_pool(item_class, ilvl, at, "preserved_rib", item, omens=active_omens or None)
                normal_count = len([p for p in pool if not p.faction])
                lich_count = len([p for p in pool if p.faction])
                print(f"  {_BOLD}Desecrate reveal pool ({at}, {len(pool)} options: "
                      f"{normal_count} normal + {lich_count} abyss-exclusive):{_RESET}")
                for p in sorted(pool, key=lambda x: (x.faction or "zzz", x.family)):
                    faction_tag = f" [{p.faction}]" if p.faction else ""
                    print(f"    {p.affix_type:6} | {p.family:28} | {p.stat_text}{faction_tag}")
                print()

        elif cmd in ("vpool", "vaal-pool"):
            # Show available Vaal Orb corruption implicits for this item
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect('data/poe2_craft.db')
            conn.row_factory = _sqlite3.Row
            rows = conn.execute(
                "SELECT mod_family, stat_text, weight FROM mod_weights "
                "WHERE pool = 'corrupted' AND item_class = ? AND req_level <= ? "
                "ORDER BY mod_family",
                (item_class, ilvl),
            ).fetchall()
            conn.close()
            print(f"  {_BOLD}Vaal Orb implicit pool for {item_class} ({len(rows)} options):{_RESET}")
            if not rows:
                print(f"  {_DIM}No corruption implicits for this item class.{_RESET}")
            else:
                for r in rows:
                    print(f"    {r['mod_family']:35} | {r['stat_text']}")
            # Also show corruption_upgrade pool if available
            rows2 = conn if False else None  # reopen for upgrade pool
            conn2 = _sqlite3.connect('data/poe2_craft.db')
            conn2.row_factory = _sqlite3.Row
            upgrades = conn2.execute(
                "SELECT mod_family, stat_text FROM mod_weights "
                "WHERE pool = 'corruption_upgrade' AND item_class = ? AND req_level <= ? "
                "ORDER BY mod_family",
                (item_class, ilvl),
            ).fetchall()
            conn2.close()
            if upgrades:
                print(f"\n  {_BOLD}Orb of Sacrifice upgrades ({len(upgrades)}):{_RESET}")
                for r in upgrades:
                    print(f"    {r['mod_family']:35} | {r['stat_text']}")

        elif cmd == "currencies":
            # Show which currencies are valid for current item state
            print(f"  {_BOLD}Valid currencies for {item.rarity} item:{_RESET}")
            for cur_name, cur_def in sorted(CURRENCIES.items()):
                from_r = cur_def.get("from_rarity", [])
                if from_r and item.rarity not in from_r:
                    continue
                min_mods = cur_def.get("min_mods", 0)
                if min_mods and len(item.mods) < min_mods:
                    continue
                op = cur_def.get("op", "")
                # Skip add/augment if no open slots AND no rarity change that would create slots
                if op == "add" and item.open_affixes == 0:
                    if "to_rarity" not in cur_def:
                        continue  # truly no slots (e.g. augment on full Magic)
                to_r = cur_def.get("to_rarity", "")
                rarity_change = f" → {to_r}" if to_r else ""
                print(f"    {cur_name:25} op={op}{rarity_change}")

        elif cmd == "omens":
            # Show omens applicable to a currency
            target_cur = parts[1] if len(parts) > 1 else ""
            if not target_cur:
                print(f"  {_BOLD}Usage: omens <currency>{_RESET}")
                print(f"  {_DIM}Shows which omens apply to that currency.{_RESET}")
            else:
                print(f"  {_BOLD}Omens for '{target_cur}':{_RESET}")
                found = False
                for omen_name, omen_def in sorted(OMENS.items()):
                    if target_cur in omen_def.get("applies_to", []):
                        effect_parts = []
                        if omen_def.get("gentype_only") == 1:
                            effect_parts.append("prefix only")
                        elif omen_def.get("gentype_only") == 2:
                            effect_parts.append("suffix only")
                        if omen_def.get("qty_override"):
                            effect_parts.append(f"adds {omen_def['qty_override']} mods")
                        if omen_def.get("homogenise"):
                            effect_parts.append("shared tags only")
                        if omen_def.get("del_gentype_only") == 1:
                            effect_parts.append("removes prefix only")
                        elif omen_def.get("del_gentype_only") == 2:
                            effect_parts.append("removes suffix only")
                        if omen_def.get("del_target"):
                            effect_parts.append(f"removes {omen_def['del_target']}")
                        effect = ", ".join(effect_parts) if effect_parts else "special"
                        print(f"    {omen_name:30} {effect}")
                        found = True
                if not found:
                    print(f"    {_DIM}No omens apply to '{target_cur}'.{_RESET}")

        elif cmd == "essences":
            # Show available essences for this item slot
            from poe2_crafting_mcp.crafting.essence_resolver import EssenceResolver
            ess_resolver = EssenceResolver()
            # Determine slot from item_class
            slot = _item_class_to_slot(item_class)
            tier_filter = parts[1] if len(parts) > 1 else ""
            essences_list = ess_resolver.list_for_slot(slot, tier=tier_filter)
            if not essences_list:
                print(f"  {_DIM}No essences found for slot '{slot}'"
                      f"{' tier=' + tier_filter if tier_filter else ''}{_RESET}")
            else:
                print(f"  {_BOLD}Essences for {slot}"
                      f"{' (' + tier_filter + ')' if tier_filter else ''}:{_RESET}")
                for e in essences_list:
                    valid = ""
                    # Check if essence tier matches item rarity requirement
                    if e.tier in ("Lesser", "Normal", "Greater"):
                        if item.rarity not in ("Normal", "Magic"):
                            valid = f" {_DIM}(needs Magic item){_RESET}"
                    elif e.tier in ("Perfect", "Corrupted", "Alloy"):
                        if item.rarity != "Rare":
                            valid = f" {_DIM}(needs Rare item){_RESET}"
                    print(f"    {e.essence_name:40} {e.stat_text}{valid}")

        elif cmd == "bones":
            # Show available bones for this item
            slot_cat = get_bone_slot_for_item_class(item_class)
            print(f"  {_BOLD}Bones for {item_class} (category: {slot_cat}):{_RESET}")
            for bone_name, bone_def in sorted(BONES.items()):
                if bone_def["slots"] != slot_cat:
                    continue
                err = desecration.validate_bone(bone_name, item_class, ilvl)
                status = f" {_RED}({err}){_RESET}" if err else f" {_GREEN}✓{_RESET}"
                min_lv = bone_def.get("min_mod_level", 0)
                max_iv = bone_def.get("max_ilvl")
                desc = f"min_lv={min_lv}" if min_lv else ""
                if max_iv:
                    desc += f" max_ilvl={max_iv}"
                print(f"    {bone_name:25} {desc:20}{status}")

        elif cmd in ("essence", "use_essence"):
            # Apply essence by name — resolve family and stat_text from DB
            from poe2_crafting_mcp.crafting.essence_resolver import EssenceResolver
            ess_resolver = EssenceResolver()

            # Parse essence name (everything after 'essence' that's not a flag)
            ess_name_parts = []
            i = 1
            while i < len(parts) and not parts[i].startswith("--"):
                ess_name_parts.append(parts[i])
                i += 1
            ess_name = " ".join(ess_name_parts)

            if not ess_name:
                print(f"  {_RED}Usage: essence \"Greater Essence of the Body\"{_RESET}")
                print(f"  {_DIM}Run 'essences' to see available options.{_RESET}")
                continue

            # Resolve slot
            slot = _item_class_to_slot(item_class)
            resolved = ess_resolver.resolve(ess_name, slot)
            if not resolved:
                print(f"  {_RED}Cannot resolve '{ess_name}' for slot '{slot}'.{_RESET}")
                print(f"  {_DIM}Run 'essences' to see available options.{_RESET}")
                continue

            # Determine currency key from tier
            tier_to_currency = {
                "Lesser": "lesser_essence",
                "Normal": "normal_essence",
                "Greater": "greater_essence",
                "Perfect": "perfect_essence",
                "Corrupted": "perfect_essence",  # corrupted essences use swap mechanic
                "Alloy": "perfect_essence",       # alloys also use swap mechanic
            }
            currency_key = tier_to_currency.get(resolved.tier)
            if not currency_key:
                print(f"  {_RED}Unknown essence tier: {resolved.tier}{_RESET}")
                continue

            # Resolve mod_family from stat_text via mod_weights join
            mod_family = _resolve_essence_family(pdb, resolved.stat_text, item_class)
            if not mod_family:
                print(f"  {_YELLOW}Warning: could not resolve mod_family for stat_text. "
                      f"Using best-effort.{_RESET}")
                # Try to continue anyway
                mod_family = ""

            # Parse omens
            omens_str = _parse_flag(parts, "--omens")
            active_omens = omens_str.split(",") if omens_str else []

            print(f"  {_DIM}Applying {resolved.essence_name} ({resolved.tier}){_RESET}")
            print(f"  {_DIM}  → family={mod_family}, stat={resolved.stat_text}{_RESET}")

            try:
                sim.apply_currency(
                    currency_key,
                    omens=active_omens if active_omens else None,
                    essence_family=mod_family,
                    essence_stat_text=resolved.stat_text,
                )
                item = sim.item
                _track(resolved.essence_name)
                for o in active_omens:
                    if o:
                        _track(o)
                history.append({
                    "action": f"essence:{ess_name}",
                    "currency": currency_key,
                    "essence_family": mod_family,
                    "omens": active_omens,
                })
                print()
                _print_item(item, base_name)
            except ValueError as e:
                print(f"  {_RED}Error: {e}{_RESET}")

        elif cmd == "socketables":
            # Show available socketables for this item with their effects
            from poe2_crafting_mcp.crafting.socketables import list_socketable_families
            families = list_socketable_families('data/poe2_craft.db', item_class)
            filter_text = " ".join(parts[1:]).lower() if len(parts) > 1 else ""
            
            if filter_text:
                families = [f for f in families if filter_text in f["display_name"].lower()
                           or filter_text in f["best_stat_text"].lower()]
            
            print(f"  {_BOLD}Socketables for {item_class}"
                  f"{' (filter: ' + filter_text + ')' if filter_text else ''}:{_RESET}")
            if not families:
                print(f"  {_DIM}No matches.{_RESET}")
            else:
                for f in families[:30]:  # limit display
                    tiers_str = f" ({f['tiers']} tiers)" if f['tiers'] > 1 else ""
                    print(f"    {f['display_name']:35} {f['best_stat_text']}{tiers_str}")
                if len(families) > 30:
                    print(f"  {_DIM}...and {len(families) - 30} more. Use a filter to narrow.{_RESET}")

        elif cmd == "export":
            # Export item as PoB text format
            from poe2_crafting_mcp.crafting.pob_export import item_state_to_pob_text, item_state_to_trade_text
            fmt = parts[1] if len(parts) > 1 else "pob"
            if fmt == "trade":
                text = item_state_to_trade_text(item, base_name)
            else:
                text = item_state_to_pob_text(item, base_name)
            print(f"\n{_DIM}{'─' * 50}{_RESET}")
            print(text)
            print(f"{_DIM}{'─' * 50}{_RESET}")
            # Also copy-friendly: print without ANSI
            if fmt == "pob":
                print(f"  {_DIM}(Paste this into PoB's item editor){_RESET}")

        elif cmd == "socket":
            # Socket an augment item (rune/soul core/idol)
            if len(parts) < 2:
                print(f"  {_RED}Usage: socket <item_name>{_RESET}")
                print(f"  {_DIM}Example: socket Body Rune{_RESET}")
                print(f"  {_DIM}Run 'socketables' to see available options with effects.{_RESET}")
                continue
            socketable_name = " ".join(parts[1:])
            # Find an empty socket slot to fill
            empty_idx = next((i for i, s in enumerate(item.sockets) if not s), None)
            if empty_idx is None:
                print(f"  {_RED}No empty sockets. All {len(item.sockets)} sockets are filled.{_RESET}")
                if len(item.sockets) < item.max_sockets:
                    print(f"  {_DIM}Use 'artificer' to add a new socket first.{_RESET}")
                continue
            # Resolve effect to validate and show what it does
            from poe2_crafting_mcp.crafting.socketables import get_socketable_effect_for_item
            family_key = socketable_name.replace(" ", "").replace("'", "")
            effect = get_socketable_effect_for_item('data/poe2_craft.db', item_class, family_key)
            if not effect:
                # Try stripping tier prefix
                for prefix in ("Lesser", "Greater"):
                    if family_key.startswith(prefix):
                        stripped = family_key[len(prefix):]
                        effect = get_socketable_effect_for_item('data/poe2_craft.db', item_class, stripped)
                        if effect:
                            break
            if not effect:
                print(f"  {_YELLOW}Warning: '{socketable_name}' not found in socketable DB for {item_class}.{_RESET}")
                print(f"  {_DIM}Socketing anyway (effect unknown). Run 'socketables' to browse.{_RESET}")
            
            item.sockets[empty_idx] = socketable_name
            _track(socketable_name)
            history.append({"action": f"socket:{socketable_name}", "omens": []})
            if effect:
                print(f"  {_GREEN}Socketed: {socketable_name} → {effect.stat_text}{_RESET}")
            else:
                print(f"  {_GREEN}Socketed: {socketable_name}{_RESET}")
            _print_item(item, base_name)

        elif cmd == "unsocket":
            # Remove a socketable by index or name
            if not any(s for s in item.sockets if s):
                print(f"  {_DIM}No socketed items to remove.{_RESET}")
                continue
            if len(parts) > 1:
                target = " ".join(parts[1:])
                for i, s in enumerate(item.sockets):
                    if s.lower() == target.lower():
                        item.sockets[i] = ""
                        print(f"  {_DIM}Removed: {target}{_RESET}")
                        break
                else:
                    print(f"  {_RED}'{target}' not found in sockets.{_RESET}")
            else:
                # Remove last socketed item
                for i in range(len(item.sockets) - 1, -1, -1):
                    if item.sockets[i]:
                        print(f"  {_DIM}Removed: {item.sockets[i]}{_RESET}")
                        item.sockets[i] = ""
                        break
            history.append({"action": "unsocket", "omens": []})
            _print_item(item, base_name)

        elif cmd == "artificer":
            # Add a socket via Artificer's Orb
            try:
                sim.apply_currency("artificer")
                item = sim.item
                _track("Artificer's Orb")
                history.append({"action": "artificer", "omens": []})
                print(f"  {_GREEN}Socket added ({len(item.sockets)}/{item.max_sockets}){_RESET}")
                _print_item(item, base_name)
            except ValueError as e:
                print(f"  {_RED}Error: {e}{_RESET}")

        elif cmd == "quality":
            # Apply quality currency
            slot_cat = get_bone_slot_for_item_class(item_class)
            if slot_cat == "weapon":
                cur_key = "blacksmiths_whetstone"
                track_name = "Blacksmith's Whetstone"
            else:
                cur_key = "armourers_scrap"
                track_name = "Armourer's Scrap"
            try:
                sim.apply_currency(cur_key)
                item = sim.item
                _track(track_name)
                history.append({"action": cur_key, "omens": []})
                print(f"  {_GREEN}Quality: {item.quality}%{_RESET}")
            except ValueError as e:
                print(f"  {_RED}Error: {e}{_RESET}")

        elif cmd == "desecrate":
            bone = parts[1] if len(parts) > 1 else "preserved_rib"
            omens_str = _parse_flag(parts, "--omens")
            active_omens = omens_str.split(",") if omens_str else []

            # Validate bone
            err = desecration.validate_bone(bone, item_class, ilvl)
            if err:
                print(f"  {_RED}{err}{_RESET}")
                continue

            # Apply bone (sets unrevealed state)
            try:
                item, affix_type = desecration.apply_bone(item, bone, omens=active_omens)
                sim.item = item
            except ValueError as e:
                print(f"  {_RED}Error: {e}{_RESET}")
                continue

            _track(bone)
            for o in active_omens:
                if o:
                    _track(o)
            history.append({"action": f"desecrate:{bone}", "omens": active_omens})
            print(f"  {_GREEN}Desecrated ({affix_type} slot reserved). Use 'reveal' at the Well of Souls.{_RESET}")
            print()
            _print_item(item, base_name)

        elif cmd == "reveal":
            # Reveal desecrated mod at the Well of Souls
            if not item.desecrated_unrevealed:
                print(f"  {_RED}No unrevealed desecrated mod. Use 'desecrate <bone>' first.{_RESET}")
                continue

            omens_str = _parse_flag(parts, "--omens")
            active_omens = omens_str.split(",") if omens_str else []

            affix_type = item.desecrated_affix_type
            # Use a generic bone for pool lookup (min_mod_level comes from bone quality used earlier)
            slot_cat = get_bone_slot_for_item_class(item_class)
            bone_for_pool = f"preserved_{slot_cat.replace('weapon','jawbone').replace('armour','rib').replace('jewellery','collarbone')}"
            if bone_for_pool not in BONES:
                bone_for_pool = "preserved_rib"

            pool = desecration.get_reveal_pool(item_class, ilvl, affix_type, bone_for_pool, item, omens=active_omens or None)
            if not pool:
                print(f"  {_RED}No mods available in reveal pool!{_RESET}")
                continue

            echoes = "abyssal_echoes" in active_omens
            n_draws = min(6 if echoes else 3, len(pool))
            options = _random.sample(pool, n_draws)

            # Show options
            print(f"\n  {_BOLD}Well of Souls — Revealed options ({affix_type}, pick 1-{n_draws}):{_RESET}")
            for i, opt in enumerate(options, 1):
                faction_tag = f" [{opt.faction}]" if opt.faction else ""
                print(f"    [{i}] {opt.affix_type:6} | {opt.family:28} | {opt.stat_text}{faction_tag}")

            if echoes:
                print(f"  {_DIM}(Abyssal Echoes: {n_draws} options shown){_RESET}")

            # Track echoes omen cost
            for o in active_omens:
                if o:
                    _track(o)

            # Get player choice
            while True:
                try:
                    choice_str = input(f"  {_CYAN}Pick (1-{n_draws}):{_RESET} ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                try:
                    choice_idx = int(choice_str) - 1
                    if 0 <= choice_idx < n_draws:
                        break
                except ValueError:
                    pass
                print(f"  {_RED}Enter a number 1-{n_draws}{_RESET}")

            chosen = options[choice_idx]
            mod = chosen.to_mod_instance(desecrated=True)
            mod.desecrated = True
            item.mods.append(mod)
            item.desecrated_unrevealed = False
            item.desecrated_affix_type = ""
            item.abyss_mark_min_level = 0  # reset after use
            sim.item = item

            history.append({
                "action": "reveal",
                "omens": active_omens,
                "affix_type": affix_type,
                "revealed": [{"family": o.family, "stat_text": o.stat_text} for o in options],
                "chose": choice_idx + 1,
            })
            print()
            _print_item(item, base_name)

        else:
            # Treat as currency application
            currency = cmd
            if currency not in CURRENCIES:
                print(f"  {_RED}Unknown command/currency: {currency}{_RESET}")
                print(f"  {_DIM}Available: {', '.join(sorted(CURRENCIES.keys()))}{_RESET}")
                continue

            omens_str = _parse_flag(parts, "--omens")
            active_omens = omens_str.split(",") if omens_str else []
            ess_family = _parse_flag(parts, "--essence_family") or _parse_flag(parts, "--family") or ""
            ess_stat = _parse_flag(parts, "--stat_text") or ""

            # Validate omens
            bad_omens = [o for o in active_omens if o and o not in OMENS]
            if bad_omens:
                print(f"  {_RED}Unknown omen(s): {bad_omens}{_RESET}")
                continue

            try:
                sim.apply_currency(
                    currency,
                    omens=active_omens if active_omens else None,
                    essence_family=ess_family,
                    essence_stat_text=ess_stat,
                )
                item = sim.item
                _track(currency)
                for o in active_omens:
                    if o:
                        _track(o)
                history.append({
                    "action": currency,
                    "omens": active_omens,
                    "essence_family": ess_family or None,
                })
                print()
                _print_item(item, base_name)
            except ValueError as e:
                print(f"  {_RED}Error: {e}{_RESET}")

    return 0


def _print_item(item: ItemState, base_name: str) -> None:
    """Pretty-print current item state."""
    corrupt_str = "  [CORRUPTED]" if item.corrupted else ""
    quality_str = f"  Q{item.quality}%" if item.quality > 0 else ""
    print(f"  {_BOLD}{base_name}{_RESET} ({item.rarity}, ilvl {item.ilvl}){quality_str}{corrupt_str}")
    # Implicits (corruption implicits, base implicits)
    if item.implicits:
        for m in item.implicits:
            print(f"    {_DIM}implicit{_RESET} | {m.family:25} | {m.display_text} {_DIM}[implicit]{_RESET}")
    if not item.mods:
        print(f"  {_DIM}(no mods){_RESET}")
    else:
        for m in item.mods:
            markers = []
            if m.fractured:
                markers.append(f"{_YELLOW}[F]{_RESET}")
            if m.desecrated:
                markers.append(f"{_CYAN}[D]{_RESET}")
            if item.essence_mod_family and m.family == item.essence_mod_family:
                markers.append(f"{_GREEN}[E]{_RESET}")
            mark_str = " ".join(markers)
            if mark_str:
                mark_str = " " + mark_str
            print(f"    {m.affix_type:6} T{m.tier} | {m.family:25} | {m.display_text}{mark_str}")
    # Sockets
    socket_filled = [s for s in item.sockets if s]
    socket_empty = len(item.sockets) - len(socket_filled)
    socket_info = f"Sockets: {len(item.sockets)}/{item.max_sockets}"
    if socket_empty > 0:
        socket_info += f" ({socket_empty} empty)"
    # Desecrated unrevealed indicator
    desecrate_info = ""
    if item.desecrated_unrevealed:
        desecrate_info = f" | {_CYAN}⚗ Unrevealed {item.desecrated_affix_type} desecration{_RESET}"
    print(f"  {_DIM}Slots: {item.open_prefixes}P / {item.open_suffixes}S open | {socket_info}{desecrate_info}{_RESET}")
    if socket_filled:
        from poe2_crafting_mcp.crafting.socketables import get_socketable_effect_for_item
        for s in socket_filled:
            family_key = s.replace(" ", "").replace("'", "")
            effect = get_socketable_effect_for_item('data/poe2_craft.db', item.item_class, family_key)
            if not effect:
                for prefix in ("Lesser", "Greater"):
                    if family_key.startswith(prefix):
                        effect = get_socketable_effect_for_item('data/poe2_craft.db', item.item_class, family_key[len(prefix):])
                        if effect:
                            break
            effect_text = f" → {effect.stat_text}" if effect else ""
            print(f"    {_DIM}⬡{_RESET} {s}{effect_text}")


def _serialize_item(
    item: ItemState, base_name: str, item_class: str, ilvl: int, history: list[dict]
) -> dict:
    """Serialize item state to JSON-compatible dict."""
    return {
        "base_name": base_name,
        "item_class": item_class,
        "ilvl": ilvl,
        "rarity": item.rarity,
        "corrupted": item.corrupted,
        "essence_mod_family": item.essence_mod_family,
        "mods": [
            {
                "family": m.family,
                "affix_type": m.affix_type,
                "tier": m.tier,
                "req_level": m.req_level,
                "weight": m.weight,
                "stat_text": m.stat_text,
                "fractured": m.fractured,
                "desecrated": m.desecrated,
            }
            for m in item.mods
        ],
        "quality": item.quality,
        "sockets": item.sockets,
        "max_sockets": item.max_sockets,
        "implicits": [
            {
                "family": m.family,
                "affix_type": m.affix_type,
                "tier": m.tier,
                "req_level": m.req_level,
                "weight": m.weight,
                "stat_text": m.stat_text,
            }
            for m in item.implicits
        ],
        "history": history,
    }


def _resolve_item_class(pdb, base_name: str) -> str | None:
    """Resolve a base name or item class to poe2db item_class slug."""
    import sqlite3
    # Direct match (user typed item_class directly)
    count = pdb._conn.execute(
        "SELECT COUNT(*) FROM mod_weights WHERE item_class = ?", (base_name,)
    ).fetchone()[0]
    if count > 0:
        return base_name

    # Search item_bases for the name
    try:
        row = pdb._conn.execute(
            "SELECT tags, slot FROM item_bases WHERE name = ? COLLATE NOCASE LIMIT 1",
            (base_name,)
        ).fetchone()
    except Exception:
        row = None

    if not row:
        # Fuzzy search
        try:
            row = pdb._conn.execute(
                "SELECT tags, slot FROM item_bases WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (f"%{base_name}%",)
            ).fetchone()
        except Exception:
            return None

    if not row:
        return None

    import json as _json
    tags = _json.loads(row["tags"]) if row["tags"] else []
    slot = row["slot"] or ""

    # Mapping logic from crafting_advisor_design.md
    attr_map = {
        "int_armour": "_int", "str_armour": "_str", "dex_armour": "_dex",
        "str_dex_armour": "_str_dex", "str_int_armour": "_str_int",
        "dex_int_armour": "_dex_int", "str_dex_int_armour": "_str_dex_int",
    }
    slot_map = {
        "Gloves": "Gloves", "Boots": "Boots", "Helmet": "Helmets",
        "Body Armour": "Body_Armours", "Shield": "Shields",
        "Focus": "Foci", "Bow": "Bows", "Crossbow": "Crossbows",
        "Dagger": "Daggers", "Claw": "Claws", "Flail": "Flails",
        "Spear": "Spears", "Quarterstaff": "Quarterstaves",
        "One Hand Sword": "One_Hand_Swords", "Two Hand Sword": "Two_Hand_Swords",
        "One Hand Axe": "One_Hand_Axes", "Two Hand Axe": "Two_Hand_Axes",
        "One Hand Mace": "One_Hand_Maces", "Two Hand Mace": "Two_Hand_Maces",
        "Sceptre": "Sceptres", "Wand": "Wands", "Staff": "Staves",
        "Ring": "Rings", "Amulet": "Amulets", "Belt": "Belts",
        "Quiver": "Quivers", "Talisman": "Talismans",
    }

    base_slug = slot_map.get(slot, slot)
    attr_suffix = ""
    for tag in tags:
        if tag in attr_map:
            attr_suffix = attr_map[tag]
            break

    item_class = base_slug + attr_suffix

    # Verify it exists
    count = pdb._conn.execute(
        "SELECT COUNT(*) FROM mod_weights WHERE item_class = ?", (item_class,)
    ).fetchone()[0]
    return item_class if count > 0 else None


def _parse_flag(parts: list[str], flag: str) -> str:
    """Extract --flag value from parts list."""
    for i, p in enumerate(parts):
        if p == flag and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _item_class_to_slot(item_class: str) -> str:
    """Convert poe2db item_class back to a slot name for EssenceResolver."""
    # Strip attribute suffixes
    slot_base = item_class.split("_")[0] if "_" in item_class else item_class

    # Map poe2db class prefixes back to slot names
    class_to_slot = {
        "Gloves": "Gloves", "Boots": "Boots", "Helmets": "Helmet",
        "Body": "Body Armour", "Shields": "Shield", "Bucklers": "Shield",
        "Foci": "Focus", "Bows": "Bow", "Crossbows": "Crossbow",
        "Daggers": "Dagger", "Claws": "Claw", "Flails": "Flail",
        "Spears": "Spear", "Quarterstaves": "Quarterstaff",
        "One": "One Hand Sword",  # will need context
        "Two": "Two Hand Sword",  # will need context
        "Sceptres": "Sceptre", "Wands": "Wand", "Staves": "Staff",
        "Rings": "Ring", "Amulets": "Amulet", "Belts": "Belt",
        "Quivers": "Quiver", "Talismans": "Talisman", "Traps": "Trap",
    }

    # Direct full matches first
    full_matches = {
        "Bows": "Bow", "Crossbows": "Crossbow", "Daggers": "Dagger",
        "Claws": "Claw", "Flails": "Flail", "Spears": "Spear",
        "Quarterstaves": "Quarterstaff", "Sceptres": "Sceptre",
        "Wands": "Wand", "Staves": "Staff", "Rings": "Ring",
        "Amulets": "Amulet", "Belts": "Belt", "Quivers": "Quiver",
        "Talismans": "Talisman", "Traps": "Trap", "Foci": "Focus",
        "Bucklers": "Shield",
        "One_Hand_Swords": "One Hand Sword", "Two_Hand_Swords": "Two Hand Sword",
        "One_Hand_Axes": "One Hand Axe", "Two_Hand_Axes": "Two Hand Axe",
        "One_Hand_Maces": "One Hand Mace", "Two_Hand_Maces": "Two Hand Mace",
    }
    if item_class in full_matches:
        return full_matches[item_class]

    # Prefix-based matching for armour with attribute suffixes
    for prefix, slot in [
        ("Body_Armours", "Body Armour"), ("Boots", "Boots"),
        ("Gloves", "Gloves"), ("Helmets", "Helmet"),
        ("Shields", "Shield"),
    ]:
        if item_class.startswith(prefix):
            return slot

    return item_class  # fallback


def _resolve_essence_family(pdb, stat_text: str, item_class: str) -> str:
    """Resolve essence stat_text to mod_family by joining with mod_weights."""
    row = pdb._conn.execute(
        "SELECT mod_family FROM mod_weights "
        "WHERE stat_text = ? AND pool IN ('essence', 'perfect_essence') "
        "AND item_class = ? LIMIT 1",
        (stat_text, item_class),
    ).fetchone()
    if row:
        return row[0]
    # Fallback: search across all item classes
    row = pdb._conn.execute(
        "SELECT mod_family FROM mod_weights "
        "WHERE stat_text = ? AND pool IN ('essence', 'perfect_essence') LIMIT 1",
        (stat_text,),
    ).fetchone()
    return row[0] if row else ""


def _sim_help() -> None:
    print(f"""
  {_BOLD}Crafting Commands:{_RESET}
    <currency>                       Apply currency (e.g. transmute, exalted, chaos)
    <currency> --omens x,y           Apply with stacked omens
    essence <name>                   Apply essence by name (auto-resolves family/tier)
    essence <name> --omens x         With omen (e.g. sinistral_crystallisation)
    desecrate <bone>                 Apply bone (e.g. preserved_rib, ancient_jawbone)
    desecrate <bone> --omens x       With omen (e.g. blackblooded, abyssal_echoes)

  {_BOLD}Discovery Commands:{_RESET}
    currencies                       Show valid currencies for current item state
    essences [tier]                  Show available essences (e.g. 'essences Greater')
    omens <currency>                 Show omens that apply to a currency
    bones                            Show valid bones for this item
    pool [prefix|suffix]             Show available mod pool with weights

  {_BOLD}Item Management:{_RESET}
    save <file.json>                 Save current item state + history
    load <file.json>                 Load item state from file
    history                          Show crafting history

  {_BOLD}Other:{_RESET}
    help                             Show this help
    quit                             Exit

  {_BOLD}Examples:{_RESET}
    > transmute
    > essence Greater Essence of the Body
    > exalted --omens dextral_exaltation,greater_exaltation
    > desecrate preserved_rib --omens blackblooded
    > omens exalted
    > essences Perfect
    > save my_craft.json
""")


# ── Help ──────────────────────────────────────────────────────────────────────

HELP_TEXT = f"""{_BOLD}poe2-craft{_RESET} — PoE2 crafting data manager & simulator

{_BOLD}Commands:{_RESET}
  {_CYAN}status{_RESET}           Check all data sources and current league
  {_CYAN}seed{_RESET}             Seed stale/missing data in correct order
  {_CYAN}seed --force{_RESET}     Re-seed all data sources
  {_CYAN}seed --only X{_RESET}    Seed only: etl, mod_weights, essences, concepts, item_descriptions, prices
  {_CYAN}sim{_RESET} <base>       Interactive crafting simulator (step-by-step)
  {_CYAN}sim --load{_RESET} F     Load saved item state and continue crafting
  {_CYAN}mcp{_RESET}              Start the MCP server (stdio transport)

{_BOLD}Sim examples:{_RESET}
  poe2-craft sim "Gold Gloves" --ilvl 82
  poe2-craft sim Bows --ilvl 82 --seed 42
  poe2-craft sim --load my_item.json

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
    elif cmd == "sim":
        sys.exit(cmd_sim(rest))
    elif cmd == "mcp":
        from poe2_crafting_mcp.server import main as mcp_main
        mcp_main()
    else:
        print(f"{_RED}Unknown command: {cmd}{_RESET}")
        print(f"Run {_BOLD}poe2-craft --help{_RESET} for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
