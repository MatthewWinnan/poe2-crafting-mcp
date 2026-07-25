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

def _fmt_base(b: dict) -> None:
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


def _fmt_mod(m: dict) -> None:
    mt = m.get("mod_type", "")
    cat = m.get("category", "")
    color = _CYAN if mt == "Prefix" else _GREEN
    label = f"{color}{mt}{_RESET}" if mt else ""
    cat_label = f"  {_DIM}{cat}{_RESET}" if cat and cat != "Item" else ""
    affix = f"  {_DIM}«{m['affix']}»{_RESET}" if m.get("affix") else ""
    print(f"  {label}{cat_label}{affix}")
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


def _fmt_currency(c: dict) -> None:
    cat = f"  {_DIM}[{c.get('category','')}]{_RESET}"
    sub = f"  {_DIM}{c.get('subcategory','')}{_RESET}" if c.get("subcategory") else ""
    print(f"  {_BOLD}{c['name']}{_RESET}{cat}{sub}")
    if c.get("effect"):
        print(f"    {c['effect']}")


# ── Main ──────────────────────────────────────────────────────────────────────

_ALL_TYPES = ("bases", "mods", "gems", "uniques", "nodes", "currencies")

_TYPE_ALIASES: dict[str, str] = {
    "base": "bases", "item": "bases", "items": "bases",
    "mod": "mods", "affix": "mods", "affixes": "mods", "craft": "mods",
    "gem": "gems", "skill": "gems", "skills": "gems",
    "unique": "uniques",
    "node": "nodes", "passive": "nodes", "passives": "nodes", "tree": "nodes",
    "currency": "currencies", "orb": "currencies", "essence": "currencies",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="poe2-lookup",
        description="Search PoE2 game data: bases, mods, gems, uniques, passive nodes, currencies.",
    )
    parser.add_argument("query", nargs="+", help="Search term(s)")
    parser.add_argument(
        "--type", "-t", dest="types", metavar="TYPE",
        help=f"Limit to: {', '.join(_ALL_TYPES)}. Comma-separated for multiple.",
    )
    parser.add_argument("--slot", "-s", default="",
                        help="Item slot filter for bases/uniques (e.g. Gloves, Ring)")
    parser.add_argument("--tag", default="",
                        help="Item tag filter for mods (e.g. staff, ring, str_armour)")
    parser.add_argument("--category", "-c", default="",
                        help="Mod category: Item (default), Jewel, Runes, Corruption, Flask")
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
        results = db.search_bases(slot=args.slot, min_level=0, max_level=100, limit=args.limit)
        # FTS not on bases — filter by name substring
        results = [b for b in results if query.lower() in b["name"].lower()]
        if results:
            found_any = True
            print(_h("Item Bases"))
            for b in results:
                _fmt_base(b)
                print()

    if "mods" in types_to_search:
        cat = args.category or "Item"
        results = db.search_mods(keyword=query, item_tag=args.tag,
                                 category=cat, limit=args.limit)
        if results:
            found_any = True
            print(_h(f"Mods ({cat})"))
            for m in results:
                _fmt_mod(m)
                print()
        # Also search other categories if no specific category was given
        if not args.category:
            for extra_cat in ("Jewel", "Runes", "Corruption"):
                extra = db.search_mods(keyword=query, item_tag=args.tag,
                                       category=extra_cat, limit=5)
                if extra:
                    found_any = True
                    print(_h(f"Mods ({extra_cat})"))
                    for m in extra:
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

    if "currencies" in types_to_search:
        results = db.search_currencies(keyword=query)
        if results:
            found_any = True
            print(_h("Currencies"))
            for c in results:
                _fmt_currency(c)
                print()

    if not found_any:
        print(f"No results found for '{query}'.")


if __name__ == "__main__":
    main()
