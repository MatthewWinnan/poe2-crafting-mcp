"""
CLI for inspecting PoB builds.

Usage:
    pob-inspect <build_file> [options]

Examples:
    pob-inspect data/builds/martial_artist.txt
    pob-inspect data/builds/martial_artist.txt --items --keystones
    pob-inspect data/builds/martial_artist.txt --export
    pob-inspect data/builds/martial_artist.txt --export --export-file out.txt
    pob-inspect data/builds/martial_artist.txt --all
"""

import argparse
import os
import sys
from pathlib import Path


POB_PATH = Path(__file__).parent.parent.parent.parent / "vendor" / "PathOfBuilding-PoE2"


def _fmt_res(value: float) -> str:
    color = "\033[32m" if value >= 75 else "\033[31m"
    return f"{color}{value:.0f}%\033[0m"


def _fmt_change(value: float) -> str:
    if value > 0:
        return f"\033[32m+{value:,.0f}\033[0m"
    elif value < 0:
        return f"\033[31m{value:,.0f}\033[0m"
    return f"{value:,.0f}"


def _section(title: str) -> None:
    print(f"\n\033[1;33m── {title} {'─' * (50 - len(title))}\033[0m")


def show_info(info: object) -> None:
    _section("Build")
    print(f"  Class:  {info.ascendancy} ({info.class_name})")  # type: ignore[attr-defined]
    print(f"  Level:  {info.level}")  # type: ignore[attr-defined]
    print(f"  Skill:  {info.main_skill}")  # type: ignore[attr-defined]
    print(f"  Tree:   {info.total_allocated} nodes  ({info.keystone_count} keystones, {info.notable_count} notables)")  # type: ignore[attr-defined]


def show_stats(stats: object) -> None:
    _section("Offence")
    print(f"  DPS:          {stats.total_dps:>15,.0f}")  # type: ignore[attr-defined]
    print(f"  Crit Chance:  {stats.crit_chance:>14.2f}%")  # type: ignore[attr-defined]
    print(f"  Crit Multi:   {stats.crit_multiplier:>14.2f}%")  # type: ignore[attr-defined]
    print(f"  Hit Chance:   {stats.hit_chance:>14.2f}%")  # type: ignore[attr-defined]
    print(f"  Attack Speed: {stats.speed:>14.2f}")  # type: ignore[attr-defined]

    if any([stats.phys_dps, stats.fire_dps, stats.cold_dps, stats.lightning_dps, stats.chaos_dps]):  # type: ignore[attr-defined]
        _section("Damage Breakdown")
        for label, val in [
            ("Physical", stats.phys_dps), ("Fire", stats.fire_dps),  # type: ignore[attr-defined]
            ("Cold", stats.cold_dps), ("Lightning", stats.lightning_dps),  # type: ignore[attr-defined]
            ("Chaos", stats.chaos_dps),  # type: ignore[attr-defined]
        ]:
            if val > 0:
                print(f"  {label:<12}  {val:>12,.0f}")

    _section("Defence")
    print(f"  Life:         {stats.life:>15,.0f}")  # type: ignore[attr-defined]
    print(f"  Energy Shield:{stats.energy_shield:>15,.0f}")  # type: ignore[attr-defined]
    if stats.ward > 0:  # type: ignore[attr-defined]
        print(f"  Ward:         {stats.ward:>15,.0f}")  # type: ignore[attr-defined]
    print(f"  Mana:         {stats.mana:>15,.0f}")  # type: ignore[attr-defined]
    print(f"  Evasion:      {stats.evasion:>15,.0f}")  # type: ignore[attr-defined]
    print(f"  Armour:       {stats.armour:>15,.0f}")  # type: ignore[attr-defined]
    if stats.block_chance > 0:  # type: ignore[attr-defined]
        print(f"  Block:        {stats.block_chance:>14.1f}%")  # type: ignore[attr-defined]
    if stats.spell_block_chance > 0:  # type: ignore[attr-defined]
        print(f"  Spell Block:  {stats.spell_block_chance:>14.1f}%")  # type: ignore[attr-defined]

    _section("Resistances")
    print(f"  Fire:         {_fmt_res(stats.fire_res)}")  # type: ignore[attr-defined]
    print(f"  Cold:         {_fmt_res(stats.cold_res)}")  # type: ignore[attr-defined]
    print(f"  Lightning:    {_fmt_res(stats.lightning_res)}")  # type: ignore[attr-defined]
    print(f"  Chaos:        {_fmt_res(stats.chaos_res)}")  # type: ignore[attr-defined]


def show_items(engine: object) -> None:
    _section("Equipped Items")
    items = engine.get_equipped_items()  # type: ignore[attr-defined]
    for slot, item in items.items():
        if item is None:
            print(f"  {slot:<14}  \033[90m(empty)\033[0m")
        else:
            rarity_colors = {
                "NORMAL": "\033[37m",
                "MAGIC": "\033[34m",
                "RARE": "\033[33m",
                "UNIQUE": "\033[35m",
            }
            color = rarity_colors.get(item.rarity, "\033[37m")
            print(f"  {slot:<14}  {color}{item.name or item.base_type}\033[0m  \033[90milvl {item.item_level}\033[0m")


