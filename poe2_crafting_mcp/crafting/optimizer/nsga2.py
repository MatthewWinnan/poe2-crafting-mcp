"""Balanced NSGA-II selection for the crafting optimizer.

Implements the Doerr, Ivan & Krejca (2024) balanced tie-breaking variant
that provably fixes classic NSGA-II's exponential failure on 3+ objectives.

Our 3 objectives (all minimized):
  - expected_cost
  - failure_rate (1 - success_rate)
  - cost_p90

References:
  - Deb et al. (2002): fast non-dominated sort, crowding distance
  - Doerr et al. (2024): balanced tie-breaking for 3+ objectives (arXiv:2412.11931)
"""

from __future__ import annotations

import random
from collections import defaultdict

from .gene import Fitness, Individual


# ── Non-Dominated Sorting ─────────────────────────────────────────────────────

def non_dominated_sort(population: list[Individual]) -> list[list[Individual]]:
    """Fast non-dominated sort — O(MN²) where M=objectives, N=pop size.

    Assigns pareto_rank to each individual. Returns list of fronts
    (front[0] = non-dominated, front[1] = dominated only by front[0], etc.)
    """
    n = len(population)
    if n == 0:
        return []

    # For each individual: who it dominates, and how many dominate it
    dominated_by_count: list[int] = [0] * n
    dominates: list[list[int]] = [[] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            fi = population[i].fitness
            fj = population[j].fitness

            if fi.dominates(fj):
                dominates[i].append(j)
                dominated_by_count[j] += 1
            elif fj.dominates(fi):
                dominates[j].append(i)
                dominated_by_count[i] += 1

    # Build fronts
    fronts: list[list[Individual]] = []
    current_front_indices: list[int] = [
        i for i in range(n) if dominated_by_count[i] == 0
    ]

    rank = 0
    while current_front_indices:
        front = []
        next_front_indices: list[int] = []

        for i in current_front_indices:
            population[i].pareto_rank = rank
            front.append(population[i])

            for j in dominates[i]:
                dominated_by_count[j] -= 1
                if dominated_by_count[j] == 0:
                    next_front_indices.append(j)

        fronts.append(front)
        current_front_indices = next_front_indices
        rank += 1

    return fronts


# ── Crowding Distance ─────────────────────────────────────────────────────────

def crowding_distance(front: list[Individual]) -> None:
    """Compute crowding distance for each individual in a front.

    Boundary solutions (min/max per objective) get infinity.
    Interior solutions get the sum of normalized distances per objective.
    """
    n = len(front)
    if n == 0:
        return

    for ind in front:
        ind.crowding_distance = 0.0

    if n <= 2:
        for ind in front:
            ind.crowding_distance = float("inf")
        return

    # 3 objectives: expected_cost, failure_rate, cost_p90
    for obj_idx in range(3):
        # Sort by this objective
        sorted_front = sorted(front, key=lambda ind: _get_objective(ind, obj_idx))

        # Boundary solutions get infinity
        sorted_front[0].crowding_distance = float("inf")
        sorted_front[-1].crowding_distance = float("inf")

        # Objective range for normalization
        f_min = _get_objective(sorted_front[0], obj_idx)
        f_max = _get_objective(sorted_front[-1], obj_idx)
        obj_range = f_max - f_min

        if obj_range == 0:
            continue

        # Interior solutions
        for i in range(1, n - 1):
            dist = (
                _get_objective(sorted_front[i + 1], obj_idx)
                - _get_objective(sorted_front[i - 1], obj_idx)
            ) / obj_range
            sorted_front[i].crowding_distance += dist


def _get_objective(ind: Individual, idx: int) -> float:
    """Get the idx-th objective value (all minimized)."""
    if idx == 0:
        return ind.fitness.expected_cost
    elif idx == 1:
        return ind.fitness.failure_rate
    else:
        return ind.fitness.cost_p90


# ── Balanced Survival Selection ───────────────────────────────────────────────

def select_survivors(population: list[Individual], n: int) -> list[Individual]:
    """Select n survivors using balanced NSGA-II.

    1. Non-dominated sort into fronts
    2. Add full fronts until the next would exceed n
    3. For the critical (splitting) front: crowding distance + balanced tie-breaking
    4. Parsimony tiebreaker at equal CD + equal objectives
    """
    fronts = non_dominated_sort(population)

    survivors: list[Individual] = []

    for front in fronts:
        if len(survivors) + len(front) <= n:
            # Entire front fits — add all
            crowding_distance(front)
            survivors.extend(front)
        else:
            # Critical front — need to split
            remaining = n - len(survivors)
            crowding_distance(front)
            selected = _balanced_select_from_front(front, remaining)
            survivors.extend(selected)
            break

    return survivors


def _balanced_select_from_front(front: list[Individual], n: int) -> list[Individual]:
    """Select n individuals from a critical front with balanced tie-breaking.

    1. Select all individuals with CD = infinity (boundary solutions)
    2. Group remaining by crowding distance
    3. For the critical CD group (same CD, need to split):
       - Partition by objective value vector
       - Select floor(remaining/n_partitions) from each partition
       - Fill remainder randomly
    4. Parsimony tiebreaker within same partition
    """
    if n >= len(front):
        return front[:]

    # Sort by crowding distance descending, then parsimony (fewer rules preferred)
    sorted_front = sorted(
        front,
        key=lambda ind: (-ind.crowding_distance, ind.rulelist.size),
    )

    selected: list[Individual] = []

    # Greedily add by descending CD until we hit a tie group that must be split
    i = 0
    while i < len(sorted_front) and len(selected) < n:
        # Find the group of individuals with the same crowding distance
        current_cd = sorted_front[i].crowding_distance
        group_start = i
        while i < len(sorted_front) and sorted_front[i].crowding_distance == current_cd:
            i += 1
        group = sorted_front[group_start:i]

        if len(selected) + len(group) <= n:
            # Entire group fits
            selected.extend(group)
        else:
            # Critical group — apply balanced tie-breaking
            remaining = n - len(selected)
            balanced = _balanced_tie_break(group, remaining)
            selected.extend(balanced)
            break

    return selected


def _balanced_tie_break(group: list[Individual], n: int) -> list[Individual]:
    """Balanced tie-breaking: distribute selections evenly by objective value.

    This is the key innovation from Doerr et al. (2024) that fixes NSGA-II
    for 3+ objectives.
    """
    if n >= len(group):
        return group[:]

    # Partition by objective value vector (discretized for grouping)
    partitions: dict[tuple[float, float, float], list[Individual]] = defaultdict(list)
    for ind in group:
        # Round objectives to avoid floating-point grouping issues
        key = (
            round(ind.fitness.expected_cost, 2),
            round(ind.fitness.failure_rate, 4),
            round(ind.fitness.cost_p90, 2),
        )
        partitions[key].append(ind)

    num_partitions = len(partitions)
    if num_partitions == 0:
        return []

    # Select floor(n / num_partitions) from each partition
    per_partition = n // num_partitions
    selected: list[Individual] = []

    for key, members in partitions.items():
        # Sort by parsimony (fewer rules preferred)
        members.sort(key=lambda ind: ind.rulelist.size)
        take = min(per_partition, len(members))
        selected.extend(members[:take])

    # Fill remainder randomly from leftover
    remaining = n - len(selected)
    if remaining > 0:
        leftover = [ind for ind in group if ind not in selected]
        if leftover:
            # Prefer smaller rule-lists (parsimony)
            leftover.sort(key=lambda ind: ind.rulelist.size)
            selected.extend(leftover[:remaining])

    return selected[:n]


# ── Binary Tournament Selection ───────────────────────────────────────────────

def tournament_select(population: list[Individual]) -> Individual:
    """Binary tournament selection for parent picking.

    Compare two random individuals:
    1. Lower Pareto rank wins
    2. If tied: higher crowding distance wins
    3. If still tied: fewer rules wins (parsimony)
    """
    a = random.choice(population)
    b = random.choice(population)
    return _tournament_winner(a, b)


def _tournament_winner(a: Individual, b: Individual) -> Individual:
    """Pick the winner of a binary tournament."""
    # Lower rank is better
    if a.pareto_rank < b.pareto_rank:
        return a
    if b.pareto_rank < a.pareto_rank:
        return b

    # Same rank: higher crowding distance is better (more diverse)
    if a.crowding_distance > b.crowding_distance:
        return a
    if b.crowding_distance > a.crowding_distance:
        return b

    # Same rank and CD: parsimony — fewer rules preferred
    if a.rulelist.size < b.rulelist.size:
        return a
    if b.rulelist.size < a.rulelist.size:
        return b

    # Truly tied: random
    return random.choice([a, b])
