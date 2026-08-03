"""Top-level optimizer runner.

Orchestrates the full GP loop:
  init → evaluate → select → breed → archive → repeat → cluster → output

Usage:
    from poe2_crafting_mcp.crafting.optimizer.runner import optimize, OptimizerConfig
    result = optimize(pool_data, target, prices, config)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

import numpy as np

from .bridge import evaluate_population_rust, is_rust_available
from .gene import (
    CraftTarget,
    Fitness,
    Individual,
    PriceCache,
    RuleList,
)
from .nsga2 import non_dominated_sort, select_survivors, tournament_select
from .operators import breed, prune_dead_rules, random_rule, CROSSOVER_RATE
from .qd_archive import QDArchive
from .seeds import create_seeded_population


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
    elif any(r.action.currency == Currency.ESSENCE_UPGRADE for r in rl.rules):
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
