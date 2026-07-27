"""
poe2-lookup — unified search across all PoE2 game data.

Usage:
    poe2-lookup <query>
    poe2-lookup <query> --type bases|mods|gems|uniques|nodes|currencies
    poe2-lookup <query> --limit 20

Examples:
    poe2-lookup "storm wave"
    poe2-lookup "critical strike" --type nodes
    poe2-lookup "lightning damage" --type mods --tag staff
    poe2-lookup "rage" --type uniques
    poe2-lookup "chaos orb" --type currencies
    poe2-lookup "energy shield" --type bases --slot Gloves

    poe2-lookup status                                # show all DB health
    poe2-lookup seed-all                              # ETL + concepts + item-desc

    poe2-lookup concept-status                        # concept DB freshness
    poe2-lookup concept-list [--category mechanic]    # list all concepts
    poe2-lookup concept-search "shock"                # search by keyword
    poe2-lookup concept-get "Iron Reflexes"           # full definition
    poe2-lookup concept-add "Name" --category mechanic --summary "..." --mechanics "..."
    poe2-lookup concept-delete "Name"
    poe2-lookup concept-refresh                       # re-seed from built-ins

    poe2-lookup item-desc-status                      # item descriptions DB freshness
    poe2-lookup item-desc-list [--category base]      # list all item descriptions
    poe2-lookup item-desc-get "Gold Gloves"           # full description
    poe2-lookup item-desc-add "Name" --category base --description "..." --crafting-notes "..."
    poe2-lookup item-desc-delete "Name"
    poe2-lookup item-desc-refresh                     # re-seed from built-ins
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

_RARITY_COLOR = {
    "Normal": _RESET,
    "Magic":  _BLUE,
    "Rare":   _YELLOW,
    "Unique": _PURPLE,
}

def _h(text: str) -> str:
    return f"{_BOLD}{_YELLOW}── {text} {'─'*(48-len(text))}{_RESET}"


def _tag(text: str, color: str = _DIM) -> str:
    return f"{color}[{text}]{_RESET}"


def _no_results(section: str) -> None:
    print(f"  {_DIM}(no {section} found){_RESET}")


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_base(b: dict, desc: dict | None = None) -> None:
    defence = []
    if b.get("armour"):        defence.append(f"AR {b['armour']}")
    if b.get("evasion"):       defence.append(f"EV {b['evasion']}")
    if b.get("energy_shield"): defence.append(f"ES {b['energy_shield']}")
    if b.get("ward"):          defence.append(f"WA {b['ward']}")
    defence_str = "  ".join(defence) if defence else "—"
    reqs = []
    if b.get("req_str"): reqs.append(f"S{b['req_str']}")
    if b.get("req_dex"): reqs.append(f"D{b['req_dex']}")
    if b.get("req_int"): reqs.append(f"I{b['req_int']}")
    req_str = " ".join(reqs) if reqs else "—"
    sub = f"  {_DIM}{b.get('sub_type','')}{_RESET}" if b.get("sub_type") else ""
    print(f"  {_BOLD}{b['name']}{_RESET}{sub}")
    print(f"    {_DIM}Slot:{_RESET} {b.get('slot','')}  "
          f"{_DIM}iLvl req:{_RESET} {b.get('req_level',0)}  "
          f"{_DIM}Req:{_RESET} {req_str}  "
          f"{_DIM}Sockets:{_RESET} {b.get('socket_limit',0)}")
    print(f"    {_DIM}Defence:{_RESET} {defence_str}")
    tags = b.get("tags") or []
    if isinstance(tags, list) and tags:
        print(f"    {_DIM}Tags:{_RESET} {', '.join(t for t in tags if t)}")
    if desc:
        if desc.get("description"):
            print(f"    {_CYAN}{desc['description']}{_RESET}")
        if desc.get("crafting_notes"):
            print(f"    {_DIM}Crafting:{_RESET} {desc['crafting_notes']}")


def _with_tiers(mods: list[dict]) -> list[dict]:
    """
    Add a 'tier' field to each mod — T1 = highest req_level within its group_name.

    Assumes mods are ordered by (group_name, req_level DESC), which is what
    PoBDatabase.expand_mod_tiers() returns.
    """
    group_count: dict[str, int] = {}
    result = []
    for m in mods:
        gn = m.get("group_name") or ""
        group_count[gn] = group_count.get(gn, 0) + 1
        result.append({**m, "tier": group_count[gn]})
    return result


def _fmt_mod(m: dict) -> None:
    mt = m.get("mod_type", "")
    cat = m.get("category", "")
    color = _CYAN if mt == "Prefix" else _GREEN
    label = f"{color}{mt}{_RESET}" if mt else ""
    cat_label = f"  {_DIM}{cat}{_RESET}" if cat and cat != "Item" else ""
    affix = f"  {_DIM}«{m['affix']}»{_RESET}" if m.get("affix") else ""
    tier_label = f"  {_YELLOW}T{m['tier']}{_RESET}" if m.get("tier") else ""
    print(f"  {label}{cat_label}{affix}{tier_label}")
    print(f"    {_BOLD}{m.get('stat_text','')}{_RESET}")
    mn, mx = m.get("stat_min"), m.get("stat_max")
    range_str = ""
    if mn is not None and mx is not None and mn != mx:
        range_str = f"  {_DIM}range: {mn}–{mx}{_RESET}"
    group = f"  {_DIM}group: {m['group_name']}{_RESET}" if m.get("group_name") else ""
    print(f"    {_DIM}ilvl:{_RESET} {m.get('req_level',0)}{range_str}{group}")
    wkeys = m.get("weight_keys") or []
    if isinstance(wkeys, list):
        # show only keys with non-zero weight
        wvals = m.get("weight_vals") or []
        applicable = [wkeys[i] for i in range(len(wkeys))
                      if i < len(wvals) and wkeys[i] != "default"
                      and int(float(wvals[i])) > 0]
        if applicable:
            print(f"    {_DIM}Rolls on:{_RESET} {', '.join(applicable[:10])}")


def _fmt_gem(g: dict) -> None:
    support_tag = _tag("Support", _BLUE) if g.get("is_support") else _tag("Active", _GREEN)
    tier = f"  {_DIM}T{g.get('tier',0)}{_RESET}" if g.get("tier") else ""
    gem_type = f"  {_DIM}{g.get('gem_type','')}{_RESET}" if g.get("gem_type") else ""
    print(f"  {_BOLD}{g['name']}{_RESET}  {support_tag}{gem_type}{tier}")
    reqs = []
    if g.get("req_str"): reqs.append(f"S{g['req_str']}")
    if g.get("req_dex"): reqs.append(f"D{g['req_dex']}")
    if g.get("req_int"): reqs.append(f"I{g['req_int']}")
    req_str = " / ".join(reqs) if reqs else "—"
    print(f"    {_DIM}Req:{_RESET} {req_str}  "
          f"{_DIM}MaxLvl:{_RESET} {g.get('natural_max_level',20)}")
    tag_string = g.get("tag_string") or ""
    if tag_string:
        print(f"    {_DIM}Tags:{_RESET} {tag_string}")
    weap = g.get("weapon_requirements") or ""
    if weap:
        print(f"    {_DIM}Weapon:{_RESET} {weap}")


def _fmt_unique(u: dict) -> None:
    print(f"  {_PURPLE}{_BOLD}{u['name']}{_RESET}  {_DIM}{u.get('base_type','')}{_RESET}")
    if u.get("source"):
        print(f"    {_DIM}Source:{_RESET} {u['source']}")
    variants = u.get("variants") or []
    if isinstance(variants, list) and variants:
        shown = variants[:5]
        more = len(variants) - len(shown)
        suffix = f"  {_DIM}+{more} more{_RESET}" if more else ""
        print(f"    {_DIM}Variants:{_RESET} {', '.join(shown)}{suffix}")
    # Show first 8 lines of raw text (skip name + base type header)
    raw = u.get("raw_text") or ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()][2:10]
    for ln in lines:
        if any(ln.startswith(p) for p in ("Variant:", "League:", "Source:", "Implicits:")):
            continue
        if ln.startswith("{variant"):
            ln = ln.split("}", 1)[-1]
        print(f"    {ln}")


def _fmt_node(n: dict) -> None:
    type_colors = {
        "Keystone":    _RED,
        "Notable":     _YELLOW,
        "Normal":      _DIM,
        "JewelSocket": _PURPLE,
        "ClassStart":  _CYAN,
    }
    ntype = n.get("node_type", "Normal")
    color = type_colors.get(ntype, _DIM)
    asc = f"  {_CYAN}[{n['ascendancy']}]{_RESET}" if n.get("ascendancy") else ""
    print(f"  {color}{_BOLD}{n.get('name') or '(unnamed)'}{_RESET}  "
          f"{_DIM}{ntype}{_RESET}  {_DIM}#{n['node_id']}{_RESET}{asc}")
    stats = n.get("stats") or []
    if isinstance(stats, list):
        for s in stats[:6]:
            print(f"    {s}")
    if len(stats) > 6:
        print(f"    {_DIM}… +{len(stats)-6} more{_RESET}")


def _fmt_concept(c: dict) -> None:
    cat = f"  {_DIM}[{c.get('category','')}]{_RESET}"
    src = f" {_DIM}{c.get('source','')}{_RESET}" if c.get("source") and c["source"] != "manual" else ""
    print(f"  {_BOLD}{c['name']}{_RESET}{cat}{src}")
    print(f"    {c.get('summary','')}")
    mechanics = c.get("mechanics", "").strip()
    if mechanics:
        for line in mechanics.split(". "):
            line = line.strip()
            if line:
                print(f"    {_DIM}{line.rstrip('.')}.{_RESET}")
    formula = c.get("formula", "").strip()
    if formula:
        print(f"    {_CYAN}Formula:{_RESET} {formula}")
    see_also = c.get("see_also") or []
    if see_also:
        print(f"    {_DIM}See also:{_RESET} {', '.join(see_also[:8])}")


def _fmt_currency(c: dict) -> None:
    cat = f"  {_DIM}[{c.get('category','')}]{_RESET}"
    sub = f"  {_DIM}{c.get('subcategory','')}{_RESET}" if c.get("subcategory") else ""
    print(f"  {_BOLD}{c['name']}{_RESET}{cat}{sub}")
    if c.get("effect"):
        print(f"    {c['effect']}")


def _fmt_exchange(e: dict) -> None:
    cat = f"  {_DIM}[{e.get('category','')}]{_RESET}"
    print(f"  {_BOLD}{e['name']}{_RESET}{cat}")
    desc = e.get("description", "")
    if desc:
        print(f"    {desc}")


# ── Concept subcommands ───────────────────────────────────────────────────────

def _get_pdb():
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    return PriceDatabase()


def _cmd_concept_status(argv: list[str]) -> int:
    cs = _get_pdb().concept_status()
    status = cs.get("status", "unknown")
    icons = {
        "fresh":        f"{_GREEN}✓ fresh{_RESET}",
        "stale":        f"{_YELLOW}⚠ stale (>30 days){_RESET}",
        "never_seeded": f"{_RED}✗ never seeded{_RESET}",
    }
    print(_h("Concepts Status"))
    print(f"  {_BOLD}Status:{_RESET}  {icons.get(status, status)}")
    print(f"  {_BOLD}Total:{_RESET}   {cs.get('total', 0)}")
    manual = cs.get("manual", 0)
    if manual:
        print(f"  {_DIM}  manual entries:{_RESET} {manual}")
    seeded_at = cs.get("seeded_at")
    age_days = cs.get("age_days")
    if seeded_at:
        age_str = f"  {_DIM}({age_days:.1f} days ago){_RESET}" if age_days is not None else ""
        print(f"  {_BOLD}Seeded:{_RESET}  {seeded_at}{age_str}")
    if status != "fresh":
        print(f"\n  {_YELLOW}→ Run: poe2-lookup concept-refresh{_RESET}")
    return 0


def _cmd_concept_list(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup concept-list")
    p.add_argument("--category", "-c", default="")
    p.add_argument("--limit", "-l", type=int, default=50)
    args = p.parse_args(argv)
    pdb = _get_pdb()
    results = pdb.search_concepts(keyword="", category=args.category, limit=args.limit)
    if not results:
        print(f"{_DIM}No concepts found.{_RESET}")
        return 0
    label = f"Concepts — {args.category}" if args.category else f"Concepts ({len(results)})"
    print(_h(label))
    for c in results:
        src = f" {_DIM}{c.get('source','')}{_RESET}" if c.get("source") and c["source"] != "manual" else ""
        print(f"  {_BOLD}{_CYAN}{c['name']}{_RESET}  {_DIM}[{c['category']}]{_RESET}{src}")
        if c.get("summary"):
            print(f"    {c['summary']}")
    return 0


def _cmd_concept_search(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup concept-search")
    p.add_argument("keyword", nargs="+")
    p.add_argument("--category", "-c", default="")
    p.add_argument("--limit", "-l", type=int, default=10)
    args = p.parse_args(argv)
    keyword = " ".join(args.keyword)
    pdb = _get_pdb()
    results = pdb.search_concepts(keyword=keyword, category=args.category, limit=args.limit)
    if not results:
        print(f"{_DIM}No concepts matching '{keyword}'.{_RESET}")
        return 0
    print(_h(f"Concepts: '{keyword}' ({len(results)})"))
    for c in results:
        _fmt_concept(c)
        print()
    return 0


def _cmd_concept_get(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup concept-get")
    p.add_argument("name", nargs="+")
    args = p.parse_args(argv)
    name = " ".join(args.name)
    c = _get_pdb().get_concept(name)
    if not c:
        print(f"{_RED}Concept '{name}' not found.{_RESET}", file=sys.stderr)
        return 1
    print(_h(c["name"]))
    print(f"  {_BOLD}Category:{_RESET}  {c['category']}")
    print(f"  {_BOLD}Source:{_RESET}    {c.get('source', 'manual')}")
    lv = c.get("league_version")
    if lv:
        print(f"  {_BOLD}League:{_RESET}    {lv}")
    if c.get("summary"):
        print(f"\n  {_BOLD}Summary:{_RESET}\n    {c['summary']}")
    if c.get("mechanics"):
        print(f"\n  {_BOLD}Mechanics:{_RESET}")
        for line in c["mechanics"].splitlines():
            print(f"    {line}")
    if c.get("formula"):
        print(f"\n  {_BOLD}Formula:{_RESET}\n    {_CYAN}{c['formula']}{_RESET}")
    see_also = c.get("see_also") or []
    if see_also:
        print(f"\n  {_BOLD}See also:{_RESET}  {', '.join(see_also)}")
    print(f"\n  {_DIM}Updated: {c.get('updated_at', '?')}{_RESET}")
    return 0


def _cmd_concept_add(argv: list[str]) -> int:
    import json as _json
    p = argparse.ArgumentParser(prog="poe2-lookup concept-add")
    p.add_argument("name", nargs="+")
    p.add_argument("--category", "-c", required=True)
    p.add_argument("--summary", default="")
    p.add_argument("--mechanics", default="")
    p.add_argument("--formula", default="")
    p.add_argument("--see-also", default="")
    p.add_argument("--source", default="manual")
    p.add_argument("--league", default="")
    args = p.parse_args(argv)
    name = " ".join(args.name)
    try:
        see_also = _json.loads(args.see_also) if args.see_also else []
    except ValueError:
        see_also = [s.strip() for s in args.see_also.split(",") if s.strip()]
    _get_pdb().upsert_concept(
        name=name, category=args.category, summary=args.summary,
        mechanics=args.mechanics, formula=args.formula, see_also=see_also,
        source=args.source, league_version=args.league or None,
    )
    print(f"{_GREEN}✓ Concept '{name}' saved.{_RESET}")
    return 0


def _cmd_concept_delete(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup concept-delete")
    p.add_argument("name", nargs="+")
    args = p.parse_args(argv)
    name = " ".join(args.name)
    if _get_pdb().delete_concept(name):
        print(f"{_GREEN}✓ Deleted '{name}'.{_RESET}")
        return 0
    print(f"{_RED}Concept '{name}' not found.{_RESET}", file=sys.stderr)
    return 1


def _cmd_concept_refresh(argv: list[str]) -> int:
    from poe2_crafting_mcp.data.concepts import CONCEPTS
    pdb = _get_pdb()
    # overwrite=False preserves wiki-sourced entries; only fills missing / manual
    n = pdb.upsert_concepts_bulk(CONCEPTS, overwrite=False)
    cs = pdb.concept_status()
    print(f"{_GREEN}✓ Re-seeded {n} built-in concepts (wiki-sourced entries preserved).{_RESET}")
    print(f"  {_BOLD}Total in DB:{_RESET} {cs.get('total', 0)}")
    return 0


def _cmd_concept_seed(argv: list[str]) -> int:
    """Fetch concept data from poe2wiki.net for all concepts in the DB.

    Concepts with source='manual' are preserved (manual overrides).
    All others are updated from wiki body prose / status infobox data.
    """
    p = argparse.ArgumentParser(prog="poe2-lookup concept-seed")
    p.add_argument("--dry-run", action="store_true", help="Show what would be seeded without writing")
    args = p.parse_args(argv)

    from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
    pdb = _get_pdb()
    wiki = Poe2WikiClient()

    if args.dry_run:
        rows = pdb.search_concepts(keyword='', limit=10000)
        print(f"{_BOLD}Would seed {len(rows)} concepts from poe2wiki.net{_RESET}")
        print(f"  (wiki data overwrites manual entries; concepts not on wiki are unchanged)")
        return 0

    print(f"{_DIM}Fetching concepts from poe2wiki.net…{_RESET}", flush=True)
    fetched, skipped = wiki.seed_concepts_from_db(pdb)
    # Rebuild FTS after bulk updates
    try:
        pdb._conn.execute("INSERT INTO concepts_fts(concepts_fts) VALUES('rebuild')")
        pdb._conn.commit()
    except Exception:
        pass
    total = pdb.concept_status().get('total', 0)
    print(f"{_GREEN}✓ Wiki seeded {fetched} concepts ({skipped} skipped/manual).{_RESET}")
    print(f"  {_BOLD}Total in DB:{_RESET} {total}")
    return 0


_CONCEPT_CMDS = {
    "concept-status":  _cmd_concept_status,
    "concept-list":    _cmd_concept_list,
    "concept-search":  _cmd_concept_search,
    "concept-get":     _cmd_concept_get,
    "concept-add":     _cmd_concept_add,
    "concept-delete":  _cmd_concept_delete,
    "concept-refresh": _cmd_concept_refresh,
    "concept-seed":    _cmd_concept_seed,
}


# ── Item description subcommands ──────────────────────────────────────────────

def _fmt_item_desc(d: dict, compact: bool = False) -> None:
    cat = f"  {_DIM}[{d.get('category','')}]{_RESET}"
    src = f" {_DIM}{d.get('source','')}{_RESET}" if d.get("source") and d["source"] != "manual" else ""
    print(f"  {_BOLD}{_CYAN}{d['name']}{_RESET}{cat}{src}")
    if d.get("description"):
        print(f"    {d['description']}")
    if not compact:
        if d.get("crafting_notes"):
            print(f"    {_BOLD}Crafting:{_RESET} {d['crafting_notes']}")
        if d.get("drop_notes"):
            print(f"    {_DIM}Drops:{_RESET} {d['drop_notes']}")
        see_also = d.get("see_also") or []
        if see_also:
            print(f"    {_DIM}See also:{_RESET} {', '.join(see_also[:8])}")


def _cmd_item_desc_status(argv: list[str]) -> int:
    ds = _get_pdb().item_desc_status()
    status = ds.get("status", "unknown")
    icons = {
        "fresh":        f"{_GREEN}✓ fresh{_RESET}",
        "stale":        f"{_YELLOW}⚠ stale (>30 days){_RESET}",
        "never_seeded": f"{_RED}✗ never seeded{_RESET}",
    }
    print(_h("Item Descriptions Status"))
    print(f"  {_BOLD}Status:{_RESET}  {icons.get(status, status)}")
    print(f"  {_BOLD}Total:{_RESET}   {ds.get('total', 0)}")
    seeded_at = ds.get("seeded_at")
    age_days = ds.get("age_days")
    if seeded_at:
        age_str = f"  {_DIM}({age_days:.1f} days ago){_RESET}" if age_days is not None else ""
        print(f"  {_BOLD}Seeded:{_RESET}  {seeded_at}{age_str}")
    if status != "fresh":
        print(f"\n  {_YELLOW}→ Run: poe2-lookup item-desc-refresh{_RESET}")
    return 0


def _cmd_item_desc_list(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup item-desc-list")
    p.add_argument("--category", "-c", default="")
    p.add_argument("--limit", "-l", type=int, default=50)
    args = p.parse_args(argv)
    pdb = _get_pdb()
    results = pdb.search_item_descs(keyword="", category=args.category, limit=args.limit)
    if not results:
        print(f"{_DIM}No item descriptions found.{_RESET}")
        return 0
    label = f"Item Descriptions — {args.category}" if args.category else f"Item Descriptions ({len(results)})"
    print(_h(label))
    for d in results:
        _fmt_item_desc(d, compact=True)
    return 0


def _cmd_item_desc_get(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup item-desc-get")
    p.add_argument("name", nargs="+")
    p.add_argument("--no-fetch", action="store_true",
                   help="skip wiki fetch on cache miss")
    args = p.parse_args(argv)
    name = " ".join(args.name)
    pdb = _get_pdb()
    if args.no_fetch:
        d = pdb.get_item_desc(name)
    else:
        from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
        wiki = Poe2WikiClient()
        d = pdb.get_item_desc_or_fetch(name, wiki_client=wiki)
    if not d:
        print(f"{_RED}No description for '{name}' (not in cache or wiki).{_RESET}",
              file=sys.stderr)
        return 1
    print(_h(d["name"]))
    print(f"  {_BOLD}Category:{_RESET} {d['category']}")
    print(f"  {_BOLD}Source:{_RESET}   {d.get('source', 'manual')}")
    lv = d.get("league_version")
    if lv:
        print(f"  {_BOLD}League:{_RESET}   {lv}")
    if d.get("description"):
        print(f"\n  {_BOLD}Description:{_RESET}\n    {d['description']}")
    if d.get("crafting_notes"):
        print(f"\n  {_BOLD}Crafting Notes:{_RESET}")
        for line in d["crafting_notes"].splitlines():
            print(f"    {line}")
    if d.get("drop_notes"):
        print(f"\n  {_BOLD}Drop Notes:{_RESET}\n    {d['drop_notes']}")
    see_also = d.get("see_also") or []
    if see_also:
        print(f"\n  {_BOLD}See also:{_RESET}  {', '.join(see_also)}")
    print(f"\n  {_DIM}Updated: {d.get('updated_at', '?')}{_RESET}")
    return 0


def _cmd_item_desc_add(argv: list[str]) -> int:
    import json as _json
    p = argparse.ArgumentParser(prog="poe2-lookup item-desc-add")
    p.add_argument("name", nargs="+")
    p.add_argument("--category", "-c", required=True,
                   choices=["base", "currency", "gem", "unique", "mechanic_item"])
    p.add_argument("--description", default="")
    p.add_argument("--crafting-notes", default="")
    p.add_argument("--drop-notes", default="")
    p.add_argument("--see-also", default="")
    p.add_argument("--source", default="manual")
    p.add_argument("--league", default="")
    args = p.parse_args(argv)
    name = " ".join(args.name)
    try:
        see_also = _json.loads(args.see_also) if args.see_also else []
    except ValueError:
        see_also = [s.strip() for s in args.see_also.split(",") if s.strip()]
    _get_pdb().upsert_item_desc(
        name=name, category=args.category,
        description=args.description,
        crafting_notes=args.crafting_notes,
        drop_notes=args.drop_notes,
        see_also=see_also,
        source=args.source,
        league_version=args.league or None,
    )
    print(f"{_GREEN}✓ Item description '{name}' saved.{_RESET}")
    return 0


def _cmd_item_desc_delete(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="poe2-lookup item-desc-delete")
    p.add_argument("name", nargs="+")
    args = p.parse_args(argv)
    name = " ".join(args.name)
    if _get_pdb().delete_item_desc(name):
        print(f"{_GREEN}✓ Deleted '{name}'.{_RESET}")
        return 0
    print(f"{_RED}Item description '{name}' not found.{_RESET}", file=sys.stderr)
    return 1


def _cmd_item_desc_refresh(argv: list[str]) -> int:
    """Re-seed mechanic concept entries from the built-in definitions."""
    from poe2_crafting_mcp.data.item_descriptions import ITEM_DESCRIPTIONS
    pdb = _get_pdb()
    n = pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)
    ds = pdb.item_desc_status()
    print(f"{_GREEN}✓ Seeded {n} mechanic-concept entries from built-in definitions.{_RESET}")
    print(f"  {_BOLD}Total in DB:{_RESET} {ds.get('total', 0)}")
    print(f"  {_DIM}Run 'poe2-lookup item-desc-seed' to bulk-seed from poe2wiki.net{_RESET}")
    return 0


def _cmd_item_desc_seed(argv: list[str]) -> int:
    """Bulk-seed item descriptions from poe2wiki.net for all known bases + currencies."""
    p = argparse.ArgumentParser(prog="poe2-lookup item-desc-seed",
                                description=(
                                    "Fetch item descriptions from poe2wiki.net for all "
                                    "currencies and bases in the PoB DB. Results are cached "
                                    "in the item_descriptions table. Requires internet."
                                ))
    p.add_argument("--dry-run", action="store_true",
                   help="show counts without writing to DB")
    args = p.parse_args(argv)

    from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
    from poe2_crafting_mcp.data.database import PoBDatabase

    pdb = _get_pdb()
    db = PoBDatabase()
    wiki = Poe2WikiClient()

    # Re-seed mechanic concept entries from built-ins first
    from poe2_crafting_mcp.data.item_descriptions import ITEM_DESCRIPTIONS
    n_concepts = pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)
    print(f"  {n_concepts} mechanic concept entries seeded from built-ins.")

    from poe2_crafting_mcp.data.general_items import all_exchange_item_names

    print("Collecting item names from PoB DB and exchange lists…")
    currency_rows = db.search_currencies(limit=5000)
    base_rows = db.search_bases(limit=5000)
    seen: set[str] = set()
    names: list[str] = []
    for r in list(currency_rows) + list(base_rows):
        n = r['name']
        if n not in seen:
            seen.add(n)
            names.append(n)
    # Also include exchange item display names (catalysts, abyss jewels, wombgifts, etc.)
    for n in all_exchange_item_names():
        if n not in seen:
            seen.add(n)
            names.append(n)
    print(f"  {len(names)} unique names "
          f"({len(currency_rows)} currencies + {len(base_rows)} bases + exchange items)")

    if args.dry_run:
        print(f"{_YELLOW}Dry run — no DB writes.{_RESET}")
        return 0

    print(f"Fetching from poe2wiki.net in batches of 50…")
    items = wiki.fetch_items(names)
    fetched = 0
    for item in items:
        pdb.upsert_item_desc(**item)
        fetched += 1
    try:
        pdb._conn.execute("INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES('rebuild')")
        pdb._conn.commit()
    except Exception:
        pass
    ds = pdb.item_desc_status()
    print(f"\n{_GREEN}✓ Seeded {fetched} items from poe2wiki.net "
          f"({len(names) - fetched} not found on wiki).{_RESET}")
    print(f"  {_BOLD}Total in DB:{_RESET} {ds.get('total', 0)}")
    return 0


_ITEM_DESC_CMDS = {
    "item-desc-status":  _cmd_item_desc_status,
    "item-desc-list":    _cmd_item_desc_list,
    "item-desc-get":     _cmd_item_desc_get,
    "item-desc-add":     _cmd_item_desc_add,
    "item-desc-delete":  _cmd_item_desc_delete,
    "item-desc-refresh": _cmd_item_desc_refresh,
    "item-desc-seed":    _cmd_item_desc_seed,
}


# ── Mod pool subcommands ──────────────────────────────────────────────────────


def _cmd_mod_pool_status(argv: list[str]) -> int:
    """Show mod_weights table freshness."""
    ms = _get_pdb().mod_weight_status()
    status = ms.get("status", "unknown")
    icons = {
        "fresh":        f"{_GREEN}✓ fresh{_RESET}",
        "stale":        f"{_YELLOW}⚠ stale (>14 days){_RESET}",
        "never_seeded": f"{_RED}✗ never seeded{_RESET}",
    }
    print(_h("Mod Pool Status"))
    print(f"  {_BOLD}Status:{_RESET}       {icons.get(status, status)}")
    print(f"  {_BOLD}Total mods:{_RESET}   {ms.get('total', 0)}")
    print(f"  {_BOLD}Item classes:{_RESET} {ms.get('item_classes', 0)}")
    seeded_at = ms.get("seeded_at")
    age_days = ms.get("age_days")
    if seeded_at:
        age_str = f"  {_DIM}({age_days:.1f}d ago){_RESET}" if age_days is not None else ""
        print(f"  {_BOLD}Seeded:{_RESET}      {seeded_at}{age_str}")
    if status != "fresh":
        print(f"\n  {_YELLOW}→ Run: poe2-lookup mod-pool-seed{_RESET}")
    return 0


def _cmd_mod_pool_seed(argv: list[str]) -> int:
    """Fetch mod spawn weights from poe2db.tw for all item classes."""
    import time as _time

    p = argparse.ArgumentParser(
        prog="poe2-lookup mod-pool-seed",
        description="Fetch modifier spawn weights from poe2db.tw for all item classes.",
    )
    p.add_argument("--class", dest="item_class", default="",
                   help="Seed a single item class (e.g. Gloves_int)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be fetched without writing")
    p.add_argument("--delay", type=float, default=3.0,
                   help="Seconds between requests (default: 3)")
    args = p.parse_args(argv)

    from poe2_crafting_mcp.data.poe2db_client import Poe2DbClient, ALL_ITEM_CLASSES

    targets = [args.item_class] if args.item_class else ALL_ITEM_CLASSES

    if args.dry_run:
        print(f"{_BOLD}Would fetch mod weights for {len(targets)} item classes:{_RESET}")
        for t in targets:
            print(f"  {t}")
        est = len(targets) * args.delay
        print(f"\n  {_DIM}Estimated time: ~{est:.0f}s{_RESET}")
        return 0

    pdb = _get_pdb()
    client = Poe2DbClient()
    start = _time.time()

    print(f"{_DIM}Fetching mod weights from poe2db.tw "
          f"({len(targets)} classes, ~{len(targets) * args.delay:.0f}s)…{_RESET}",
          flush=True)

    total_mods = 0
    failed: list[str] = []
    for i, item_class in enumerate(targets):
        if i > 0:
            _time.sleep(args.delay)
        try:
            mods = client.fetch_item_class(item_class)
            if mods:
                pdb.clear_mod_weights(item_class)
                pdb.upsert_mod_weights(mods)
                total_mods += len(mods)
                print(f"  {_DIM}[{i+1}/{len(targets)}] {item_class}: "
                      f"{len(mods)} mods{_RESET}", flush=True)
            else:
                print(f"  {_YELLOW}[{i+1}/{len(targets)}] {item_class}: "
                      f"no data{_RESET}", flush=True)
        except Exception as exc:
            failed.append(item_class)
            print(f"  {_RED}[{i+1}/{len(targets)}] {item_class}: "
                  f"ERROR {exc}{_RESET}", flush=True)

    from datetime import datetime, timezone
    pdb.set_meta("mod_weights_seeded_at",
                 datetime.now(timezone.utc).isoformat())

    elapsed = _time.time() - start
    print(f"\n{_GREEN}✓ Seeded {total_mods} mods from {len(targets)} classes "
          f"in {elapsed:.1f}s{_RESET}")
    if failed:
        print(f"  {_YELLOW}Failed: {', '.join(failed)}{_RESET}")
    return 0


def _fmt_craftable_mods(result: dict, show_tiers: bool = False) -> None:
    """Print craftable mods result in a readable format."""
    ilvl = result['ilvl']
    pool = result['pool']
    item_class = result['item_class']
    min_lv = result.get('min_mod_level', 0)

    header = f"Craftable Mods: {item_class} (ilvl {ilvl}, {pool}"
    if min_lv:
        header += f", min_mod_lv≥{min_lv}"
    header += ")"
    print(_h(header))
    print()

    def _fmt_group_list(groups: list, total_weight: int, label: str,
                       grand_total_weight: int = 0) -> None:
        print(f"  {_BOLD}{label}{_RESET} ({len(groups)} families, "
              f"total pool weight {total_weight})")
        for g in groups:
            fw = g['family_weight']
            affix_pct = fw / total_weight * 100 if total_weight else 0
            all_pct = fw / grand_total_weight * 100 if grand_total_weight else affix_pct
            top_tier = g['tiers'][0]  # highest tier (sorted by req_level DESC)
            print(f"    {_CYAN}{affix_pct:5.1f}%{_RESET} "
                  f"{_DIM}({all_pct:4.1f}% all | w={fw}){_RESET}  "
                  f"{top_tier['stat_text'][:48]}")
            if show_tiers:
                for i, t in enumerate(g['tiers']):
                    tier_num = i + 1
                    tier_affix_pct = t['weight'] / total_weight * 100 if total_weight else 0
                    tier_all_pct = t['weight'] / grand_total_weight * 100 if grand_total_weight else tier_affix_pct
                    print(f"           {_DIM}T{tier_num} ilvl≥{t['req_level']:2d}  "
                          f"{tier_affix_pct:4.1f}% ({tier_all_pct:4.1f}% all | w={t['weight']})  "
                          f"{t['stat_text'][:38]}{_RESET}")
            elif len(g['tiers']) > 1:
                print(f"           {_DIM}{len(g['tiers'])} tiers "
                      f"(T1 ilvl≥{top_tier['req_level']}){_RESET}")

    # Grand total = prefix + suffix combined (for "all%" column)
    grand_total = result['total_prefix_weight'] + result['total_suffix_weight']

    # Prefixes
    _fmt_group_list(result['prefixes'], result['total_prefix_weight'],
                    "Prefixes", grand_total)
    print()
    # Suffixes
    _fmt_group_list(result['suffixes'], result['total_suffix_weight'],
                    "Suffixes", grand_total)


def _cmd_mod_pool_query(argv: list[str]) -> int:
    """Query craftable mods for an item class or base name."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup mod-pool",
        description="Query craftable mod pool for an item class or base item.",
    )
    p.add_argument("target", help="Item class slug (Gloves_int) or base name (Gold Gloves)")
    p.add_argument("--ilvl", type=int, default=100, help="Item level (default: 100)")
    p.add_argument("--pool", default="normal", help="Mod pool (default: normal)")
    p.add_argument("--prefix", action="store_true", help="Show prefixes only")
    p.add_argument("--suffix", action="store_true", help="Show suffixes only")
    p.add_argument("--tiers", action="store_true", help="Expand all tiers with individual weights")
    p.add_argument("--currency", default="",
                   help=("Currency to simulate pool filtering. "
                         "Options: greater-transmute (ilvl≥44), perfect-transmute (≥70), "
                         "greater-regal/chaos/exalted (≥35), perfect-regal/chaos/exalted (≥50), "
                         "greater-augment (≥44), perfect-augment (≥70). "
                         "Or pass a raw min-mod-level number."))
    args = p.parse_args(argv)

    pdb = _get_pdb()

    # Determine item_class — either directly or by resolving a base name
    target = args.target
    item_class = None

    # Check if it looks like a poe2db slug (contains underscore or is a known class)
    from poe2_crafting_mcp.data.poe2db_client import ALL_ITEM_CLASSES
    if target in ALL_ITEM_CLASSES:
        item_class = target
    else:
        # Try to resolve as a base item name
        from poe2_crafting_mcp.data.database import PoBDatabase
        try:
            db = PoBDatabase()
            bases = db.search_bases(keyword=target, limit=1)
            if bases:
                base = bases[0]
                from poe2_crafting_mcp.data.poe2db_client import base_tags_to_item_class
                item_class = base_tags_to_item_class(
                    base['slot'], base.get('tags', []))
                if item_class:
                    print(f"  {_DIM}Resolved: {base['name']} → {item_class}{_RESET}")
        except FileNotFoundError:
            pass

    if not item_class:
        # Last resort: try the target as-is
        item_class = target.replace(' ', '_')

    affix_type = ""
    if args.prefix:
        affix_type = "prefix"
    elif args.suffix:
        affix_type = "suffix"

    # Resolve --currency to min_mod_level
    _CURRENCY_MIN_MOD_LV: dict[str, int] = {
        "greater-transmute": 44, "greater-transmutation": 44,
        "perfect-transmute": 70, "perfect-transmutation": 70,
        "greater-augment": 44, "greater-augmentation": 44,
        "perfect-augment": 70, "perfect-augmentation": 70,
        "greater-regal": 35, "perfect-regal": 50,
        "greater-chaos": 35, "perfect-chaos": 50,
        "greater-exalted": 35, "perfect-exalted": 50,
    }
    min_mod_level = 0
    if args.currency:
        cur = args.currency.lower().strip()
        if cur in _CURRENCY_MIN_MOD_LV:
            min_mod_level = _CURRENCY_MIN_MOD_LV[cur]
        else:
            try:
                min_mod_level = int(cur)
            except ValueError:
                print(f"  {_RED}Unknown currency '{args.currency}'. "
                      f"Use: greater-transmute, perfect-regal, etc. "
                      f"or a raw number.{_RESET}")
                return 1
        print(f"  {_DIM}Currency filter: min mod level ≥ {min_mod_level}{_RESET}")

    result = pdb.get_craftable_mods(item_class, args.ilvl, args.pool,
                                    affix_type, min_mod_level)

    if not result['prefixes'] and not result['suffixes']:
        print(f"  {_RED}No mods found for {item_class} (pool={args.pool}, "
              f"ilvl={args.ilvl}, min_mod_lv={min_mod_level}).{_RESET}")
        print(f"  {_DIM}Run 'poe2-lookup mod-pool-seed' if not yet seeded.{_RESET}")
        return 1

    _fmt_craftable_mods(result, show_tiers=args.tiers)
    return 0


