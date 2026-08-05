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
    parser.add_argument("item_class", help="Item class slug (e.g. Gloves_int, Boots_dex, Amulets)")
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
        "--runes", default="",
        help="Comma-separated rune pools socketed on item (e.g. 'marksman,decay' or 'Kolr\\'s Hunt')",
    )

    args = parser.parse_args()

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
        optimize, optimize_multi_target, optimize_cooperative, OptimizerConfig,
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
    display = lookup_display_info(args.item_class, target_mods)
    item_label = display["item_class_name"]
    if display["example_base"]:
        item_label += f" (e.g. {display['example_base']})"

    print(f"PoE2 Crafting Optimizer")
    print(f"{'─' * 50}")
    print(f"  Item:    {item_label}  ilvl {args.ilvl}")
    print(f"  Targets:")
    for family, affix, tier in target_mods:
        desc = display["mod_descriptions"].get(family, "")
        desc_str = f"  — {desc}" if desc else ""
        print(f"    T{tier} {family} ({affix}){desc_str}")
    print(f"  Engine:  {'Rust (fast)' if is_rust_available() else 'Python stub (slow)'}")
    print(f"  Config:  pop={args.pop_size} gen={args.generations} trials={args.trials}")
    if use_decompose:
        mode = "Cooperative coevolution" if args.cooperative else "Sequential decomposition"
        print(f"  Mode:    {mode} ({len(target_mods)} targets)")
    if rune_pools:
        from poe2_crafting_mcp.crafting.simulator import RUNE_POOL_NAMES
        rune_names = [RUNE_POOL_NAMES.get(p, p) for p in rune_pools]
        print(f"  Runes:   {', '.join(rune_names)}")
    print()

    # Preflight: fetch pool + prices from DB
    print("Fetching mod pool and prices...")
    pool_data, prices, target = preflight(args.item_class, args.ilvl, target_mods,
                                          rune_pools=rune_pools)

    print(f"  Pool: {len(pool_data['prefix_weights'])} prefix + {len(pool_data['suffix_weights'])} suffix tiers")
    print(f"  Prices: {len(prices.currency)} currencies, {len(prices.omen)} omens")

    # Apply base-item if specified
    if args.base_item:
        _apply_base_item(args.base_item, prices, target)

    # Apply trade price if specified
    if args.trade_price:
        prices.trade_finished = args.trade_price
        print(f"  Trade price: {args.trade_price:.0f}c")

    print()

    config = OptimizerConfig(
        pop_size=args.pop_size,
        max_generations=args.generations,
        mc_trials=args.trials,
    )

    if use_decompose:
        if args.cooperative:
            _run_cooperative(pool_data, target, prices, config)
        else:
            _run_decomposed(pool_data, target, prices, config)
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
        print(f"  Trade price: {prices.trade_finished:.0f}c")
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


def _run_decomposed(pool_data, target, prices, config) -> None:
    """Run sub-goal decomposed optimization."""
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_multi_target

    print("Decomposing targets and optimizing phases...")
    start = time.time()
    result = optimize_multi_target(pool_data, target, prices, config)
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
        print(f"  Trade price: {result.trade_price:.0f}c")
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


def _run_cooperative(pool_data, target, prices, config) -> None:
    """Run cooperative coevolution optimization."""
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_cooperative

    print("Running cooperative coevolution...")
    start = time.time()
    result = optimize_cooperative(pool_data, target, prices, config)
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
        print(f"  Trade price: {result.trade_price:.0f}c")
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
