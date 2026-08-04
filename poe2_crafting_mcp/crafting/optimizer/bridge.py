"""Bridge between Python optimizer and Rust MC evaluator.

Serializes population, mod pool, and prices into numpy arrays for the
Rust evaluate_population() call. Deserializes results back into Fitness objects.

Falls back to a pure-Python stub if the Rust extension isn't available
(for development/testing without maturin build).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from .gene import (
    MAX_RULES,
    Currency,
    Fitness,
    Individual,
    Omen,
    PhaseTarget,
    PriceCache,
    CraftTarget,
)

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# Try to import the Rust extension
_RUST_AVAILABLE = False
try:
    from poe2_optimizer import evaluate_population as _rust_evaluate  # type: ignore
    _RUST_AVAILABLE = True
    log.info("Rust poe2_optimizer loaded — fast MC evaluation available")
except ImportError:
    # Try loading from the build directory (development mode)
    import sys
    from pathlib import Path
    _so_dir = Path(__file__).resolve().parent.parent.parent.parent / "target" / "release"
    if _so_dir.exists():
        sys.path.insert(0, str(_so_dir))
        try:
            from poe2_optimizer import evaluate_population as _rust_evaluate  # type: ignore
            _RUST_AVAILABLE = True
            log.info("Rust poe2_optimizer loaded from target/release/")
        except ImportError:
            pass
    if not _RUST_AVAILABLE:
        log.warning(
            "Rust poe2_optimizer not available — using Python stub (slow). "
            "Build with: cd crates/poe2-optimizer && maturin develop --release"
        )


# ── Pool Encoding ─────────────────────────────────────────────────────────────

def encode_pool(
    prefix_weights: list[int],
    prefix_families: list[int],
    prefix_tiers: list[int],
    prefix_req_levels: list[int],
    suffix_weights: list[int],
    suffix_families: list[int],
    suffix_tiers: list[int],
    suffix_req_levels: list[int],
    target: CraftTarget,
    ilvl: int = 82,
    max_prefixes: int = 3,
    max_suffixes: int = 3,
) -> dict[str, np.ndarray]:
    """Encode mod pool as numpy arrays for Rust.

    Returns dict of arrays matching the evaluate_population() signature.
    """
    # Build cumulative sums for weighted sampling
    prefix_cumsum = np.cumsum(np.array(prefix_weights, dtype=np.uint64))
    suffix_cumsum = np.cumsum(np.array(suffix_weights, dtype=np.uint64))

    return {
        "prefix_weights": np.array(prefix_weights, dtype=np.uint32),
        "prefix_cumsum": prefix_cumsum.astype(np.uint64),
        "prefix_families": np.array(prefix_families, dtype=np.uint16),
        "prefix_tiers": np.array(prefix_tiers, dtype=np.uint8),
        "prefix_req_levels": np.array(prefix_req_levels, dtype=np.uint8),
        "suffix_weights": np.array(suffix_weights, dtype=np.uint32),
        "suffix_cumsum": suffix_cumsum.astype(np.uint64),
        "suffix_families": np.array(suffix_families, dtype=np.uint16),
        "suffix_tiers": np.array(suffix_tiers, dtype=np.uint8),
        "suffix_req_levels": np.array(suffix_req_levels, dtype=np.uint8),
        "target_prefix_families": np.array(target.prefix_family_ids, dtype=np.uint16),
        "target_suffix_families": np.array(target.suffix_family_ids, dtype=np.uint16),
        "target_max_tiers": np.array(target.max_tiers, dtype=np.uint8),
        "ilvl": ilvl,
        "max_prefixes": max_prefixes,
        "max_suffixes": max_suffixes,
    }


# ── Population Serialization ──────────────────────────────────────────────────

def serialize_population_for_rust(
    population: list[Individual],
) -> tuple[np.ndarray, np.ndarray]:
    """Serialize population into arrays matching Rust evaluate_population() input.

    Returns:
        rules_array: (pop_size, MAX_RULES, 5) uint16
        rule_counts: (pop_size,) uint8
    """
    pop_size = len(population)
    rules_array = np.zeros((pop_size, MAX_RULES, 5), dtype=np.uint16)
    rule_counts = np.zeros(pop_size, dtype=np.uint8)

    for i, ind in enumerate(population):
        conds, acts, n = ind.rulelist.serialize()
        rules_array[i, :, :3] = conds
        rules_array[i, :, 3:5] = acts
        rule_counts[i] = n

    return rules_array, rule_counts


# ── Initial State Encoding ────────────────────────────────────────────────────

def encode_initial_state(phase: PhaseTarget) -> np.ndarray | None:
    """Encode a PhaseTarget's starting state as 17 uint16s for Rust.

    Layout: [rarity, prefix_count, suffix_count, fractured_mask, flags,
             pf0, pf1, pf2, sf0, sf1, sf2, pt0, pt1, pt2, st0, st1, st2]

    Returns None if phase has no starting mods (blank start).
    """
    if not phase.starting_mods:
        return None

    data = np.zeros(17, dtype=np.uint16)
    data[0] = phase.starting_rarity
    data[4] = phase.starting_flags

    prefix_count = 0
    suffix_count = 0
    for family_id, affix_type, tier in phase.starting_mods:
        if affix_type == "prefix" and prefix_count < 3:
            data[5 + prefix_count] = family_id      # pf0-2
            data[11 + prefix_count] = tier           # pt0-2
            prefix_count += 1
        elif affix_type == "suffix" and suffix_count < 3:
            data[8 + suffix_count] = family_id       # sf0-2
            data[14 + suffix_count] = tier           # st0-2
            suffix_count += 1

    data[1] = prefix_count
    data[2] = suffix_count

    return data


# ── Evaluation Interface ──────────────────────────────────────────────────────

def evaluate_population_rust(
    population: list[Individual],
    pool_data: dict[str, np.ndarray],
    prices: PriceCache,
    n_trials: int = 500,
    max_steps: int = 500,
    base_seed: int = 0,
    initial_state: np.ndarray | None = None,
) -> None:
    """Evaluate entire population via Rust, updating fitness in place.

    Args:
        initial_state: Optional 17-element uint16 array from encode_initial_state().
            If provided, each MC trial starts from this item state instead of blank.

    If Rust isn't available, falls back to Python stub (random fitness).
    """
    if not _RUST_AVAILABLE:
        _evaluate_stub(population)
        return

    rules_array, rule_counts = serialize_population_for_rust(population)
    price_array = prices.encode_for_rust()
    max_currency_id = max(int(c) for c in Currency) + 1

    # Call Rust
    fitness_array, fire_success, fire_failure = _rust_evaluate(
        rules_array,
        rule_counts,
        pool_data["prefix_weights"],
        pool_data["prefix_cumsum"],
        pool_data["prefix_families"],
        pool_data["prefix_tiers"],
        pool_data["prefix_req_levels"],
        pool_data["suffix_weights"],
        pool_data["suffix_cumsum"],
        pool_data["suffix_families"],
        pool_data["suffix_tiers"],
        pool_data["suffix_req_levels"],
        pool_data["target_prefix_families"],
        pool_data["target_suffix_families"],
        pool_data["target_max_tiers"],
        price_array,
        max_currency_id,
        pool_data["ilvl"],
        pool_data["max_prefixes"],
        pool_data["max_suffixes"],
        n_trials,
        max_steps,
        base_seed,
        initial_state,
    )

    # Unpack results into Individual.fitness
    for i, ind in enumerate(population):
        ind.fitness = Fitness(
            expected_cost=float(fitness_array[i, 0]),
            success_rate=float(fitness_array[i, 1]),
            cost_p90=float(fitness_array[i, 2]),
            cost_median=float(fitness_array[i, 3]),
            cost_std=float(fitness_array[i, 4]),
            expected_steps=float(fitness_array[i, 5]),
            step_median=float(fitness_array[i, 6]),
            rule_count=ind.rulelist.size,
            fire_on_success=fire_success[i, :ind.rulelist.size].tolist(),
            fire_on_failure=fire_failure[i, :ind.rulelist.size].tolist(),
        )


def _evaluate_stub(population: list[Individual]) -> None:
    """Fallback: assign random fitness for testing without Rust.

    This allows the full GP loop to run (slowly, with meaningless fitness)
    for development and testing of the Python orchestration layer.
    """
    import random

    for ind in population:
        ind.fitness = Fitness(
            expected_cost=random.uniform(30, 500),
            success_rate=random.uniform(0.1, 0.99),
            cost_p90=random.uniform(50, 1000),
            cost_median=random.uniform(20, 400),
            cost_std=random.uniform(10, 200),
            expected_steps=random.uniform(10, 300),
            step_median=random.uniform(10, 200),
            rule_count=ind.rulelist.size,
            fire_on_success=[random.randint(0, 100) for _ in range(ind.rulelist.size)],
            fire_on_failure=[random.randint(0, 50) for _ in range(ind.rulelist.size)],
        )


def is_rust_available() -> bool:
    """Check if the Rust extension is importable."""
    return _RUST_AVAILABLE