def _cmd_essence_mods(argv: list[str]) -> int:
    """Query essence-guaranteed mods for an item class or base."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup essence-mods",
        description="Show essence-guaranteed mods for an item base.",
    )
    p.add_argument("target", help="Base name or item class slug")
    p.add_argument("--ilvl", type=int, default=100)
    args = p.parse_args(argv)
    # Reuse mod-pool with pool=essence
    return _cmd_mod_pool_query([args.target, '--ilvl', str(args.ilvl), '--pool', 'essence'])


def _cmd_desecrated_mods(argv: list[str]) -> int:
    """Query abyss desecrated mods for an item class or base."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup desecrated-mods",
        description="Show abyss desecrated mods for an item base.",
    )
    p.add_argument("target", help="Base name or item class slug")
    p.add_argument("--ilvl", type=int, default=100)
    args = p.parse_args(argv)
    return _cmd_mod_pool_query([args.target, '--ilvl', str(args.ilvl), '--pool', 'desecrated'])


def _cmd_influence_mods(argv: list[str]) -> int:
    """Query influence mods (marksman, decay, etc.) for an item class or base."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup influence-mods",
        description="Show influence-specific mods for an item base.",
    )
    p.add_argument("target", help="Base name or item class slug")
    p.add_argument("influence", help="marksman, decay, chronomancy, destruction, berserking, soul")
    p.add_argument("--ilvl", type=int, default=100)
    args = p.parse_args(argv)
    return _cmd_mod_pool_query([args.target, '--ilvl', str(args.ilvl), '--pool', args.influence])


def _resolve_item_class(target: str) -> str | None:
    """Resolve a base name or slug to an item class. Returns None if unresolvable."""
    from poe2_crafting_mcp.data.poe2db_client import ALL_ITEM_CLASSES, base_tags_to_item_class
    if target in ALL_ITEM_CLASSES:
        return target
    from poe2_crafting_mcp.data.database import PoBDatabase
    try:
        db = PoBDatabase()
        bases = db.search_bases(keyword=target, limit=1)
        if bases:
            ic = base_tags_to_item_class(bases[0]['slot'], bases[0].get('tags', []))
            if ic:
                print(f"  {_DIM}Resolved: {bases[0]['name']} → {ic}{_RESET}")
                return ic
    except FileNotFoundError:
        pass
    return target.replace(' ', '_')


def _get_live_prices() -> dict[str, float]:
    """Try to get live currency prices from the economy cache."""
    try:
        pdb = _get_pdb()
        league = pdb.get_meta("active_league") or ""
        if not league:
            return {}
        # Map currency keys to search terms
        _CURRENCY_NAMES = {
            "transmute": "Orb of Transmutation",
            "augment": "Orb of Augmentation",
            "regal": "Regal Orb",
            "alchemy": "Orb of Alchemy",
            "chaos": "Chaos Orb",
            "exalted": "Exalted Orb",
            "annulment": "Orb of Annulment",
            "divine": "Divine Orb",
            "greater_transmute": "Greater Orb of Transmutation",
            "greater_augment": "Greater Orb of Augmentation",
            "greater_regal": "Greater Regal Orb",
            "greater_chaos": "Greater Chaos Orb",
            "greater_exalted": "Greater Exalted Orb",
            "perfect_transmute": "Perfect Orb of Transmutation",
            "perfect_augment": "Perfect Orb of Augmentation",
            "perfect_regal": "Perfect Regal Orb",
            "perfect_chaos": "Perfect Chaos Orb",
            "perfect_exalted": "Perfect Exalted Orb",
        }
        prices = {}
        for key, name in _CURRENCY_NAMES.items():
            rows = pdb.search_prices(name, league, category="Currency", limit=1)
            if rows and rows[0].get("chaos_value"):
                prices[key] = rows[0]["chaos_value"]
        return prices
    except Exception:
        return {}


def _cmd_craft_cost(argv: list[str]) -> int:
    """Estimate crafting cost for a target mod."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup craft-cost",
        description="Estimate expected cost to hit a target mod on an item.",
    )
    p.add_argument("target", help="Base name or item class slug")
    p.add_argument("mod_family", help="Mod family (e.g. IncreasedLife, LocalIncreasedEnergyShield)")
    p.add_argument("--currency", default="exalted", help="Currency to use (default: exalted)")
    p.add_argument("--ilvl", type=int, default=82)
    p.add_argument("--tier", type=int, default=0, help="Target specific tier (0=any)")
    p.add_argument("--omen", default="", help="Omen to use (e.g. sinistral_exaltation)")
    p.add_argument("--price", type=float, default=0, help="Currency price in chaos (0=auto from economy)")
    p.add_argument("--existing-mods", default="",
                   help="Comma-separated mod families already on item (blocks them from pool)")
    args = p.parse_args(argv)

    pdb = _get_pdb()
    item_class = _resolve_item_class(args.target)

    mod_pool = pdb.get_craftable_mods(item_class, args.ilvl, "normal")

    from poe2_crafting_mcp.crafting.simulator import CraftingSimulator
    sim = CraftingSimulator(item_class, args.ilvl, mod_pool)

    # Set existing mods if specified (blocks those families from pool)
    if args.existing_mods:
        existing = [f.strip() for f in args.existing_mods.split(",") if f.strip()]
        sim.set_item_mods(existing)
        print(f"  {_DIM}Existing mods blocked: {', '.join(existing)}{_RESET}")

    # Get price — use provided, or try live, or fallback
    currency_price = args.price
    if currency_price <= 0:
        live_prices = _get_live_prices()
        currency_price = live_prices.get(args.currency, 0)
        if currency_price <= 0:
            # Fallback defaults
            from poe2_crafting_mcp.crafting.simulator import CraftingSimulator as _CS
            # Use the default prices from compare_methods
            currency_price = 1.0  # generic fallback
            _defaults = {"transmute": 0.01, "augment": 0.02, "chaos": 1.0,
                         "exalted": 5.0, "greater_transmute": 0.1,
                         "greater_exalted": 15.0, "perfect_transmute": 2.0,
                         "perfect_exalted": 50.0}
            currency_price = _defaults.get(args.currency, 1.0)

    result = sim.estimate_cost(
        target_family=args.mod_family,
        currency=args.currency,
        omen=args.omen,
        target_tier=args.tier,
        currency_price=currency_price,
    )

    if result.get("error"):
        print(f"  {_RED}{result['error']}{_RESET}")
        return 1

    if result.get("probability", 0) == 0:
        print(f"  {_RED}Target '{args.mod_family}' not in available pool.{_RESET}")
        note = result.get("note", "")
        if note:
            print(f"  {_DIM}{note}{_RESET}")
        return 1

    print(_h(f"Craft Cost: {args.mod_family} on {item_class}"))
    print(f"  {_BOLD}Currency:{_RESET}    {args.currency}"
          + (f" + {args.omen}" if args.omen else ""))
    print(f"  {_BOLD}Probability:{_RESET} {_CYAN}{result['probability_pct']}%{_RESET}"
          f"  (weight {result['target_weight']}/{result['total_weight']})")
    print(f"  {_BOLD}Pool size:{_RESET}   {result['available_pool_size']} eligible tiers")
    print(f"  {_BOLD}Expected:{_RESET}    {_YELLOW}{result['expected_attempts']}{_RESET} attempts")
    print(f"  {_BOLD}Cost/try:{_RESET}    {result['cost_per_attempt']:.1f}c")
    print(f"  {_BOLD}Total cost:{_RESET}  {_GREEN}{result['expected_cost']:.1f}c{_RESET} expected")
    return 0


