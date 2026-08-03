# Module Card: NSGA-II Selection (Balanced Variant)

## Problem

We have 3 Pareto objectives (expected_cost, failure_rate, cost_p90) and need
multi-objective selection that maintains diversity across all three dimensions.

## Critical Research Finding

**Classic NSGA-II fails with 3+ objectives** (proven mathematically):
- Zheng & Doerr (2024): exponential runtime lower bound for 3+ objectives
- Root cause: crowding distance regards objectives independently, causing
  population collapse toward the center of the front
- Result: classic NSGA-II cannot cover the full Pareto front in sub-exponential
  time when objectives ≥ 3

## Solution: Balanced NSGA-II (Doerr, Ivan & Krejca, Dec 2024)

A simple tie-breaking modification that provably fixes the 3+ objective problem:

**Paper:** "Speeding Up the NSGA-II With a Simple Tie-Breaking Rule" (arXiv:2412.11931)

**The fix:** When selecting from the critical front (same rank + same crowding
distance), distribute selections evenly across distinct objective values instead
of choosing uniformly at random.

### Why It Works

Classic NSGA-II's random tie-breaking preserves population imbalances — if most
individuals in the critical CD group have objective value v₁ and few have v₂,
random selection preferentially keeps v₁. The balanced variant forces equal
representation of each objective value, preventing any region from being lost.

### Proven Properties

- Efficient optimization for 3+ objectives (polynomial time, vs exponential for classic)
- Robust to suboptimal population size (moderate N oversizing doesn't hurt runtime)
- Preserves all Pareto-optimal objective values once discovered (no value loss)
- Wall-clock overhead: ~10× slower for the tie-breaking step only, which is ~15%
  of total sorting time — negligible overall

## Algorithm

### Step 1: Fast Non-Dominated Sort — O(MN²)

For combined parent + offspring population R (size 2N):
1. For each individual p, compute domination count (how many dominate p)
   and dominated set (which individuals p dominates)
2. Front 0 = all individuals with domination count 0
3. For each p in current front, decrement domination count of all q in p's
   dominated set. If q's count reaches 0, q goes in next front.
4. Repeat until all individuals are assigned to a front.

### Step 2: Crowding Distance

For each front F with |F| > 2:
1. For each objective m (3 total):
   - Sort F by objective m
   - Set boundary individuals' CD to ∞
   - For interior individuals: CD += (f[i+1] - f[i-1]) / (f_max - f_min)
2. Sum across all objectives

### Step 3: Survival Selection (Balanced)

Fill next generation (size N) from fronts:
1. Add entire fronts F₀, F₁, ... until adding the next front would exceed N
2. For the critical (splitting) front F*:
   a. First select all individuals with CD = ∞ (boundary solutions)
   b. Sort remaining by CD descending, select greedily
   c. **Balanced tie-breaking:** When multiple individuals share the same CD:
      - Partition them by objective value vector
      - Select ⌊remaining_spots / n_partitions⌋ from each partition
      - Fill remainder randomly from leftover
3. At equal CD AND same objective-value partition: prefer fewer rules (parsimony)

### Step 4: Binary Tournament Selection (for mating)

To select parents for crossover:
1. Pick 2 random individuals from the population
2. Winner = lower rank (better front), or if tied, higher crowding distance
3. If still tied: prefer fewer rules (parsimony tiebreaker)

## Parameters

```
Population size N = 200
Tournament size = 2 (binary)
Elite fraction: all individuals from fronts below critical survive unchanged
Parsimony: rule_count used as lexicographic tiebreaker (not an objective)
```

## Interface

```python
def non_dominated_sort(population: list[Individual]) -> list[list[Individual]]:
    """Assign Pareto fronts. Returns list of fronts (front 0 first)."""

def crowding_distance(front: list[Individual]) -> None:
    """Compute and assign crowding_distance to each individual in the front."""

def select_survivors(population: list[Individual], n: int) -> list[Individual]:
    """Select n survivors using balanced NSGA-II selection."""

def tournament_select(population: list[Individual]) -> Individual:
    """Binary tournament selection for parent picking."""
```

## File

`poe2_crafting_mcp/crafting/optimizer/nsga2.py`

## References

- Deb et al. (2002): "A Fast Elitist Non-dominated Sorting Genetic Algorithm
  for Multi-objective Optimization: NSGA-II" (50,000+ citations)
- Doerr, Ivan & Krejca (2024): "Speeding Up the NSGA-II With a Simple
  Tie-Breaking Rule" (arXiv:2412.11931) — the balanced variant
- Zheng & Doerr (2024): proven exponential failure of classic NSGA-II on 3+ objectives
