"""Top-level optimizer runner.

Orchestrates the full GP loop:
  init → evaluate → select → breed → archive → repeat → cluster → output

Provides three multi-target strategies:
- optimize(): monolithic single-population GP (best for 1-3 targets)
- optimize_multi_target(): Tier 1 sequential decomposition (independent phases)
- optimize_cooperative(): Tier 2 cooperative coevolution (co-adapting phases)

Usage:
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize, OptimizerConfig
    result = optimize(pool_data, target, prices, config)

    # Multi-target decomposition:
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_multi_target
    result = optimize_multi_target(pool_data, target, prices, config)

    # Cooperative coevolution:
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize_cooperative
    result = optimize_cooperative(pool_data, target, prices, config)
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field

import numpy as np

from .bridge import encode_initial_state, evaluate_population_rust, is_rust_available
from .gene import (
    CraftTarget,
    DecomposedResult,
    Fitness,
    Individual,
    ModTarget,
    PhaseResult,
    PhaseTarget,
    PriceCache,
    RuleList,
)
from .nsga2 import non_dominated_sort, select_survivors, tournament_select
from .operators import breed, prune_dead_rules, random_rule, CROSSOVER_RATE
from .qd_archive import QDArchive
from .seeds import create_seeded_population

log = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class OptimizerConfig:
    """Parameters for the optimization run."""
    pop_size: int = 200
    max_generations: int = 50
    mc_trials: int = 500
    max_steps: int = 500
    seed_fraction: float = 0.4
    elite_fraction: float = 0.2
    archive_injection_interval: int = 5
    archive_injection_fraction: float = 0.1
    convergence_threshold: float = 0.001  # hypervolume change threshold
    convergence_patience: int = 5         # generations without improvement


# ── Result Structures ─────────────────────────────────────────────────────────

@dataclass
class CraftingStrategy:
    """One discovered strategy — a human-readable crafting recipe."""
    rulelist: RuleList
    fitness: Fitness
    family_name: str = ""
    verdict: str = ""              # "CRAFT" or "BUY"
    expected_cost: float = 0.0     # Total: base + all currency/omens (chaos equiv)
    success_rate: float = 0.0
    cost_p90: float = 0.0
    savings_vs_trade: float = 0.0

    # Starting point
    starting_state: str = "blank"  # "blank", "magic_with_target", "fractured_target"
    base_acquisition_cost: float = 0.0

    # Cost breakdown (all in chaos)
    currency_cost: float = 0.0     # expected_cost - base_acquisition_cost (approx)
    # Note: expected_cost from MC includes ALL costs (base purchases on restart,
    # currency usage, omens). The breakdown is approximate since restarts mean
    # multiple base purchases can happen in one craft attempt.

    # Human-readable steps
    steps: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [
            f"Strategy: {self.family_name}",
            f"  Verdict: {self.verdict} | Total cost: {self.expected_cost:.0f}c | "
            f"Success: {self.success_rate:.0%} | p90: {self.cost_p90:.0f}c",
            f"  Start: {self.starting_state} (base: {self.base_acquisition_cost:.0f}c) | "
            f"Currency: ~{self.currency_cost:.0f}c",
            f"  vs Trade ({self.savings_vs_trade:+.0f}c)",
            f"  Rules:",
        ]
        lines.append(str(self.rulelist))
        return "\n".join(lines)


@dataclass
class OptimizationResult:
    """Full output from one optimization run."""
    target: CraftTarget
    strategies: list[CraftingStrategy] = field(default_factory=list)
    trade_price: float = float("inf")
    best_verdict: str = ""

    # Metadata
    generations: int = 0
    evaluations: int = 0
    wall_time_seconds: float = 0.0
    archive_coverage: float = 0.0
    rust_available: bool = False

    # All discovered strategies (from archive)
    archive_strategies: list[CraftingStrategy] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Optimization Result: {self.target}",
            f"  Trade price: {self.trade_price:.0f}c",
            f"  Best verdict: {self.best_verdict}",
            f"  Generations: {self.generations} | Evaluations: {self.evaluations:,}",
            f"  Wall time: {self.wall_time_seconds:.1f}s | Rust: {self.rust_available}",
            f"  Archive coverage: {self.archive_coverage:.0%}",
            f"  Strategies found: {len(self.strategies)} (Pareto front) + "
            f"{len(self.archive_strategies)} (archive)",
        ]
        if self.strategies:
            best = self.strategies[0]
            lines.append(f"  Best: {best.expected_cost:.0f}c | {best.success_rate:.0%} | "
                         f"p90={best.cost_p90:.0f}c | {best.family_name}")
        return "\n".join(lines)


# ── Strategy Labeling ─────────────────────────────────────────────────────────

def _label_strategy(rl: RuleList, fitness: Fitness, prices: PriceCache) -> CraftingStrategy:
    """Convert a RuleList + Fitness into a labeled CraftingStrategy."""
    # Determine starting state from rules
    from .gene import Currency
    starting_state = "blank"
    base_cost = prices.base_white

    for rule in rl.rules:
        if rule.action.currency == Currency.BUY_MAGIC:
            starting_state = "magic_with_target"
            # Use first target's magic price
            if prices.base_magic_with:
                base_cost = next(iter(prices.base_magic_with.values()), prices.base_white)
            break
        elif rule.action.currency == Currency.BUY_FRACTURED:
            starting_state = "fractured_target"
            if prices.base_fractured_with:
                base_cost = next(iter(prices.base_fractured_with.values()), prices.base_white)
            break

    # Auto-generate family name from behavioral descriptors
    early = rl.primary_early_currency
    omen_count = rl.omen_count

    if starting_state == "fractured_target":
        family_name = "Buy Fractured + Fill"
    elif starting_state == "magic_with_target":
        family_name = "Buy Magic + Regal + Fill"
    elif early == "chaos":
        family_name = "Chaos Spam" + (" + Whittling" if omen_count > 0 else "")
    elif early == "alchemy":
        family_name = "Alchemy + Exalt"
    elif omen_count >= 3:
        family_name = "Omen-Targeted"
    elif any(r.action.currency in (Currency.ESSENCE_GREATER, Currency.ESSENCE_NORMAL, Currency.ESSENCE_LESSER) for r in rl.rules):
        if any(r.action.currency == Currency.DESECRATE for r in rl.rules):
            family_name = "Essence + Desecrate + Fill"
        else:
            family_name = "Essence + Fill"
    elif any(r.action.currency == Currency.FRACTURING for r in rl.rules):
        family_name = "Divine → Fracture"
    else:
        family_name = "Alt-Regal" + (" (Greater)" if any(
            r.action.currency == Currency.GREATER_EXALTED for r in rl.rules
        ) else "")

    # Verdict
    trade_price = prices.trade_finished
    verdict = "CRAFT" if fitness.expected_cost < trade_price else "BUY"
    savings = trade_price - fitness.expected_cost

    # Generate step descriptions
    steps = [f"{i+1}. {rule}" for i, rule in enumerate(rl.rules)]

    return CraftingStrategy(
        rulelist=rl,
        fitness=fitness,
        family_name=family_name,
        verdict=verdict,
        expected_cost=fitness.expected_cost,
        success_rate=fitness.success_rate,
        cost_p90=fitness.cost_p90,
        savings_vs_trade=savings,
        starting_state=starting_state,
        base_acquisition_cost=base_cost,
        currency_cost=max(0.0, fitness.expected_cost - base_cost),
        steps=steps,
    )


# ── Main Optimizer ────────────────────────────────────────────────────────────

def optimize(
    pool_data: dict,
    target: CraftTarget,
    prices: PriceCache,
    config: OptimizerConfig | None = None,
) -> OptimizationResult:
    """Run the full GP optimization loop.

    Args:
        pool_data: encoded mod pool from bridge.encode_pool()
        target: what mods to achieve
        prices: pre-fetched price cache
        config: optimizer parameters (defaults if None)

    Returns:
        OptimizationResult with ranked strategies and metadata
    """
    if config is None:
        config = OptimizerConfig()

    start_time = time.time()

    # ── Initialize population ──
    seeded = create_seeded_population(config.pop_size, config.seed_fraction)
    population: list[Individual] = [Individual(rl) for rl in seeded]

    # Fill remaining with random individuals
    while len(population) < config.pop_size:
        rl = _random_rulelist()
        population.append(Individual(rl))

    archive = QDArchive()
    best_cost_history: list[float] = []
    total_evaluations = 0

    # ── Generation loop ──
    gen = 0
    for gen in range(config.max_generations):
        # Evaluate
        evaluate_population_rust(
            population, pool_data, prices,
            n_trials=config.mc_trials,
            max_steps=config.max_steps,
            base_seed=gen * 100_000,
        )
        total_evaluations += len(population) * config.mc_trials

        # Dead rule pruning
        for ind in population:
            if ind.fitness.fire_on_success:
                ind.rulelist = prune_dead_rules(ind.rulelist, ind.fitness)

        # Offer to QD archive
        archive.offer_population(population)

        # Archive injection (every N generations)
        if gen > 0 and gen % config.archive_injection_interval == 0:
            injection_size = int(config.pop_size * config.archive_injection_fraction)
            injection = archive.get_injection_set(injection_size)
            if injection:
                # Replace worst-ranked individuals
                population.sort(key=lambda ind: (ind.pareto_rank, -ind.crowding_distance))
                for i, inj_ind in enumerate(injection):
                    if i < len(population):
                        population[-(i + 1)] = inj_ind

        # Selection
        survivors = select_survivors(population, config.pop_size)

        # Breed offspring
        offspring: list[Individual] = []
        elite_count = int(config.pop_size * config.elite_fraction)

        # Keep elites unchanged
        elites = survivors[:elite_count]

        # Fill rest with offspring
        while len(offspring) < config.pop_size - elite_count:
            parent_a = tournament_select(survivors)
            parent_b = tournament_select(survivors)
            child_rl = breed(
                parent_a.rulelist, parent_b.rulelist,
                parent_a.fitness, parent_b.fitness,
            )
            offspring.append(Individual(child_rl))

        population = [ind for ind in elites] + offspring

        # Convergence check — track best VIABLE (>50% success) cost
        viable_costs = [
            ind.fitness.expected_cost for ind in survivors
            if ind.fitness.expected_cost < float("inf") and ind.fitness.success_rate > 0.5
        ]
        if viable_costs:
            best_cost = min(viable_costs)
            best_cost_history.append(best_cost)

            if len(best_cost_history) >= config.convergence_patience:
                recent = best_cost_history[-config.convergence_patience:]
                if recent[0] > 0:
                    improvement = (recent[0] - recent[-1]) / recent[0]
                    if improvement < config.convergence_threshold:
                        break

    # ── Build results ──
    wall_time = time.time() - start_time

    # Get final Pareto front
    final_fronts = non_dominated_sort(population)
    pareto_front = final_fronts[0] if final_fronts else []

    # Convert to CraftingStrategy
    strategies = []
    for ind in sorted(pareto_front, key=lambda x: x.fitness.expected_cost):
        strategy = _label_strategy(ind.rulelist, ind.fitness, prices)
        strategies.append(strategy)

    # Archive strategies
    archive_strategies = []
    for ind in archive.get_elites():
        strategy = _label_strategy(ind.rulelist, ind.fitness, prices)
        archive_strategies.append(strategy)

    archive_strategies.sort(key=lambda s: s.expected_cost)

    # Best verdict: find cheapest strategy with >50% success rate
    # (considers both Pareto front and archive)
    all_strategies = strategies + archive_strategies
    viable = [s for s in all_strategies if s.success_rate > 0.5]
    if not viable:
        # Fall back to any strategy with >0% success
        viable = [s for s in all_strategies if s.success_rate > 0]
    if viable:
        best = min(viable, key=lambda s: s.expected_cost)
        if best.expected_cost < prices.trade_finished:
            best_verdict = f"CRAFT (saves ~{prices.trade_finished - best.expected_cost:.0f}c vs trade)"
        else:
            best_verdict = f"BUY (crafting costs {best.expected_cost - prices.trade_finished:.0f}c more than trade)"
    else:
        best_verdict = "NO VIABLE STRATEGY FOUND"

    # Reorder: put best viable first, then rest of Pareto front
    if viable:
        best_strategy = min(viable, key=lambda s: s.expected_cost)
        strategies = [best_strategy] + [s for s in strategies if s is not best_strategy]

    return OptimizationResult(
        target=target,
        strategies=strategies,
        trade_price=prices.trade_finished,
        best_verdict=best_verdict,
        generations=gen + 1,
        evaluations=total_evaluations,
        wall_time_seconds=wall_time,
        archive_coverage=archive.coverage,
        rust_available=is_rust_available(),
        archive_strategies=archive_strategies,
    )


def _random_rulelist() -> RuleList:
    """Generate a random rule-list for initial population diversity."""
    from .gene import Condition, Action, Currency, Rarity

    rl = RuleList()
    n_rules = random.randint(5, 12)

    # Always start with a rarity-handling rule
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))

    for _ in range(n_rules - 2):
        rl.add_rule(random_rule().condition, random_rule().action)

    # Always end with a default
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))

    return rl


def _random_rulelist_for_phase(setup_rules: list | None = None) -> RuleList:
    """Generate a random rule-list for a decomposed phase.

    Prepends setup rules, then adds random exalt/annul rules.
    Skips transmute/alchemy since the item is already Rare.
    """
    from .gene import Condition, Action, Currency, Rarity, Omen

    rl = RuleList()

    # Prepend setup rules
    if setup_rules:
        for rule in setup_rules:
            rl.add_rule(rule.condition, rule.action, rule.label)

    # Success check
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE))

    n_rules = random.randint(3, 6)
    exalt_actions = [
        Action(Currency.EXALTED),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        Action(Currency.GREATER_EXALTED),
        Action(Currency.GREATER_EXALTED, Omen.SINISTRAL_EXALTATION),
        Action(Currency.GREATER_EXALTED, Omen.DEXTRAL_EXALTATION),
        Action(Currency.ANNULMENT),
    ]
    conditions = [
        Condition.open_prefix_gte(1),
        Condition.open_suffix_gte(1),
        Condition.missing_target_prefix(),
        Condition.missing_target_suffix(),
        Condition.removable_gt_targets(),
        Condition.has_non_target_removable(),
    ]

    for _ in range(n_rules):
        cond = random.choice(conditions)
        act = random.choice(exalt_actions)
        rl.add_rule(cond, act)

    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
    return rl


# ── Multi-Target Decomposition ───────────────────────────────────────────────

def optimize_multi_target(
    pool_data: dict,
    target: CraftTarget,
    prices: PriceCache,
    config: OptimizerConfig | None = None,
    ordering: list[int] | None = None,
    max_orderings: int = 120,
    decompose_threshold: int = 4,
) -> DecomposedResult:
    """Optimize a multi-target craft via sub-goal decomposition.

    Breaks N targets into sequential single-target phases, determines
    optimal ordering, and runs the GP independently on each phase.

    For targets <= decompose_threshold, delegates to monolithic optimize().

    Args:
        pool_data: encoded mod pool from bridge.encode_pool()
        target: full multi-target CraftTarget
        prices: pre-fetched price cache
        config: GP parameters (applied to each phase)
        ordering: explicit phase order (indices into target.targets).
                  If None, auto-detect via WSJF heuristic.
        max_orderings: max permutations to evaluate for ordering search.
        decompose_threshold: min targets before decomposing (default 4).

    Returns:
        DecomposedResult with per-phase strategies and total cost.
    """
    from .decompose import (
        build_phases,
        build_phase_craft_target,
        build_setup_rules,
        classify_phase_risk,
        detect_free_hits,
        optimal_ordering,
    )
    from .seeds import create_seeded_population_for_phase

    if config is None:
        config = OptimizerConfig()

    start_time = time.time()
    n_targets = len(target.targets)

    # For small target counts, fall back to monolithic optimization
    if n_targets < decompose_threshold:
        mono_result = optimize(pool_data, target, prices, config)
        # Wrap in DecomposedResult for uniform interface
        if mono_result.strategies:
            best = mono_result.strategies[0]
            phase_result = PhaseResult(
                phase_index=0,
                phase_target=PhaseTarget(targets=target.targets),
                strategy=best,
                expected_cost=best.expected_cost,
                success_rate=best.success_rate,
                restart_risk="safe",
                cumulative_cost=best.expected_cost,
            )
            return DecomposedResult(
                phases=[phase_result],
                total_expected_cost=best.expected_cost,
                total_success_rate=best.success_rate,
                ordering=list(range(n_targets)),
                ordering_rationale=f"Monolithic (only {n_targets} targets)",
                trade_price=prices.trade_finished,
                verdict=mono_result.best_verdict,
                wall_time_seconds=time.time() - start_time,
                item_class=target.item_class,
                ilvl=target.ilvl,
            )
        return DecomposedResult(
            wall_time_seconds=time.time() - start_time,
            item_class=target.item_class,
            ilvl=target.ilvl,
            verdict="NO VIABLE STRATEGY FOUND",
        )

    # ── Step 1: Determine phase ordering ──
    # Build prices dict for decompose module (it uses simple dicts, not PriceCache)
    price_dict = {**prices.currency, **prices.omen}
    price_dict["buy_magic"] = prices.base_magic_with.get(
        target.targets[0].family, prices.base_white * 10
    )

    if ordering is None:
        best_ordering, rationale, candidates = optimal_ordering(
            target, pool_data, price_dict, max_orderings
        )
    else:
        best_ordering = ordering
        rationale = "User-specified ordering"
        candidates = []

    log.info(
        f"Decomposition: {n_targets} targets, ordering={best_ordering}, "
        f"rationale={rationale}"
    )

    # ── Step 2: Build phases ──
    phases = build_phases(target, best_ordering, pool_data, price_dict)

    # ── Step 3: Optimize each phase ──
    phase_results: list[PhaseResult] = []
    cumulative_cost = 0.0
    cumulative_success = 1.0
    skipped_phases: set[int] = set()  # phases skipped due to free hits

    for phase in phases:
        if phase.phase_index in skipped_phases:
            log.info(f"Skipping phase {phase.phase_index} (free hit from earlier phase)")
            continue
        log.info(f"Optimizing phase {phase.phase_index}: {phase}")

        # Build setup rules for this phase (encodes prior-phase state)
        setup_rules = build_setup_rules(phase)

        # Build the phase-specific CraftTarget
        # For the Phase 1 shortcut, we need ALL prior-phase targets in the
        # pool_data targets so find_first_missing_target works correctly.
        # The setup rules will place prior-phase mods via BUY_MAGIC/ESSENCE.
        phase_craft_target = _build_phase_pool_target(phase, target)

        # Re-encode pool_data with phase-specific targets
        phase_pool = _retarget_pool(pool_data, phase_craft_target)

        # Generate phase-appropriate initial population
        primary_affix = phase.targets[0].affix_type
        seeded = create_seeded_population_for_phase(
            config.pop_size, config.seed_fraction,
            primary_affix, setup_rules,
        )
        population: list[Individual] = [Individual(rl) for rl in seeded]

        # Fill remaining with random phase-aware individuals
        while len(population) < config.pop_size:
            rl = _random_rulelist_for_phase(setup_rules)
            population.append(Individual(rl))

        # Encode initial state for Rust (later phases start from prior mods)
        phase_initial_state = encode_initial_state(phase)

        # Run the GP loop for this phase
        phase_config = OptimizerConfig(
            pop_size=config.pop_size,
            max_generations=config.max_generations,
            mc_trials=config.mc_trials,
            max_steps=config.max_steps,
            seed_fraction=0.0,  # already seeded above
            elite_fraction=config.elite_fraction,
            archive_injection_interval=config.archive_injection_interval,
            archive_injection_fraction=config.archive_injection_fraction,
            convergence_threshold=config.convergence_threshold,
            convergence_patience=config.convergence_patience,
        )

        phase_result_raw = _run_gp_loop(
            population, phase_pool, prices, phase_config,
            initial_state=phase_initial_state,
        )

        # Extract best strategy
        if phase_result_raw.strategies:
            best = phase_result_raw.strategies[0]
        else:
            # No viable strategy — report failure for this phase
            best = CraftingStrategy(
                rulelist=RuleList(),
                fitness=Fitness(),
                family_name="NO STRATEGY",
                verdict="FAILED",
                expected_cost=float("inf"),
                success_rate=0.0,
            )

        # Classify phase risk
        risk = classify_phase_risk(
            phase.targets[0],
            len(phase.starting_mods),
            phase.starting_rarity,
        )

        cumulative_cost += best.expected_cost
        cumulative_success *= best.success_rate

        phase_results.append(PhaseResult(
            phase_index=phase.phase_index,
            phase_target=phase,
            strategy=best,
            expected_cost=best.expected_cost,
            success_rate=best.success_rate,
            restart_risk=risk,
            cumulative_cost=cumulative_cost,
        ))

        log.info(
            f"Phase {phase.phase_index} done: {best.expected_cost:.0f}c, "
            f"{best.success_rate:.0%}, risk={risk}"
        )

        # Check for free hits on remaining targets
        remaining_phase_indices = [
            p.phase_index for p in phases
            if p.phase_index > phase.phase_index
            and p.phase_index not in skipped_phases
        ]
        if remaining_phase_indices:
            remaining_targets = [
                phases[pi].targets[0] for pi in range(len(phases))
                if phases[pi].phase_index in remaining_phase_indices
            ]
            # Estimate random mods: alchemy/chaos add ~4, regal/essence add ~2
            expected_random = 2
            free_indices = detect_free_hits(
                phase, remaining_targets, pool_data,
                expected_random_mods=expected_random,
            )
            for fi in free_indices:
                skip_phase_idx = remaining_phase_indices[fi]
                skipped_phases.add(skip_phase_idx)
                log.info(
                    f"Free hit: phase {skip_phase_idx} target "
                    f"({remaining_targets[fi].family}) likely covered by phase "
                    f"{phase.phase_index}"
                )

    # ── Step 4: Aggregate results ──
    total_cost = sum(pr.expected_cost for pr in phase_results)
    total_success = 1.0
    for pr in phase_results:
        total_success *= pr.success_rate

    # Verdict
    if total_cost < prices.trade_finished:
        verdict = f"CRAFT (saves ~{prices.trade_finished - total_cost:.0f}c vs trade)"
    elif prices.trade_finished < float("inf"):
        verdict = f"BUY (crafting costs {total_cost - prices.trade_finished:.0f}c more)"
    else:
        verdict = f"CRAFT ({total_cost:.0f}c, no trade price available)"

    wall_time = time.time() - start_time

    return DecomposedResult(
        phases=phase_results,
        total_expected_cost=total_cost,
        total_success_rate=total_success,
        ordering=best_ordering,
        ordering_rationale=rationale,
        trade_price=prices.trade_finished,
        verdict=verdict,
        ordering_candidates=candidates,
        wall_time_seconds=wall_time,
        item_class=target.item_class,
        ilvl=target.ilvl,
    )


def _build_phase_pool_target(phase: PhaseTarget, full_target: CraftTarget) -> CraftTarget:
    """Build a CraftTarget that includes this phase's targets plus all
    prior-phase targets (so find_first_missing_target places them in order).

    The target list is ordered: prior-phase targets first, then this phase's targets.
    The setup rules will place prior-phase targets via BUY_MAGIC/ESSENCE_GREATER.
    The GP's remaining rules then pursue THIS phase's targets.
    """
    # Collect prior-phase mod families
    prior_targets = []
    for fam_id, affix, tier in phase.starting_mods:
        # Find the matching ModTarget in the full target
        for t in full_target.targets:
            if t.family_id == fam_id:
                prior_targets.append(t)
                break

    # This phase's targets come after
    all_targets = prior_targets + list(phase.targets)

    return CraftTarget(
        targets=all_targets,
        item_class=full_target.item_class,
        ilvl=full_target.ilvl,
    )


def _retarget_pool(pool_data: dict, new_target: CraftTarget) -> dict:
    """Create a copy of pool_data with updated target arrays."""
    from .bridge import encode_pool
    import numpy as np

    result = dict(pool_data)
    result["target_prefix_families"] = np.array(new_target.prefix_family_ids, dtype=np.uint16)
    result["target_suffix_families"] = np.array(new_target.suffix_family_ids, dtype=np.uint16)
    result["target_max_tiers"] = np.array(new_target.max_tiers, dtype=np.uint8)
    return result


def _run_gp_loop(
    population: list[Individual],
    pool_data: dict,
    prices: PriceCache,
    config: OptimizerConfig,
    initial_state: np.ndarray | None = None,
) -> OptimizationResult:
    """Run the GP loop on a pre-initialized population.

    Extracted from optimize() to allow reuse with custom populations
    (e.g., phase-specific populations with setup rules).

    Args:
        initial_state: Optional 17-element uint16 array for Rust MC trials.
            If provided, each trial starts from this item state.
    """
    archive = QDArchive()
    best_cost_history: list[float] = []
    total_evaluations = 0

    gen = 0
    for gen in range(config.max_generations):
        # Evaluate
        evaluate_population_rust(
            population, pool_data, prices,
            n_trials=config.mc_trials,
            max_steps=config.max_steps,
            base_seed=gen * 100_000,
            initial_state=initial_state,
        )
        total_evaluations += len(population) * config.mc_trials

        # Dead rule pruning
        for ind in population:
            if ind.fitness.fire_on_success:
                ind.rulelist = prune_dead_rules(ind.rulelist, ind.fitness)

        # Offer to QD archive
        archive.offer_population(population)

        # Archive injection
        if gen > 0 and gen % config.archive_injection_interval == 0:
            injection_size = int(config.pop_size * config.archive_injection_fraction)
            injection = archive.get_injection_set(injection_size)
            if injection:
                population.sort(key=lambda ind: (ind.pareto_rank, -ind.crowding_distance))
                for i, inj_ind in enumerate(injection):
                    if i < len(population):
                        population[-(i + 1)] = inj_ind

        # Selection
        survivors = select_survivors(population, config.pop_size)

        # Breed offspring
        offspring: list[Individual] = []
        elite_count = int(config.pop_size * config.elite_fraction)
        elites = survivors[:elite_count]

        while len(offspring) < config.pop_size - elite_count:
            parent_a = tournament_select(survivors)
            parent_b = tournament_select(survivors)
            child_rl = breed(
                parent_a.rulelist, parent_b.rulelist,
                parent_a.fitness, parent_b.fitness,
            )
            offspring.append(Individual(child_rl))

        population = [ind for ind in elites] + offspring

        # Convergence check
        viable_costs = [
            ind.fitness.expected_cost for ind in survivors
            if ind.fitness.expected_cost < float("inf") and ind.fitness.success_rate > 0.5
        ]
        if viable_costs:
            best_cost = min(viable_costs)
            best_cost_history.append(best_cost)

            if len(best_cost_history) >= config.convergence_patience:
                recent = best_cost_history[-config.convergence_patience:]
                if recent[0] > 0:
                    improvement = (recent[0] - recent[-1]) / recent[0]
                    if improvement < config.convergence_threshold:
                        break

    # Build results
    final_fronts = non_dominated_sort(population)
    pareto_front = final_fronts[0] if final_fronts else []

    strategies = []
    for ind in sorted(pareto_front, key=lambda x: x.fitness.expected_cost):
        strategy = _label_strategy(ind.rulelist, ind.fitness, prices)
        strategies.append(strategy)

    archive_strategies = []
    for ind in archive.get_elites():
        strategy = _label_strategy(ind.rulelist, ind.fitness, prices)
        archive_strategies.append(strategy)
    archive_strategies.sort(key=lambda s: s.expected_cost)

    # Best verdict
    all_strategies = strategies + archive_strategies
    viable = [s for s in all_strategies if s.success_rate > 0.5]
    if not viable:
        viable = [s for s in all_strategies if s.success_rate > 0]

    if viable:
        best = min(viable, key=lambda s: s.expected_cost)
        strategies = [best] + [s for s in strategies if s is not best]

    best_verdict = ""
    if viable:
        best = strategies[0]
        if best.expected_cost < prices.trade_finished:
            best_verdict = f"CRAFT (saves ~{prices.trade_finished - best.expected_cost:.0f}c)"
        else:
            best_verdict = f"BUY (crafting costs more)"
    else:
        best_verdict = "NO VIABLE STRATEGY FOUND"

    # Use a dummy target for the result (phase target is in the phase result)
    return OptimizationResult(
        target=CraftTarget(),
        strategies=strategies,
        trade_price=prices.trade_finished,
        best_verdict=best_verdict,
        generations=gen + 1,
        evaluations=total_evaluations,
        wall_time_seconds=0.0,
        archive_coverage=archive.coverage,
        rust_available=is_rust_available(),
        archive_strategies=archive_strategies,
    )


# ── Cooperative Coevolution (Tier 2) ────────────────────────────────────────

@dataclass
class _PhasePopulation:
    """State for one sub-population in cooperative coevolution."""
    phase: PhaseTarget
    population: list[Individual]
    archive: QDArchive
    pool_data: dict
    best_cost_history: list[float]
    champion: Individual | None = None
    total_evaluations: int = 0


def optimize_cooperative(
    pool_data: dict,
    target: CraftTarget,
    prices: PriceCache,
    config: OptimizerConfig | None = None,
    ordering: list[int] | None = None,
    max_orderings: int = 120,
    decompose_threshold: int = 4,
) -> DecomposedResult:
    """Cooperative coevolution: N sub-populations co-adapting simultaneously.

    Unlike Tier 1 (optimize_multi_target) which optimizes phases independently
    and sequentially, CC maintains all phase populations at once. Each
    generation evaluates phases in order, where phase K uses the current
    champion from phase K-1 as its starting state. This lets later phases
    adapt to changes in earlier phase strategies.

    Args:
        pool_data: encoded mod pool from bridge.encode_pool()
        target: full multi-target CraftTarget
        prices: pre-fetched price cache
        config: GP parameters (applied to each phase)
        ordering: explicit phase order. If None, auto-detect via WSJF.
        max_orderings: max permutations to evaluate for ordering search.
        decompose_threshold: min targets before decomposing (default 4).

    Returns:
        DecomposedResult with per-phase strategies and total cost.
    """
    from .decompose import (
        build_phases,
        build_setup_rules,
        classify_phase_risk,
        optimal_ordering,
    )
    from .seeds import create_seeded_population_for_phase

    if config is None:
        config = OptimizerConfig()

    start_time = time.time()
    n_targets = len(target.targets)

    # For small target counts, fall back to monolithic optimization
    if n_targets < decompose_threshold:
        mono_result = optimize(pool_data, target, prices, config)
        if mono_result.strategies:
            best = mono_result.strategies[0]
            phase_result = PhaseResult(
                phase_index=0,
                phase_target=PhaseTarget(targets=target.targets),
                strategy=best,
                expected_cost=best.expected_cost,
                success_rate=best.success_rate,
                restart_risk="safe",
                cumulative_cost=best.expected_cost,
            )
            return DecomposedResult(
                phases=[phase_result],
                total_expected_cost=best.expected_cost,
                total_success_rate=best.success_rate,
                ordering=list(range(n_targets)),
                ordering_rationale=f"Monolithic (only {n_targets} targets)",
                trade_price=prices.trade_finished,
                verdict=mono_result.best_verdict,
                wall_time_seconds=time.time() - start_time,
                item_class=target.item_class,
                ilvl=target.ilvl,
            )
        return DecomposedResult(
            wall_time_seconds=time.time() - start_time,
            item_class=target.item_class,
            ilvl=target.ilvl,
            verdict="NO VIABLE STRATEGY FOUND",
        )

    # ── Step 1: Determine phase ordering ──
    price_dict = {**prices.currency, **prices.omen}
    price_dict["buy_magic"] = prices.base_magic_with.get(
        target.targets[0].family, prices.base_white * 10
    )

    if ordering is None:
        best_ordering, rationale, candidates = optimal_ordering(
            target, pool_data, price_dict, max_orderings
        )
    else:
        best_ordering = ordering
        rationale = "User-specified ordering"
        candidates = []

    log.info(
        f"CC decomposition: {n_targets} targets, ordering={best_ordering}, "
        f"rationale={rationale}"
    )

    # ── Step 2: Build phases and initialize sub-populations ──
    phases = build_phases(target, best_ordering, pool_data, price_dict)

    sub_pops: list[_PhasePopulation] = []
    for phase in phases:
        setup_rules = build_setup_rules(phase)
        phase_craft_target = _build_phase_pool_target(phase, target)
        phase_pool = _retarget_pool(pool_data, phase_craft_target)

        primary_affix = phase.targets[0].affix_type
        seeded = create_seeded_population_for_phase(
            config.pop_size, config.seed_fraction,
            primary_affix, setup_rules,
        )
        population: list[Individual] = [Individual(rl) for rl in seeded]
        while len(population) < config.pop_size:
            rl = _random_rulelist_for_phase(setup_rules)
            population.append(Individual(rl))

        sub_pops.append(_PhasePopulation(
            phase=phase,
            population=population,
            archive=QDArchive(),
            pool_data=phase_pool,
            best_cost_history=[],
        ))

    # ── Step 3: Co-evolutionary loop ──
    total_evaluations = 0
    converged_count = 0

    for gen in range(config.max_generations):
        gen_converged = True

        for sp in sub_pops:
            # Build initial_state from phase definition.
            # In CC, we use the static phase starting_mods — these encode
            # which targets prior phases are responsible for. The co-adaptation
            # comes from all phases evolving simultaneously: if phase K's
            # champion changes strategy, phase K+1's population is re-evaluated
            # in the same generation and adapts.
            phase_initial_state = encode_initial_state(sp.phase)

            # Evaluate this sub-population
            evaluate_population_rust(
                sp.population, sp.pool_data, prices,
                n_trials=config.mc_trials,
                max_steps=config.max_steps,
                base_seed=gen * 100_000 + sp.phase.phase_index * 7919,
                initial_state=phase_initial_state,
            )
            sp.total_evaluations += len(sp.population) * config.mc_trials

            # Dead rule pruning
            for ind in sp.population:
                if ind.fitness.fire_on_success:
                    ind.rulelist = prune_dead_rules(ind.rulelist, ind.fitness)

            # Update archive
            sp.archive.offer_population(sp.population)

            # Archive injection
            if gen > 0 and gen % config.archive_injection_interval == 0:
                injection_size = int(config.pop_size * config.archive_injection_fraction)
                injection = sp.archive.get_injection_set(injection_size)
                if injection:
                    sp.population.sort(
                        key=lambda ind: (ind.pareto_rank, -ind.crowding_distance)
                    )
                    for i, inj_ind in enumerate(injection):
                        if i < len(sp.population):
                            sp.population[-(i + 1)] = inj_ind

            # Selection + breeding
            survivors = select_survivors(sp.population, config.pop_size)

            offspring: list[Individual] = []
            elite_count = int(config.pop_size * config.elite_fraction)
            elites = survivors[:elite_count]

            while len(offspring) < config.pop_size - elite_count:
                parent_a = tournament_select(survivors)
                parent_b = tournament_select(survivors)
                child_rl = breed(
                    parent_a.rulelist, parent_b.rulelist,
                    parent_a.fitness, parent_b.fitness,
                )
                offspring.append(Individual(child_rl))

            sp.population = list(elites) + offspring

            # Track champion (best viable individual)
            viable = [
                ind for ind in survivors
                if ind.fitness.expected_cost < float("inf")
                and ind.fitness.success_rate > 0.5
            ]
            if viable:
                sp.champion = min(viable, key=lambda ind: ind.fitness.expected_cost)

            # Per-phase convergence check
            viable_costs = [ind.fitness.expected_cost for ind in viable]
            if viable_costs:
                best_cost = min(viable_costs)
                sp.best_cost_history.append(best_cost)

                if len(sp.best_cost_history) >= config.convergence_patience:
                    recent = sp.best_cost_history[-config.convergence_patience:]
                    if recent[0] > 0:
                        improvement = (recent[0] - recent[-1]) / recent[0]
                        if improvement >= config.convergence_threshold:
                            gen_converged = False
                    else:
                        gen_converged = False
                else:
                    gen_converged = False
            else:
                gen_converged = False

        total_evaluations = sum(sp.total_evaluations for sp in sub_pops)

        # All phases converged this generation
        if gen_converged:
            converged_count += 1
            if converged_count >= config.convergence_patience:
                log.info(f"CC converged after {gen + 1} generations")
                break
        else:
            converged_count = 0

        # Log progress every 10 generations
        if gen % 10 == 0:
            costs = [
                f"{sp.champion.fitness.expected_cost:.0f}c"
                if sp.champion else "?"
                for sp in sub_pops
            ]
            log.info(f"CC gen {gen}: phase costs = [{', '.join(costs)}]")

    # ── Step 4: Extract results ──
    phase_results: list[PhaseResult] = []
    cumulative_cost = 0.0

    for sp in sub_pops:
        # Get best strategy from champion or archive
        if sp.champion:
            best = _label_strategy(sp.champion.rulelist, sp.champion.fitness, prices)
        else:
            # Try archive
            archive_elites = sp.archive.get_elites()
            viable_elites = [
                ind for ind in archive_elites
                if ind.fitness.success_rate > 0.5
            ]
            if viable_elites:
                best_ind = min(viable_elites, key=lambda x: x.fitness.expected_cost)
                best = _label_strategy(best_ind.rulelist, best_ind.fitness, prices)
            else:
                best = CraftingStrategy(
                    rulelist=RuleList(),
                    fitness=Fitness(),
                    family_name="NO STRATEGY",
                    verdict="FAILED",
                    expected_cost=float("inf"),
                    success_rate=0.0,
                )

        risk = classify_phase_risk(
            sp.phase.targets[0],
            len(sp.phase.starting_mods),
            sp.phase.starting_rarity,
        )

        cumulative_cost += best.expected_cost

        phase_results.append(PhaseResult(
            phase_index=sp.phase.phase_index,
            phase_target=sp.phase,
            strategy=best,
            expected_cost=best.expected_cost,
            success_rate=best.success_rate,
            restart_risk=risk,
            cumulative_cost=cumulative_cost,
        ))

    # Aggregate
    total_cost = sum(pr.expected_cost for pr in phase_results)
    total_success = 1.0
    for pr in phase_results:
        total_success *= pr.success_rate

    if total_cost < prices.trade_finished:
        verdict = f"CRAFT (saves ~{prices.trade_finished - total_cost:.0f}c vs trade)"
    elif prices.trade_finished < float("inf"):
        verdict = f"BUY (crafting costs {total_cost - prices.trade_finished:.0f}c more)"
    else:
        verdict = f"CRAFT ({total_cost:.0f}c, no trade price available)"

    wall_time = time.time() - start_time

    return DecomposedResult(
        phases=phase_results,
        total_expected_cost=total_cost,
        total_success_rate=total_success,
        ordering=best_ordering,
        ordering_rationale=f"CC: {rationale}",
        trade_price=prices.trade_finished,
        verdict=verdict,
        ordering_candidates=candidates,
        wall_time_seconds=wall_time,
        item_class=target.item_class,
        ilvl=target.ilvl,
    )