def _cmd_craft_compare(argv: list[str]) -> int:
    """Compare crafting methods for a target mod."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup craft-compare",
        description="Compare crafting methods to find cheapest path to a target mod.",
    )
    p.add_argument("target", help="Base name or item class slug")
    p.add_argument("mod_family", help="Mod family (e.g. IncreasedLife)")
    p.add_argument("--ilvl", type=int, default=82)
    p.add_argument("--tier", type=int, default=0, help="Target specific tier (0=any)")
    p.add_argument("--existing-mods", default="",
                   help="Comma-separated mod families already on item")
    args = p.parse_args(argv)

    pdb = _get_pdb()
    item_class = _resolve_item_class(args.target)

    mod_pool = pdb.get_craftable_mods(item_class, args.ilvl, "normal")

    from poe2_crafting_mcp.crafting.simulator import CraftingSimulator
    sim = CraftingSimulator(item_class, args.ilvl, mod_pool)

    # Set existing mods
    if args.existing_mods:
        existing = [f.strip() for f in args.existing_mods.split(",") if f.strip()]
        sim.set_item_mods(existing)
        print(f"  {_DIM}Existing mods blocked: {', '.join(existing)}{_RESET}")

    # Try live prices
    live_prices = _get_live_prices()

    results = sim.compare_methods(
        target_family=args.mod_family,
        target_tier=args.tier,
        prices=live_prices if live_prices else None,
    )

    if not results:
        print(f"  {_RED}Target '{args.mod_family}' not achievable with any method.{_RESET}")
        return 1

    print(_h(f"Method Comparison: {args.mod_family} on {item_class}"))
    print(f"  {_DIM}ilvl={args.ilvl}, tier={'any' if args.tier == 0 else args.tier}{_RESET}")
    print()
    print(f"  {'Currency':<22} {'Prob%':>6} {'Attempts':>8} {'Cost/try':>8} {'Total':>8}")
    print(f"  {'─'*22} {'─'*6} {'─'*8} {'─'*8} {'─'*8}")
    for r in results:
        cur = r.get('currency', '?')
        prob = r.get('probability_pct', 0)
        att = r.get('expected_attempts', 0)
        cpa = r.get('cost_per_attempt', 0)
        total = r.get('expected_cost', 0)
        color = _GREEN if r == results[0] else _RESET
        print(f"  {color}{cur:<22} {prob:>5.1f}% {att:>7.1f}x  {cpa:>7.1f}c {total:>7.1f}c{_RESET}")

    print()
    best = results[0]
    print(f"  {_GREEN}→ Best: {best['currency']} at {best['expected_cost']:.1f}c "
          f"({best['probability_pct']}% per attempt){_RESET}")
    return 0


def _cmd_craft_item(argv: list[str]) -> int:
    """Analyze a found/traded item and show crafting options."""
    p = argparse.ArgumentParser(
        prog="poe2-lookup craft-item",
        description=(
            "Analyze an item's current mods and show what can still be crafted.\n"
            "Pass mod texts as they appear on the item (from trade or in-game)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("target", help="Base name or item class slug")
    p.add_argument("--ilvl", type=int, default=82)
    p.add_argument("--mods", nargs="+", required=True,
                   help='Mod texts on the item (e.g. "+120 to maximum Life" "42%% to Fire Res")')
    p.add_argument("--want", default="",
                   help="Mod family you want to add (shows probability)")
    p.add_argument("--currency", default="exalted",
                   help="Currency to use for probability (default: exalted)")
    args = p.parse_args(argv)

    pdb = _get_pdb()
    item_class = _resolve_item_class(args.target)

    mod_pool = pdb.get_craftable_mods(item_class, args.ilvl, "normal")

    from poe2_crafting_mcp.crafting.simulator import CraftingSimulator
    sim = CraftingSimulator(item_class, args.ilvl, mod_pool)

    # Identify the mods
    identified = sim.identify_mods_from_text(args.mods)

    print(_h(f"Item Analysis: {item_class} (ilvl {args.ilvl})"))
    print()
    print(f"  {_BOLD}Current Mods:{_RESET}")
    prefixes = []
    suffixes = []
    unknown = []
    for m in identified:
        fam = m['family']
        atype = m['affix_type']
        if fam == "(unknown)":
            unknown.append(m)
            print(f"    {_RED}? {m['text']}{_RESET}")
        elif atype == 'prefix':
            prefixes.append(fam)
            print(f"    {_CYAN}P{_RESET} {m['text']}  {_DIM}→ {fam}{_RESET}")
        else:
            suffixes.append(fam)
            print(f"    {_YELLOW}S{_RESET} {m['text']}  {_DIM}→ {fam}{_RESET}")

    print()
    print(f"  {_BOLD}Slots:{_RESET} {len(prefixes)}/3 prefixes, {len(suffixes)}/3 suffixes")
    open_p = 3 - len(prefixes)
    open_s = 3 - len(suffixes)
    print(f"  {_BOLD}Open:{_RESET}  {open_p} prefix, {open_s} suffix")

    # Set the item state
    all_families = prefixes + suffixes
    sim.set_item_mods(all_families)

    if unknown:
        print(f"\n  {_YELLOW}⚠ {len(unknown)} mod(s) not identified — pool may be inaccurate{_RESET}")

    # Show available pool summary
    pool = sim.get_available_pool(min_mod_level=0)
    pool_prefixes = [m for m in pool if m['affix_type'] == 'prefix']
    pool_suffixes = [m for m in pool if m['affix_type'] == 'suffix']
    total_weight = sum(m['weight'] for m in pool)

    print(f"\n  {_BOLD}Available pool:{_RESET} {len(pool)} tiers "
          f"({len(pool_prefixes)} prefix, {len(pool_suffixes)} suffix)")

    # If --want specified, show probability
    if args.want:
        result = sim.probability_of(args.want, args.currency)
        if result.get("probability", 0) > 0:
            print(f"\n  {_BOLD}Chance to hit '{args.want}':{_RESET}")
            print(f"    {_CYAN}{result['probability_pct']}%{_RESET} per {args.currency} "
                  f"({result['expected_attempts']:.1f} expected attempts)")
        else:
            print(f"\n  {_RED}'{args.want}' not available (already on item or wrong ilvl){_RESET}")
    else:
        # Show top 5 most likely mods to hit
        print(f"\n  {_BOLD}Most likely mods to hit (exalted):{_RESET}")
        # Group by family
        from collections import defaultdict
        family_weights: dict[str, int] = defaultdict(int)
        family_type: dict[str, str] = {}
        for m in pool:
            family_weights[m['family']] += m['weight']
            family_type[m['family']] = m['affix_type']
        sorted_families = sorted(family_weights.items(), key=lambda x: -x[1])
        for fam, w in sorted_families[:8]:
            pct = w / total_weight * 100 if total_weight else 0
            atype = family_type[fam]
            marker = f"{_CYAN}P{_RESET}" if atype == 'prefix' else f"{_YELLOW}S{_RESET}"
            print(f"    {marker} {pct:5.1f}%  {fam}")

    return 0


_MOD_POOL_CMDS = {
    "mod-pool-status":  _cmd_mod_pool_status,
    "mod-pool-seed":    _cmd_mod_pool_seed,
    "mod-pool":         _cmd_mod_pool_query,
    "essence-mods":     _cmd_essence_mods,
    "desecrated-mods":  _cmd_desecrated_mods,
    "influence-mods":   _cmd_influence_mods,
    "craft-cost":       _cmd_craft_cost,
    "craft-compare":    _cmd_craft_compare,
    "craft-item":       _cmd_craft_item,
}


# ── Global status & seed-all ──────────────────────────────────────────────────


def _cmd_status(argv: list[str]) -> int:
    """Show status of all data stores: ETL, concepts, item descriptions."""
    from poe2_crafting_mcp.data.price_db import PriceDatabase

    pdb = PriceDatabase()

    # ── ETL (game data) ───────────────────────────────────────────────────────
    print(_h("Game Data (ETL)"))
    try:
        etl_row = pdb._conn.execute(
            "SELECT ran_at, row_counts FROM etl_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except Exception:
        etl_row = None

    if etl_row:
        import json as _json
        counts = _json.loads(etl_row["row_counts"]) if etl_row["row_counts"] else {}
        print(f"  {_BOLD}Status:{_RESET}  {_GREEN}✓ populated{_RESET}")
        print(f"  {_BOLD}Ran at:{_RESET}  {etl_row['ran_at']}")
        for tbl, cnt in counts.items():
            print(f"  {_DIM}  {tbl}:{_RESET} {cnt}")
    else:
        # Check if the file even exists or has the ETL tables
        db_path = Path(pdb._path)
        if not db_path.exists():
            print(f"  {_BOLD}Status:{_RESET}  {_RED}✗ database file not found{_RESET}")
            print(f"  {_DIM}  path: {db_path}{_RESET}")
        else:
            # Check if ETL tables exist
            has_currencies = pdb._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='currencies'"
            ).fetchone()
            if has_currencies:
                cur_count = pdb._conn.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
                base_count = pdb._conn.execute("SELECT COUNT(*) FROM item_bases").fetchone()[0]
                print(f"  {_BOLD}Status:{_RESET}  {_YELLOW}⚠ no ETL run recorded{_RESET}")
                print(f"  {_DIM}  currencies: {cur_count}, item_bases: {base_count}{_RESET}")
            else:
                print(f"  {_BOLD}Status:{_RESET}  {_RED}✗ never run{_RESET}")
        print(f"\n  {_YELLOW}→ Run: poe2-lookup seed-all{_RESET}")

    # ── Concepts ──────────────────────────────────────────────────────────────
    print()
    cs = pdb.concept_status()
    icons = {
        "fresh":        f"{_GREEN}✓ fresh{_RESET}",
        "stale":        f"{_YELLOW}⚠ stale (>30 days){_RESET}",
        "never_seeded": f"{_RED}✗ never seeded{_RESET}",
    }
    print(_h("Concepts"))
    print(f"  {_BOLD}Status:{_RESET}  {icons.get(cs.get('status', ''), cs.get('status', ''))}")
    print(f"  {_BOLD}Total:{_RESET}   {cs.get('total', 0)}")
    if cs.get("manual"):
        print(f"  {_DIM}  manual: {cs['manual']}{_RESET}")
    if cs.get("seeded_at"):
        age = cs.get("age_days")
        age_str = f"  {_DIM}({age:.1f}d ago){_RESET}" if age is not None else ""
        print(f"  {_BOLD}Seeded:{_RESET}  {cs['seeded_at']}{age_str}")

    # ── Item Descriptions ─────────────────────────────────────────────────────
    print()
    ds = pdb.item_desc_status()
    print(_h("Item Descriptions"))
    print(f"  {_BOLD}Status:{_RESET}  {icons.get(ds.get('status', ''), ds.get('status', ''))}")
    print(f"  {_BOLD}Total:{_RESET}   {ds.get('total', 0)}")
    if ds.get("seeded_at"):
        age = ds.get("age_days")
        age_str = f"  {_DIM}({age:.1f}d ago){_RESET}" if age is not None else ""
        print(f"  {_BOLD}Seeded:{_RESET}  {ds['seeded_at']}{age_str}")

    # ── Mod Weights ───────────────────────────────────────────────────────────
    print()
    ms = pdb.mod_weight_status()
    print(_h("Mod Pool (poe2db weights)"))
    print(f"  {_BOLD}Status:{_RESET}  {icons.get(ms.get('status', ''), ms.get('status', ''))}")
    print(f"  {_BOLD}Total:{_RESET}   {ms.get('total', 0)} mods across "
          f"{ms.get('item_classes', 0)} item classes")
    if ms.get("seeded_at"):
        age = ms.get("age_days")
        age_str = f"  {_DIM}({age:.1f}d ago){_RESET}" if age is not None else ""
        print(f"  {_BOLD}Seeded:{_RESET}  {ms['seeded_at']}{age_str}")

    # ── Summary hint ──────────────────────────────────────────────────────────
    needs_work = []
    if not etl_row:
        needs_work.append("ETL")
    if cs.get("status") != "fresh":
        needs_work.append("concepts")
    if ds.get("status") != "fresh":
        needs_work.append("item-descriptions")
    if ms.get("status") != "fresh":
        needs_work.append("mod-pool")
    if needs_work:
        print(f"\n  {_YELLOW}→ Run 'poe2-lookup seed-all' to populate: "
              f"{', '.join(needs_work)}{_RESET}")
    else:
        print(f"\n  {_GREEN}All data stores are up to date.{_RESET}")
    return 0


def _cmd_seed_all(argv: list[str]) -> int:
    """Run ETL + concept seed + item description seed in correct order."""
    import time as _time

    p = argparse.ArgumentParser(
        prog="poe2-lookup seed-all",
        description=(
            "Populate all data stores in the correct order:\n"
            "  1. ETL (game data from PoB vendor)\n"
            "  2. Concepts (from built-ins + poe2wiki.net)\n"
            "  3. Item descriptions (from built-ins + poe2wiki.net)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--skip-etl", action="store_true",
                   help="Skip ETL step (use existing game data)")
    p.add_argument("--skip-wiki", action="store_true",
                   help="Skip wiki fetching (seed from built-ins only)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be done without writing")
    args = p.parse_args(argv)

    start = _time.time()

    # ── Step 1: ETL ───────────────────────────────────────────────────────────
    if args.skip_etl:
        print(f"{_DIM}Skipping ETL (--skip-etl){_RESET}")
    else:
        print(_h("Step 1: ETL (game data)"))
        # Check if DB already has ETL data
        from poe2_crafting_mcp.data.price_db import PriceDatabase
        pdb_check = PriceDatabase()
        has_currencies = pdb_check._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='currencies'"
        ).fetchone()
        if has_currencies:
            cur_count = pdb_check._conn.execute(
                "SELECT COUNT(*) FROM currencies").fetchone()[0]
            if cur_count > 0 and not args.dry_run:
                print(f"  {_DIM}ETL tables already populated ({cur_count} currencies). "
                      f"Re-running to refresh…{_RESET}")
        pdb_check._conn.close()

        if args.dry_run:
            print(f"  {_YELLOW}Would run ETL pipeline (PoB data → SQLite){_RESET}")
        else:
            print(f"  {_DIM}Running ETL pipeline…{_RESET}", flush=True)
            from poe2_crafting_mcp.data.etl import run as run_etl
            counts = run_etl()
            total_rows = sum(counts.values())
            print(f"  {_GREEN}✓ ETL complete: {total_rows} rows across "
                  f"{len(counts)} tables{_RESET}")
            for tbl, cnt in counts.items():
                print(f"    {_DIM}{tbl}: {cnt}{_RESET}")

    # ── Step 2: Concepts ──────────────────────────────────────────────────────
    print()
    print(_h("Step 2: Concepts"))
    pdb = _get_pdb()

    # Seed from built-ins
    from poe2_crafting_mcp.data.concepts import CONCEPTS
    if args.dry_run:
        print(f"  {_YELLOW}Would seed {len(CONCEPTS)} concepts from built-ins{_RESET}")
    else:
        n = pdb.upsert_concepts_bulk(CONCEPTS)
        print(f"  {n} concepts seeded from built-ins.")

    # Wiki seed
    if args.skip_wiki:
        print(f"  {_DIM}Skipping wiki fetch (--skip-wiki){_RESET}")
    elif args.dry_run:
        print(f"  {_YELLOW}Would fetch concepts from poe2wiki.net{_RESET}")
    else:
        from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
        wiki = Poe2WikiClient()
        print(f"  {_DIM}Fetching concepts from poe2wiki.net…{_RESET}", flush=True)
        fetched, skipped = wiki.seed_concepts_from_db(pdb)
        try:
            pdb._conn.execute(
                "INSERT INTO concepts_fts(concepts_fts) VALUES('rebuild')")
            pdb._conn.commit()
        except Exception:
            pass
        print(f"  {_GREEN}✓ Wiki seeded {fetched} concepts "
              f"({skipped} skipped/not on wiki).{_RESET}")

    # ── Step 3: Item Descriptions ─────────────────────────────────────────────
    print()
    print(_h("Step 3: Item Descriptions"))

    # Seed from built-ins
    from poe2_crafting_mcp.data.item_descriptions import ITEM_DESCRIPTIONS
    if args.dry_run:
        print(f"  {_YELLOW}Would seed {len(ITEM_DESCRIPTIONS)} item descriptions "
              f"from built-ins{_RESET}")
    else:
        n = pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)
        print(f"  {n} item descriptions seeded from built-ins.")

    # Wiki seed (requires ETL tables)
    if args.skip_wiki:
        print(f"  {_DIM}Skipping wiki fetch (--skip-wiki){_RESET}")
    elif args.dry_run:
        print(f"  {_YELLOW}Would fetch item descriptions from poe2wiki.net{_RESET}")
    else:
        from poe2_crafting_mcp.data.database import PoBDatabase
        from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
        from poe2_crafting_mcp.data.general_items import all_exchange_item_names

        try:
            db = PoBDatabase()
        except FileNotFoundError:
            print(f"  {_RED}✗ Cannot fetch wiki items — ETL database not found.{_RESET}")
            print(f"  {_DIM}  Run without --skip-etl first.{_RESET}")
            return 1

        currency_rows = db.search_currencies(limit=5000)
        base_rows = db.search_bases(limit=5000)
        seen: set[str] = set()
        names: list[str] = []
        for r in list(currency_rows) + list(base_rows):
            n = r['name']
            if n not in seen:
                seen.add(n)
                names.append(n)
        for n in all_exchange_item_names():
            if n not in seen:
                seen.add(n)
                names.append(n)

        n_batches = (len(names) + 49) // 50
        print(f"  {_DIM}Fetching {len(names)} items from poe2wiki.net "
              f"({n_batches} batches, ~{n_batches * 3}s)…{_RESET}",
              flush=True)
        wiki = Poe2WikiClient()
        items = wiki.fetch_items(names)
        for item in items:
            pdb.upsert_item_desc(**item)
        try:
            pdb._conn.execute(
                "INSERT INTO item_descriptions_fts(item_descriptions_fts) "
                "VALUES('rebuild')")
            pdb._conn.commit()
        except Exception:
            pass
        print(f"  {_GREEN}✓ Wiki seeded {len(items)} item descriptions "
              f"({len(names) - len(items)} not on wiki).{_RESET}")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = _time.time() - start
    print()
    if args.dry_run:
        print(f"{_YELLOW}Dry run complete — no changes made.{_RESET}")
    else:
        print(f"{_GREEN}{'─'*52}{_RESET}")
        print(f"{_GREEN}✓ All data stores seeded in {elapsed:.1f}s{_RESET}")
        print(f"  {_DIM}Run 'poe2-lookup status' to verify.{_RESET}")
    return 0


_GLOBAL_CMDS = {
    "status":   _cmd_status,
    "seed-all": _cmd_seed_all,
}


# ── Main ──────────────────────────────────────────────────────────────────────

_ALL_TYPES = ("bases", "mods", "gems", "uniques", "nodes", "currencies",
              "concepts", "exchange", "descriptions")

_TYPE_ALIASES: dict[str, str] = {
    # ── Data section aliases ───────────────────────────────────────────────────
    # bases: item base types (use --slot to filter by equipment slot)
    "base": "bases", "item": "bases", "items": "bases",
    "weapon": "bases", "weapons": "bases",
    "armour": "bases", "armor": "bases",
    "helmet": "bases", "helm": "bases",
    "gloves": "bases", "glove": "bases",
    "boots": "bases", "boot": "bases",
    "shield": "bases",
    "quiver": "bases",
    "jewel": "bases",
    "waystone": "bases", "waystones": "bases", "map": "bases", "maps": "bases",
    # mods: explicit/crafted/flask/jewel/charm mods — combine with --category
    "mod": "mods", "affix": "mods", "affixes": "mods", "craft": "mods",
    # gems: skill/support gems
    "gem": "gems", "skill": "gems", "skills": "gems",
    # uniques
    "unique": "uniques",
    # passive tree nodes
    "node": "nodes", "passive": "nodes", "passives": "nodes", "tree": "nodes",
    # currencies: orbs, quality currency, expedition, etc.
    "currency": "currencies", "orb": "currencies",
    # concepts: keyword/mechanic definitions
    "concept": "concepts", "keyword": "concepts", "keywords": "concepts",
    "mechanic": "concepts", "mechanics": "concepts", "definition": "concepts",
    # exchange: poe.ninja exchange items (runes, essences, catalysts, fragments…)
    # Use this to look up prices for these consumable/exchange items
    "rune": "exchange", "essence": "exchange", "catalyst": "exchange",
    "delirium": "exchange", "breach": "exchange", "abyss": "exchange",
    "liquid": "exchange", "wombgift": "exchange", "fragment": "exchange",
    "soulcore": "exchange", "soul_core": "exchange",
    "omen": "exchange", "idol": "exchange", "distilled": "exchange",
    # descriptions: item category / mechanic context entries
    # (Jewellery, Focus, Weapon, Flask, Essence, Omen, Abyss Jewel, etc.)
    "desc": "descriptions", "description": "descriptions",
    "item-desc": "descriptions", "foci": "descriptions",
    "focus": "descriptions", "jewellery": "descriptions", "jewelry": "descriptions",
}


def main() -> None:
    # Pre-dispatch: management subcommands bypass the query parser
    if len(sys.argv) > 1:
        _cmd = sys.argv[1]
        _dispatch = {**_GLOBAL_CMDS, **_CONCEPT_CMDS, **_ITEM_DESC_CMDS, **_MOD_POOL_CMDS}
        if _cmd in _dispatch:
            sys.exit(_dispatch[_cmd](sys.argv[2:]) or 0)

    parser = argparse.ArgumentParser(
        prog="poe2-lookup",
        description=(
            "Search PoE2 game data: bases, mods, gems, uniques, passive nodes, "
            "currencies, concepts/keywords, and item descriptions.\n\n"
            "Also supports management subcommands (run without query):\n"
            "  concept-status/list/search/get/add/delete/refresh/seed\n"
            "  item-desc-status/list/get/add/delete/refresh/seed"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  poe2-lookup 'Gold Gloves'                      base stats + crafting notes\n"
            "  poe2-lookup 'energy shield' --type mods        ES mods with tiers\n"
            "  poe2-lookup 'energy shield' --type mods --tag int_armour\n"
            "  poe2-lookup 'foci'                             focus/foci item descriptions\n"
            "  poe2-lookup 'jewellery'                        ring/amulet/belt context\n"
            "  poe2-lookup 'shock' --type concepts            keyword definitions\n"
            "  poe2-lookup 'Vaal Regalia' --type bases        body armour base\n"
            "  poe2-lookup '' --type bases --slot Focus       all focus bases\n"
            "  poe2-lookup '' --type bases --slot Ring        all ring bases\n"
            "  poe2-lookup '' --type mods --category Flask    all flask mods\n"
            "  poe2-lookup '' --type mods --category Charm    all charm mods\n"
            "  poe2-lookup 'chaos orb' --type descriptions    crafting notes for Chaos Orb\n"
            "  poe2-lookup 'essence' --type descriptions      essence crafting overview\n"
            "  poe2-lookup 'omen' --type descriptions         omen overview\n"
            "\n"
            "Management subcommands (bypass query parser):\n"
            "  poe2-lookup concept-status\n"
            "  poe2-lookup concept-search 'shock'\n"
            "  poe2-lookup concept-get 'Iron Reflexes'\n"
            "  poe2-lookup concept-add 'Name' --category mechanic --summary '...'\n"
            "  poe2-lookup concept-refresh\n"
            "  poe2-lookup item-desc-status\n"
            "  poe2-lookup item-desc-get 'Gold Gloves'\n"
            "  poe2-lookup item-desc-add 'Name' --category base --description '...'\n"
            "  poe2-lookup item-desc-refresh"
        ),
    )
    parser.add_argument("query", nargs="+", help="Search term(s)")
    parser.add_argument(
        "--type", "-t", dest="types", metavar="TYPE",
        help=(
            "Limit search to specific data types. Comma-separated for multiple.\n"
            "Core values: bases, mods, gems, uniques, nodes, currencies, concepts, "
            "exchange, descriptions.\n"
            "Slot shortcuts (→ bases): weapon, armour, helmet, gloves, boots, "
            "shield, quiver, jewel, waystone/map.\n"
            "Concept shortcuts (→ concepts): keyword, mechanic, definition.\n"
            "Exchange shortcuts (→ exchange): rune, essence, catalyst, omen, idol, "
            "breach, abyss, distilled, fragment.\n"
            "Description shortcuts (→ descriptions): desc, foci, focus, jewellery."
        ),
    )
    parser.add_argument("--slot", "-s", default="",
                        help="Item slot filter for bases/uniques (e.g. Gloves, Ring)")
    parser.add_argument("--tag", default="",
                        help="Item tag filter for mods/bases (e.g. staff, ring, int_armour)")
    parser.add_argument("--category", "-c", default="",
                        help=(
                            "Mod category filter (for --type mods). "
                            "Item=weapons/armour/jewellery explicit mods (default), "
                            "Jewel=passive jewel mods, "
                            "Flask=flask prefix/suffix mods, "
                            "Charm=charm mods, "
                            "Runes=rune socket effects, "
                            "Corruption=vaal corruption implicits, "
                            "Desecrated=abyss jewel desecrated mods, "
                            "Exclusive=vendor/special-only mods."
                        ))
    parser.add_argument("--min-level", type=int, default=0,
                        help="Minimum ilvl for bases (default 0)")
    parser.add_argument("--max-level", type=int, default=100,
                        help="Maximum ilvl for bases (default 100)")
    parser.add_argument("--limit", "-l", type=int, default=10,
                        help="Max results per section (default 10)")
    parser.add_argument("--craftable", action="store_true",
                        help="Show craftable mod pool for a base item (with weights)")
    parser.add_argument("--ilvl", type=int, default=100,
                        help="Item level for --craftable (default 100)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colour output")

    args = parser.parse_args()

    query = " ".join(args.query)

    # Resolve which types to search
    if args.types:
        requested = [t.strip().lower() for t in args.types.split(",")]
        types_to_search = [_TYPE_ALIASES.get(t, t) for t in requested]
        types_to_search = [t for t in types_to_search if t in _ALL_TYPES]
        if not types_to_search:
            print(f"Unknown type(s). Choose from: {', '.join(_ALL_TYPES)}", file=sys.stderr)
            sys.exit(1)
    else:
        types_to_search = list(_ALL_TYPES)

    # Disable colour if requested or not a tty
    if args.no_color or not sys.stdout.isatty():
        for name in ("_RESET","_BOLD","_DIM","_YELLOW","_CYAN","_GREEN",
                     "_BLUE","_PURPLE","_RED"):
            globals()[name] = ""

    from poe2_crafting_mcp.data.database import PoBDatabase
    try:
        db = PoBDatabase()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    found_any = False

    if "bases" in types_to_search:
        results = db.search_bases(slot=args.slot, keyword=query, tag=args.tag,
                                  min_level=args.min_level, max_level=args.max_level,
                                  limit=args.limit)
        if results:
            found_any = True
            pdb = _get_pdb()
            # Bulk-fetch missing descriptions from wiki (only uncached names)
            uncached = [b["name"] for b in results
                        if pdb.get_item_desc(b["name"]) is None]
            if uncached:
                try:
                    from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
                    wiki = Poe2WikiClient()
                    fetched = wiki.fetch_items(uncached)
                    for item in fetched:
                        pdb.upsert_item_desc(**item)
                    if fetched:
                        pdb._conn.execute(
                            "INSERT INTO item_descriptions_fts(item_descriptions_fts)"
                            " VALUES('rebuild')"
                        )
                        pdb._conn.commit()
                except Exception:
                    pass  # wiki unavailable — continue without descriptions
            print(_h("Item Bases"))
            for b in results:
                desc = pdb.get_item_desc(b["name"])
                _fmt_base(b, desc=desc)
                print()

            # If --craftable flag is set, show craftable mod pool for the first result
            if args.craftable and results:
                base = results[0]
                from poe2_crafting_mcp.data.poe2db_client import base_tags_to_item_class
                item_class = base_tags_to_item_class(
                    base['slot'], base.get('tags', []))
                if item_class:
                    craft_result = pdb.get_craftable_mods(
                        item_class, args.ilvl, "normal")
                    if craft_result['prefixes'] or craft_result['suffixes']:
                        _fmt_craftable_mods(craft_result)
                    else:
                        print(f"  {_YELLOW}No mod pool data for {item_class}. "
                              f"Run: poe2-lookup mod-pool-seed{_RESET}")
                else:
                    print(f"  {_YELLOW}Cannot resolve item class for "
                          f"{base['name']}{_RESET}")

    if "mods" in types_to_search:
        cat = args.category or "Item"
        results = db.search_mods(keyword=query, item_tag=args.tag,
                                 category=cat, limit=args.limit)
        if results:
            # Expand: fetch all tiers for each matched group (limit groups = args.limit)
            results = db.expand_mod_tiers(results, category=cat,
                                          item_tag=args.tag, max_groups=args.limit)
            found_any = True
            print(_h(f"Mods ({cat})"))
            for m in _with_tiers(results):
                _fmt_mod(m)
                print()
        # Also search other categories if no specific category was given
        if not args.category:
            for extra_cat in ("Jewel", "Runes", "Corruption", "Desecrated", "Flask", "Charm"):
                extra = db.search_mods(keyword=query, item_tag=args.tag,
                                       category=extra_cat, limit=5)
                if extra:
                    extra = db.expand_mod_tiers(extra, category=extra_cat,
                                                item_tag=args.tag, max_groups=5)
                    extra = [m for m in extra if m.get("stat_text") or m.get("affix")]
                    if not extra:
                        continue
                    found_any = True
                    print(_h(f"Mods ({extra_cat})"))
                    for m in _with_tiers(extra):
                        _fmt_mod(m)
                        print()

    if "gems" in types_to_search:
        results = db.search_gems(keyword=query, limit=args.limit)
        if results:
            found_any = True
            print(_h("Gems / Skills"))
            for g in results:
                _fmt_gem(g)
                print()

    if "uniques" in types_to_search:
        results = db.search_uniques(slot=args.slot, keyword=query, limit=args.limit)
        if results:
            found_any = True
            print(_h("Unique Items"))
            for u in results:
                _fmt_unique(u)
                print()

    if "nodes" in types_to_search:
        results = db.search_passive_nodes(keyword=query, limit=args.limit)
        if results:
            found_any = True
            print(_h("Passive Nodes"))
            for n in results:
                _fmt_node(n)
                print()

    currency_names_shown: set[str] = set()
    if "currencies" in types_to_search:
        results = db.search_currencies(keyword=query)
        if results:
            found_any = True
            print(_h("Currencies"))
            for c in results:
                _fmt_currency(c)
                currency_names_shown.add(c["name"].lower())
                print()

    if "concepts" in types_to_search:
        results = _get_pdb().search_concepts(keyword=query, limit=args.limit)
        if results:
            found_any = True
            print(_h("Concepts / Keywords"))
            for c in results:
                _fmt_concept(c)
                print()

    if "exchange" in types_to_search:
        from poe2_crafting_mcp.data.general_items import search_exchange_items
        results = search_exchange_items(keyword=query, limit=args.limit, pdb=_get_pdb())
        results = [e for e in results if e["name"].lower() not in currency_names_shown]
        if results:
            found_any = True
            print(_h("Exchange Items"))
            for e in results:
                _fmt_exchange(e)
                print()

    if "descriptions" in types_to_search:
        pdb = _get_pdb()
        results = pdb.search_item_descs(keyword=query, category=args.category, limit=args.limit)
        if results:
            found_any = True
            print(_h("Item Descriptions"))
            for d in results:
                _fmt_item_desc(d)
                print()

    if not found_any:
        # Last resort: try fetching directly from poe2wiki.net
        try:
            from poe2_crafting_mcp.data.wiki_client import Poe2WikiClient
            pdb = _get_pdb()
            wiki = Poe2WikiClient()
            item = pdb.get_item_desc_or_fetch(query, wiki_client=wiki)
            if item:
                found_any = True
                print(_h("Item Descriptions (from poe2wiki.net)"))
                _fmt_item_desc(item)
                print()
        except Exception:
            pass

    if not found_any:
        print(f"No results found for '{query}'.")


if __name__ == "__main__":
    main()
