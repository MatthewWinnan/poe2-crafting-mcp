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
    print(f"  {_BOLD}{c['name']}{_RESET}{cat}")
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
    n = pdb.upsert_concepts_bulk(CONCEPTS)
    cs = pdb.concept_status()
    print(f"{_GREEN}✓ Seeded {n} concepts from built-in definitions.{_RESET}")
    print(f"  {_BOLD}Total in DB:{_RESET} {cs.get('total', 0)}")
    return 0


_CONCEPT_CMDS = {
    "concept-status":  _cmd_concept_status,
    "concept-list":    _cmd_concept_list,
    "concept-search":  _cmd_concept_search,
    "concept-get":     _cmd_concept_get,
    "concept-add":     _cmd_concept_add,
    "concept-delete":  _cmd_concept_delete,
    "concept-refresh": _cmd_concept_refresh,
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
    args = p.parse_args(argv)
    name = " ".join(args.name)
    d = _get_pdb().get_item_desc(name)
    if not d:
        print(f"{_RED}No description for '{name}'.{_RESET}", file=sys.stderr)
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
    from poe2_crafting_mcp.data.item_descriptions import ITEM_DESCRIPTIONS
    pdb = _get_pdb()
    n = pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)
    ds = pdb.item_desc_status()
    print(f"{_GREEN}✓ Seeded {n} item descriptions from built-in definitions.{_RESET}")
    print(f"  {_BOLD}Total in DB:{_RESET} {ds.get('total', 0)}")
    return 0


_ITEM_DESC_CMDS = {
    "item-desc-status":  _cmd_item_desc_status,
    "item-desc-list":    _cmd_item_desc_list,
    "item-desc-get":     _cmd_item_desc_get,
    "item-desc-add":     _cmd_item_desc_add,
    "item-desc-delete":  _cmd_item_desc_delete,
    "item-desc-refresh": _cmd_item_desc_refresh,
}


# ── Main ──────────────────────────────────────────────────────────────────────

_ALL_TYPES = ("bases", "mods", "gems", "uniques", "nodes", "currencies",
              "concepts", "exchange", "descriptions")

_TYPE_ALIASES: dict[str, str] = {
    "base": "bases", "item": "bases", "items": "bases",
    "mod": "mods", "affix": "mods", "affixes": "mods", "craft": "mods",
    "gem": "gems", "skill": "gems", "skills": "gems",
    "unique": "uniques",
    "node": "nodes", "passive": "nodes", "passives": "nodes", "tree": "nodes",
    "currency": "currencies", "orb": "currencies",
    "concept": "concepts", "keyword": "concepts", "keywords": "concepts",
    "mechanic": "concepts", "mechanics": "concepts", "definition": "concepts",
    "rune": "exchange", "essence": "exchange", "catalyst": "exchange",
    "delirium": "exchange", "breach": "exchange", "abyss": "exchange",
    "liquid": "exchange", "wombgift": "exchange", "fragment": "exchange",
    "soulcore": "exchange", "soul_core": "exchange",
    "desc": "descriptions", "description": "descriptions",
    "item-desc": "descriptions", "foci": "descriptions",
    "focus": "descriptions", "jewellery": "descriptions", "jewelry": "descriptions",
    "shield": "descriptions", "quiver": "descriptions",
}


def main() -> None:
    # Pre-dispatch: management subcommands bypass the query parser
    if len(sys.argv) > 1:
        _cmd = sys.argv[1]
        _dispatch = {**_CONCEPT_CMDS, **_ITEM_DESC_CMDS}
        if _cmd in _dispatch:
            sys.exit(_dispatch[_cmd](sys.argv[2:]) or 0)

    parser = argparse.ArgumentParser(
        prog="poe2-lookup",
        description=(
            "Search PoE2 game data: bases, mods, gems, uniques, passive nodes, "
            "currencies, concepts/keywords, and item descriptions.\n\n"
            "Also supports management subcommands (run without query):\n"
            "  concept-status/list/search/get/add/delete/refresh\n"
            "  item-desc-status/list/get/add/delete/refresh"
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
            "  poe2-lookup 'chaos orb' --type descriptions    crafting notes for Chaos Orb\n"
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
            "Values: bases, mods, gems, uniques, nodes, currencies, concepts, "
            "exchange, descriptions.\n"
            "Aliases: base, mod, gem, unique, node, currency, concept, "
            "keyword, mechanic, rune, essence, desc, foci, focus, jewellery, shield, quiver."
        ),
    )
    parser.add_argument("--slot", "-s", default="",
                        help="Item slot filter for bases/uniques (e.g. Gloves, Ring)")
    parser.add_argument("--tag", default="",
                        help="Item tag filter for mods/bases (e.g. staff, ring, int_armour)")
    parser.add_argument("--category", "-c", default="",
                        help="Mod category: Item (default), Jewel, Runes, Corruption, Desecrated, Flask, Charm")
    parser.add_argument("--min-level", type=int, default=0,
                        help="Minimum ilvl for bases (default 0)")
    parser.add_argument("--max-level", type=int, default=100,
                        help="Maximum ilvl for bases (default 100)")
    parser.add_argument("--limit", "-l", type=int, default=10,
                        help="Max results per section (default 10)")
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
            print(_h("Item Bases"))
            for b in results:
                desc = pdb.get_item_desc(b["name"])
                _fmt_base(b, desc=desc)
                print()

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
        results = search_exchange_items(keyword=query, limit=args.limit)
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
        print(f"No results found for '{query}'.")


if __name__ == "__main__":
    main()
