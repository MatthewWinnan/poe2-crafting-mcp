"""CLI for the crafting optimizer.

Usage:
    poe2-optimize "Gloves_int" --target "IncreasedEnergyShield:prefix:1, IncreasedMaximumLife:prefix:2, FireResistance:suffix:2"
    poe2-optimize "Boots_dex" --target "MovementSpeed:prefix:1" --budget 500
    poe2-optimize "Gloves_int" --target "IncreasedES:prefix:1" --base-item "fractured:IncreasedES:220"
    poe2-optimize "Amulets" --target "CritChance:suffix:1" --trade-price 300

Options:
    --target       Comma-separated "Family:affix:tier" specs
    --ilvl         Item level (default 82)
    --budget       Max chaos budget (for FAIL threshold)
    --trade-price  Known trade price for finished item (for CRAFT vs BUY verdict)
    --base-price   Price of a white base in chaos (default 1c). Also sets scour/reforge costs.
    --base-item    Starting item: "fractured:Family:Price" or "magic:Family:Price" or "white:Price"
    --pop-size     Population size (default 200)
    --generations  Max generations (default 50)
    --trials       MC trials per evaluation (default 500)
    --quick        Quick mode: pop=50, gen=10, trials=200
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="poe2-optimize",
        description="Find optimal crafting strategies via evolutionary optimization",
    )
    parser.add_argument(
        "item_class",
        help="Item class slug (e.g. Gloves_int) or base item name (e.g. 'Stitched Gloves')",
    )
    parser.add_argument(
        "--target", "-t", required=True,
        help="Target mods: 'Family:affix:tier, ...' e.g. 'IncreasedES:prefix:1,FireRes:suffix:2'",
    )
    parser.add_argument("--ilvl", type=int, default=82, help="Item level (default 82)")
    parser.add_argument("--budget", type=float, default=None, help="Max chaos budget")
    parser.add_argument("--trade-price", type=float, default=None, help="Trade price for finished item")
    parser.add_argument(
        "--base-item", default=None,
        help="Starting base: 'fractured:Family:Price' or 'magic:Family:Price' or 'white:Price'",
    )
    parser.add_argument("--pop-size", type=int, default=200)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--trials", type=int, default=500)
    parser.add_argument("--quick", action="store_true", help="Quick mode (faster, less accurate)")
    parser.add_argument(
        "--decompose", action="store_true", default=None,
        help="Force sub-goal decomposition (auto for >3 targets)",
    )
    parser.add_argument(
        "--no-decompose", action="store_true",
        help="Force monolithic optimization (no decomposition)",
    )
    parser.add_argument(
        "--cooperative", "--cc", action="store_true",
        help="Use cooperative coevolution (Tier 2) instead of sequential decomposition",
    )
    parser.add_argument(
        "--hierarchical", "--t3", action="store_true",
        help="Use Tier 3 hierarchical GP (evolves target groupings + phase strategies)",
    )
    parser.add_argument(
        "--runes", default="",
        help="Comma-separated rune pools socketed on item (e.g. 'marksman,decay' or 'Kolr\\'s Hunt')",
    )
    parser.add_argument(
        "--base-price", type=float, default=None,
        help="Price of a white base in chaos (default: auto-lookup from trade data, fallback 1c)",
    )
    parser.add_argument(
        "--no-buy", action="store_true",
        help="Disable buy_magic/buy_base actions (craft from scratch only, no trade resets)",
    )

    args = parser.parse_args()

    # Resolve item_class: accept base names like "Stitched Gloves" or slugs like "Gloves_int"
    item_class, base_name = _resolve_item_class(args.item_class)

    # Parse targets
    target_mods = _parse_targets(args.target)
    if not target_mods:
        print("Error: no valid targets parsed. Format: 'Family:prefix|suffix:tier'", file=sys.stderr)
        sys.exit(1)

    # Quick mode overrides
    if args.quick:
        args.pop_size = 50
        args.generations = 10
        args.trials = 200

    # Import optimizer (deferred to avoid slow imports on --help)
    from poe2_crafting_mcp.crafting.optimizer.preflight import preflight, lookup_display_info
    from poe2_crafting_mcp.crafting.optimizer.runner import (
        optimize, optimize_multi_target, optimize_cooperative,
        optimize_hierarchical, OptimizerConfig,
    )
    from poe2_crafting_mcp.crafting.optimizer.bridge import is_rust_available

    # Parse rune pools
    rune_pools = None
    if args.runes:
        from poe2_crafting_mcp.crafting.simulator import resolve_rune_pool
        rune_pools = []
        for r in args.runes.split(","):
            pool_name = resolve_rune_pool(r.strip())
            if pool_name:
                rune_pools.append(pool_name)
            else:
                print(f"  Warning: unknown rune '{r.strip()}'", file=sys.stderr)
        if not rune_pools:
            rune_pools = None

    # Decide decomposition mode
    use_decompose = args.decompose
    if args.no_decompose:
        use_decompose = False
    elif use_decompose is None:
        use_decompose = len(target_mods) >= 4

    # Look up human-readable names
    display = lookup_display_info(item_class, target_mods)
    item_label = display["item_class_name"]
    if base_name:
        item_label += f" ({base_name})"
    elif display["example_base"]:
        item_label += f" (e.g. {display['example_base']})"

    print(f"PoE2 Crafting Optimizer")
    print(f"{'─' * 50}")
    print(f"  Item:    {item_label}  ilvl {args.ilvl}")
    print(f"  Targets:")
    desecrated_fams = display.get("desecrated_families", set())
    for family, affix, tier in target_mods:
        desc = display["mod_descriptions"].get(family, "")
        desc_str = f"  — {desc}" if desc else ""
        tier_label = "Abyss" if family in desecrated_fams else f"T{tier}"
        print(f"    {tier_label} {family} ({affix}){desc_str}")
    print(f"  Engine:  {'Rust (fast)' if is_rust_available() else 'Python stub (slow)'}")
    print(f"  Config:  pop={args.pop_size} gen={args.generations} trials={args.trials}")
    if args.hierarchical:
        print(f"  Mode:    Hierarchical GP (Tier 3, {len(target_mods)} targets)")
    elif use_decompose:
        mode = "Cooperative coevolution" if args.cooperative else "Sequential decomposition"
        print(f"  Mode:    {mode} ({len(target_mods)} targets)")
    if args.no_buy:
        print(f"  Buy:     disabled (craft from scratch only)")
    if rune_pools:
        from poe2_crafting_mcp.crafting.simulator import RUNE_POOL_NAMES
        rune_names = [RUNE_POOL_NAMES.get(p, p) for p in rune_pools]
        print(f"  Runes:   {', '.join(rune_names)}")
    print()

    # Preflight: fetch pool + prices from DB
    print("Fetching mod pool and prices...")
    pool_data, prices, target = preflight(item_class, args.ilvl, target_mods,
                                          rune_pools=rune_pools, base_name=base_name)

    print(f"  Pool: {len(pool_data['prefix_weights'])} prefix + {len(pool_data['suffix_weights'])} suffix tiers")
    print(f"  Prices: {len(prices.currency)} currencies, {len(prices.omen)} omens")

    # Apply base price if specified
    if args.base_price is not None:
        prices.base_white = args.base_price
        # Scouring = buying a new base, reforge = 2 spare bases
        prices.currency["scouring"] = args.base_price
        prices.currency["reforge"] = args.base_price * 2

    # Apply base-item if specified
    if args.base_item:
        _apply_base_item(args.base_item, prices, target)

    # Apply trade price if specified
    if args.trade_price:
        prices.trade_finished = args.trade_price

    # Show base and trade prices
    base_url = prices.trade_urls.get("base_white", "")
    base_url_str = f"  {base_url}" if base_url else ""
    print(f"  Base price: {prices.base_white:.1f}c{base_url_str}")
    if prices.trade_finished < float("inf"):
        fin_url = prices.trade_urls.get("trade_finished", "")
        fin_url_str = f"  {fin_url}" if fin_url else ""
        print(f"  Trade price: {prices.trade_finished:.1f}c{fin_url_str}")

    print()

    config = OptimizerConfig(
        pop_size=args.pop_size,
        max_generations=args.generations,
        mc_trials=args.trials,
        no_buy=args.no_buy,
    )

    if args.hierarchical:
        _run_hierarchical(pool_data, target, prices, config, force=True)
    elif use_decompose:
        # User explicitly requested decomposition — bypass target count threshold
        if args.cooperative:
            _run_cooperative(pool_data, target, prices, config, force=True)
        else:
            _run_decomposed(pool_data, target, prices, config, force=True)
    else:
        _run_monolithic(pool_data, target, prices, config)


def _run_monolithic(pool_data, target, prices, config) -> None:
    """Run monolithic (non-decomposed) optimization."""
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize

    print("Optimizing...")
    start = time.time()
    result = optimize(pool_data, target, prices, config)
    elapsed = time.time() - start

    print()
    print(f"{'═' * 50}")
    print(f"  RESULTS ({elapsed:.1f}s, {result.evaluations:,} evaluations)")
    print(f"{'═' * 50}")
    print()

    if prices.trade_finished < float("inf"):
        print(f"  Trade price: {prices.trade_finished:.1f}c")
    print(f"  Verdict: {result.best_verdict}")
    print(f"  Archive: {result.archive_coverage:.0%} coverage ({len(result.archive_strategies)} families)")
    print()

    if result.strategies:
        print(f"  {'Strategy':<30s} {'Total':>7s} {'Base':>6s} {'Orbs':>6s} {'Success':>8s} {'p90':>6s}  Verdict")
        print(f"  {'─' * 30} {'─' * 7} {'─' * 6} {'─' * 6} {'─' * 8} {'─' * 6}  {'─' * 7}")
        seen_families: set[str] = set()
        for s in result.strategies:
            if s.family_name in seen_families:
                continue
            seen_families.add(s.family_name)
            print(
                f"  {s.family_name:<30s} {s.expected_cost:>6.0f}c {s.base_acquisition_cost:>5.0f}c "
                f"{s.currency_cost:>5.0f}c {s.success_rate:>7.0%} {s.cost_p90:>5.0f}c  {s.verdict}"
            )
        print()

        best = result.strategies[0]
        print(f"  Best Strategy: {best.family_name}")
        print(f"  {'─' * 40}")
        for step in best.steps:
            print(f"    {step}")
    else:
        print("  No viable strategies found.")

    print()


def _run_decomposed(pool_data, target, prices, config, force: bool = False) -> None:
    """Run sub-goal decomposed optimization."""
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_multi_target

    print("Decomposing targets and optimizing phases...")
    start = time.time()
    threshold = 1 if force else 4
    result = optimize_multi_target(pool_data, target, prices, config,
                                   decompose_threshold=threshold)
    elapsed = time.time() - start

    print()
    print(f"{'═' * 60}")
    print(f"  DECOMPOSED RESULTS ({elapsed:.1f}s)")
    print(f"{'═' * 60}")
    print()

    print(f"  Ordering: {result.ordering_rationale}")
    print()

    # Per-phase breakdown
    print(f"  {'Phase':<6s} {'Target':<25s} {'Cost':>8s} {'Success':>8s} {'Risk':<12s} {'Cumulative':>10s}")
    print(f"  {'─' * 6} {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 12} {'─' * 10}")
    for pr in result.phases:
        target_name = pr.phase_target.targets[0].family if pr.phase_target.targets else "?"
        print(
            f"  {pr.phase_index:<6d} {target_name:<25s} {pr.expected_cost:>7.0f}c "
            f"{pr.success_rate:>7.0%} {pr.restart_risk:<12s} {pr.cumulative_cost:>9.0f}c"
        )
    print()

    print(f"  Total expected cost: {result.total_expected_cost:.0f}c")
    print(f"  Combined success rate: {result.total_success_rate:.2%}")
    if result.trade_price < float("inf"):
        print(f"  Trade price: {result.trade_price:.1f}c")
    print(f"  Verdict: {result.verdict}")
    print()

    # Show each phase's best strategy
    for pr in result.phases:
        target_name = pr.phase_target.targets[0].family if pr.phase_target.targets else "?"
        print(f"  Phase {pr.phase_index}: {target_name} ({pr.expected_cost:.0f}c, {pr.success_rate:.0%})")
        print(f"  Strategy: {pr.strategy.family_name}")
        print(f"  {'─' * 40}")
        for step in pr.strategy.steps:
            print(f"    {step}")
        print()


def _run_cooperative(pool_data, target, prices, config, force: bool = False) -> None:
    """Run cooperative coevolution optimization."""
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_cooperative

    print("Running cooperative coevolution...")
    start = time.time()
    threshold = 1 if force else 4
    result = optimize_cooperative(pool_data, target, prices, config,
                                  decompose_threshold=threshold)
    elapsed = time.time() - start

    print()
    print(f"{'═' * 60}")
    print(f"  CC RESULTS ({elapsed:.1f}s)")
    print(f"{'═' * 60}")
    print()

    print(f"  Ordering: {result.ordering_rationale}")
    print()

    # Per-phase breakdown (same format as sequential)
    print(f"  {'Phase':<6s} {'Target':<25s} {'Cost':>8s} {'Success':>8s} {'Risk':<12s} {'Cumulative':>10s}")
    print(f"  {'─' * 6} {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 12} {'─' * 10}")
    for pr in result.phases:
        target_name = pr.phase_target.targets[0].family if pr.phase_target.targets else "?"
        print(
            f"  {pr.phase_index:<6d} {target_name:<25s} {pr.expected_cost:>7.0f}c "
            f"{pr.success_rate:>7.0%} {pr.restart_risk:<12s} {pr.cumulative_cost:>9.0f}c"
        )
    print()

    print(f"  Total expected cost: {result.total_expected_cost:.0f}c")
    print(f"  Combined success rate: {result.total_success_rate:.2%}")
    if result.trade_price < float("inf"):
        print(f"  Trade price: {result.trade_price:.1f}c")
    print(f"  Verdict: {result.verdict}")
    print()

    for pr in result.phases:
        target_name = pr.phase_target.targets[0].family if pr.phase_target.targets else "?"
        print(f"  Phase {pr.phase_index}: {target_name} ({pr.expected_cost:.0f}c, {pr.success_rate:.0%})")
        print(f"  Strategy: {pr.strategy.family_name}")
        print(f"  {'─' * 40}")
        for step in pr.strategy.steps:
            print(f"    {step}")
        print()


def _run_hierarchical(pool_data, target, prices, config, force: bool = False) -> None:
    """Run Tier 3 hierarchical GP optimization."""
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_hierarchical

    print("Running hierarchical GP (evolving target groupings)...")
    start = time.time()
    threshold = 1 if force else 4
    result = optimize_hierarchical(pool_data, target, prices, config,
                                    decompose_threshold=threshold)
    elapsed = time.time() - start

    print()
    print(f"{'═' * 60}")
    print(f"  HIERARCHICAL GP RESULTS ({elapsed:.1f}s)")
    print(f"{'═' * 60}")
    print()

    print(f"  Grouping: {result.ordering_rationale}")
    print()

    # Per-phase breakdown — show multi-target groups
    print(f"  {'Phase':<6s} {'Targets':<30s} {'Cost':>8s} {'Success':>8s} {'Risk':<12s} {'Cumulative':>10s}")
    print(f"  {'─' * 6} {'─' * 30} {'─' * 8} {'─' * 8} {'─' * 12} {'─' * 10}")
    for pr in result.phases:
        target_names = ", ".join(t.family for t in pr.phase_target.targets)
        if len(target_names) > 28:
            target_names = target_names[:25] + "..."
        print(
            f"  {pr.phase_index:<6d} {target_names:<30s} {pr.expected_cost:>7.0f}c "
            f"{pr.success_rate:>7.0%} {pr.restart_risk:<12s} {pr.cumulative_cost:>9.0f}c"
        )
    print()

    print(f"  Total expected cost: {result.total_expected_cost:.0f}c")
    print(f"  Combined success rate: {result.total_success_rate:.2%}")
    if result.trade_price < float("inf"):
        print(f"  Trade price: {result.trade_price:.1f}c")
    print(f"  Verdict: {result.verdict}")
    print()

    for pr in result.phases:
        target_names = ", ".join(t.family for t in pr.phase_target.targets)
        print(f"  Phase {pr.phase_index}: {target_names} ({pr.expected_cost:.0f}c, {pr.success_rate:.0%})")
        print(f"  Strategy: {pr.strategy.family_name}")
        print(f"  {'─' * 40}")
        for step in pr.strategy.steps:
            print(f"    {step}")
        print()


def _resolve_item_class(user_input: str) -> tuple[str, str | None]:
    """Resolve user input to (item_class_slug, base_name).

    Accepts either an item_class slug ("Gloves_int") or a base item name
    ("Stitched Gloves"). Returns the resolved item_class slug and the
    specific base name (or None if a slug was given directly).
    """
    import json
    import os
    import sqlite3

    # If it looks like a slug (no spaces, has underscores or is single word
    # matching known patterns), use it directly
    if " " not in user_input:
        return user_input, None

    # Search item_bases by name
    db_path = os.environ.get("POE2_CRAFT_DB", "data/poe2_craft.db")
    if not os.path.exists(db_path):
        print(f"  Warning: DB not found, treating '{user_input}' as item_class slug", file=sys.stderr)
        return user_input.replace(" ", "_"), None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT name, slot, tags FROM item_bases WHERE name = ? LIMIT 1",
        (user_input,),
    ).fetchone()

    if not row:
        # Try case-insensitive LIKE search
        row = conn.execute(
            "SELECT name, slot, tags FROM item_bases WHERE name LIKE ? LIMIT 1",
            (user_input,),
        ).fetchone()

    conn.close()

    if not row:
        print(f"  Warning: base '{user_input}' not found in DB, treating as item_class slug", file=sys.stderr)
        return user_input.replace(" ", "_"), None

    base_name = row["name"]
    slot = row["slot"]
    tags = json.loads(row["tags"]) if row["tags"] else []

    from poe2_crafting_mcp.data.poe2db_client import base_tags_to_item_class

    item_class = base_tags_to_item_class(slot, tags)
    if not item_class:
        print(f"  Warning: could not resolve item_class for '{base_name}' (slot={slot})", file=sys.stderr)
        return user_input.replace(" ", "_"), None

    print(f"  Resolved '{base_name}' → {item_class}")
    return item_class, base_name


def _parse_targets(target_str: str) -> list[tuple[str, str, int]]:
    """Parse 'Family:affix:tier, Family:affix:tier' into list of tuples."""
    targets = []
    for part in target_str.split(","):
        part = part.strip()
        if not part:
            continue
        pieces = part.split(":")
        if len(pieces) != 3:
            print(f"  Warning: skipping malformed target '{part}' (need Family:affix:tier)", file=sys.stderr)
            continue
        family = pieces[0].strip()
        affix = pieces[1].strip().lower()
        try:
            tier = int(pieces[2].strip())
        except ValueError:
            print(f"  Warning: skipping '{part}' (tier must be integer)", file=sys.stderr)
            continue
        if affix not in ("prefix", "suffix"):
            print(f"  Warning: affix must be 'prefix' or 'suffix', got '{affix}'", file=sys.stderr)
            continue
        targets.append((family, affix, tier))
    return targets


def _apply_base_item(base_spec: str, prices, target) -> None:
    """Parse and apply a base-item specification to the price cache.

    Formats:
        "fractured:FamilyName:220"  → start from fractured base costing 220c
        "magic:FamilyName:35"       → start from magic base with mod costing 35c
        "white:2"                   → start from white base costing 2c
    """
    parts = base_spec.split(":")
    if len(parts) < 2:
        print(f"  Warning: invalid --base-item format: '{base_spec}'", file=sys.stderr)
        return

    base_type = parts[0].lower()

    if base_type == "white":
        price = float(parts[1]) if len(parts) > 1 else 1.0
        prices.base_white = price
        print(f"  Base: white ({price:.0f}c)")

    elif base_type == "magic":
        if len(parts) < 3:
            print(f"  Warning: magic base needs 'magic:Family:Price'", file=sys.stderr)
            return
        family = parts[1]
        price = float(parts[2])
        prices.base_magic_with[family] = price
        print(f"  Base: magic with {family} ({price:.0f}c)")

    elif base_type == "fractured":
        if len(parts) < 3:
            print(f"  Warning: fractured base needs 'fractured:Family:Price'", file=sys.stderr)
            return
        family = parts[1]
        price = float(parts[2])
        prices.base_fractured_with[family] = price
        print(f"  Base: fractured {family} ({price:.0f}c)")

    else:
        print(f"  Warning: unknown base type '{base_type}' (use white/magic/fractured)", file=sys.stderr)


if __name__ == "__main__":
    main()