def show_gems(engine: object) -> None:
    _section("Socket Groups")
    groups = engine.get_socket_groups()  # type: ignore[attr-defined]
    if not groups:
        print("  (none)")
        return
    for group in groups:
        enabled_tag = "" if group.enabled else " \033[90m[disabled]\033[0m"
        fulldps_tag = " \033[36m[full DPS]\033[0m" if group.include_in_full_dps else ""
        slot_tag = f" \033[90m({group.slot})\033[0m" if group.slot else ""
        print(f"  \033[1m{group.label}\033[0m{slot_tag}{enabled_tag}{fulldps_tag}")
        for gem in group.gems:
            corrupt_tag = ""
            if gem.corrupted:
                sign = f"+{gem.corrupt_level}" if gem.corrupt_level > 0 else str(gem.corrupt_level)
                corrupt_tag = f" \033[31mC{sign if gem.corrupt_level != 0 else ''}\033[0m"
            type_tag = "\033[90m[S]\033[0m" if gem.is_support else "\033[33m[A]\033[0m"
            disabled_tag = " \033[90m(off)\033[0m" if not gem.enabled else ""
            print(f"    {type_tag} {gem.name:<36} L{gem.level} Q{gem.quality}{corrupt_tag}{disabled_tag}")


def show_jewels(engine: object) -> None:
    _section("Tree Jewels")
    jewels = engine.get_tree_jewels()  # type: ignore[attr-defined]
    if not jewels:
        print("  (none socketed)")
        return
    for j in jewels:
        corrupt_tag = " \033[31m[corrupted]\033[0m" if j.corrupted else ""
        print(f"  \033[33m{j.name or j.base_type}\033[0m{corrupt_tag}  \033[90mnode {j.node_id}\033[0m")
        for mod in j.explicit_mods[:4]:
            print(f"    \033[90m{mod}\033[0m")


def show_keystones(engine: object) -> None:
    _section("Keystones")
    keystones = engine.get_keystones()  # type: ignore[attr-defined]
    if keystones:
        for k in keystones:
            print(f"  • {k}")
    else:
        print("  (none allocated)")


def show_notables(engine: object) -> None:
    _section("Notables")
    notables = engine.get_notables()  # type: ignore[attr-defined]
    if notables:
        for n in notables:
            print(f"  • {n}")
    else:
        print("  (none allocated)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pob-inspect",
        description="Inspect a PoB build file and display stats.",
    )
    parser.add_argument("build_file", help="Path to build file (share code .txt or .xml)")
    parser.add_argument("--stats", action="store_true", help="Show offence/defence stats")
    parser.add_argument("--items", action="store_true", help="Show equipped gear")
    parser.add_argument("--gems", action="store_true", help="Show socket groups with gem details")
    parser.add_argument("--jewels", action="store_true", help="Show jewels socketed in passive tree")
    parser.add_argument("--keystones", action="store_true", help="Show keystone passives")
    parser.add_argument("--notables", action="store_true", help="Show notable passives")
    parser.add_argument("--export", action="store_true", help="Print the PoB share code")
    parser.add_argument("--export-file", metavar="FILE", help="Save share code to a file")
    parser.add_argument("--all", dest="show_all", action="store_true", help="Show everything")
    parser.add_argument("--skill", type=int, metavar="N", help="Select skill by index (1-based) before calculating")
    parser.add_argument("--skills", action="store_true", help="List all available skills and exit")
    parser.add_argument("--pob-path", default=str(POB_PATH), help="Override PoB-PoE2 repo path")

    args = parser.parse_args()

    # Default: show info + stats if no display flags are given
    explicit_flags = any([args.stats, args.items, args.gems, args.jewels, args.keystones, args.notables, args.show_all])
    show_info_section = not explicit_flags or args.show_all
    show_stats_section = not explicit_flags or args.stats or args.show_all
    show_items_section = args.items or args.show_all
    show_gems_section = args.gems or args.show_all
    show_jewels_section = args.jewels or args.show_all
    show_keystones_section = args.keystones or args.show_all
    show_notables_section = args.notables or args.show_all

    from poe2_crafting_mcp.engine.pob_engine import PoBEngine

    pob_path = Path(args.pob_path)
    if not pob_path.is_absolute():
        pob_path = Path(os.getcwd()) / pob_path

    print(f"\033[1mLoading:\033[0m {args.build_file}")
    engine = PoBEngine(pob_path)
    engine.load_build_from_file(args.build_file)

    # List skills and exit if requested
    if args.skills:
        _section("Available Skills")
        current = engine.get_build_info().main_skill
        for i, name in enumerate(engine.get_skill_list(), 1):
            marker = " \033[32m◀ active\033[0m" if name == current else ""
            print(f"  {i:>2}.  {name}{marker}")
        print()
        sys.exit(0)

    # Switch active skill before calculating if requested
    if args.skill is not None:
        engine.set_main_skill(args.skill)

    info = engine.get_build_info()
    stats = engine.get_stats()

    if show_info_section:
        show_info(info)
    if show_stats_section:
        show_stats(stats)
    if show_items_section:
        show_items(engine)
    if show_gems_section:
        show_gems(engine)
    if show_jewels_section:
        show_jewels(engine)
    if show_keystones_section:
        show_keystones(engine)
    if show_notables_section:
        show_notables(engine)

    if args.export or args.export_file:
        code = engine.export_build_code()
        if args.export:
            _section("Share Code")
            print(f"  {code}")
        if args.export_file:
            Path(args.export_file).write_text(code)
            print(f"\n\033[32mShare code saved to {args.export_file}\033[0m")

    print()


if __name__ == "__main__":
    main()
