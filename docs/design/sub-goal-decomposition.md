# Sub-Goal Decomposition for the Crafting Optimizer

## Date: 2026-08-04
## Status: Design — ready for implementation

---

## Problem

The GP optimizer discovers good strategies for 1-3 target crafts but fails on
5+ targets because:

1. **Noisy fitness signal** — at 0.086% success rate, 1000 MC trials produces
   zero successes 42% of the time. The GP can't differentiate strategies.
2. **Combinatorial search space** — a correct 12-rule deterministic recipe is a
   needle in a haystack when rules interact with 25 predicates × 40 currencies.
3. **No phase reasoning** — the GP treats all targets uniformly and tries to
   find ONE rule-list for the entire craft. Mirror-tier crafts are sequential
   multi-phase processes that require decomposition.

## Solution: Sequential Sub-Goal Decomposition (Tier 1)

Break an N-target craft into N single-target phases. Optimize each phase
independently using the existing proven 1-target GP. Sum the costs.

**Literature basis:** Layered Learning (Stone & Veloso, 2000), Options/SMDP
framework (Sutton, Precup & Singh, 1999). Both validate that decomposition
into sequential sub-problems converges faster than monolithic optimization
when sub-problems have independent fitness landscapes.

**Search space reduction:** S^N (monolithic) → N×S (decomposed). For 5 targets,
this is the difference between "impossible in 50 generations" and "3 seconds
per phase."

---

## Architecture

### New Data Structures

```python
# gene.py additions

@dataclass
class PhaseTarget:
    """Targets for a single phase of a multi-step craft.

    A phase may pursue one or more targets simultaneously. Single-target
    phases are the common case; multi-target phases enable Tier 3 grouping.
    """
    targets: list[ModTarget]               # what this phase achieves
    starting_mods: list[tuple[int, str, int]]  # (family_id, affix_type, tier) already on item
    starting_rarity: int = 0               # 0=Normal, 1=Magic, 2=Rare
    starting_flags: int = 0                # essence/desecrated/divined bits
    phase_index: int = 0                   # position in the sequence


@dataclass
class DecomposedResult:
    """Result of multi-target optimization via sub-goal decomposition."""
    phases: list[PhaseResult]
    total_expected_cost: float
    total_success_rate: float          # product of phase success rates
    ordering: list[int]                # which target indices in which order
    ordering_rationale: str            # why this ordering was chosen
    trade_price: float = float("inf")
    verdict: str = ""

    # Comparison data: top N orderings evaluated
    ordering_candidates: list[tuple[list[int], float]] = field(default_factory=list)


@dataclass
class PhaseResult:
    """Result of optimizing one phase."""
    phase_index: int
    target: PhaseTarget
    strategy: CraftingStrategy         # best strategy from single-target GP
    expected_cost: float               # amortized cost of THIS phase
    success_rate: float
    restart_risk: str                  # "safe" | "destructive" | "full_restart"
    cumulative_cost: float             # sum of this + all prior phases
```

### New Functions

#### `decompose.py` — Phase Decomposition & Ordering

```python
def decompose_targets(
    target: CraftTarget,
    pool_data: dict,
    prices: PriceCache,
) -> list[list[int]]:
    """Generate candidate phase orderings for a multi-target craft.

    For N <= 7: all N! permutations.
    For N > 7: heuristic orderings (WSJF, cheapest-first, most-constrained-first).

    Returns list of orderings, each an index permutation of target.targets.
    """


def classify_phase_risk(
    phase_target: PhaseTarget,
    pool_data: dict,
) -> str:
    """Classify whether a phase can destroy prior-phase mods.

    Returns:
        "safe"        — phase only adds mods (exalt, essence). Cannot destroy
                        prior work. Phase failure = retry this phase only.
        "destructive" — phase uses annul/chaos. Can remove prior-phase mods.
                        Phase failure may require full restart.
        "full_restart"— phase uses scour/alchemy. Definitely destroys prior work.
    """


def estimate_phase_cost_quick(
    target_mod: ModTarget,
    starting_mods: list[tuple[int, str, int]],
    pool_data: dict,
    prices: PriceCache,
) -> tuple[float, float]:
    """Quick analytical cost estimate for one phase (no GP, no MC).

    Uses probability_of() from the existing craft simulator to estimate
    cost and success rate. Used for ordering heuristics — the full GP
    runs on the chosen ordering.

    Returns (expected_cost, success_rate).
    """


def optimal_ordering(
    target: CraftTarget,
    pool_data: dict,
    prices: PriceCache,
    max_orderings: int = 120,
) -> list[int]:
    """Find the optimal phase ordering using WSJF heuristic.

    Algorithm:
    1. For each target, estimate (cost_i, success_rate_i) via quick analytical.
    2. Classify each phase's risk level.
    3. Sort by: deterministic first, then c_i / (1 - p_i) ascending (WSJF).
    4. For N <= 7, also enumerate all N! and evaluate each with quick costs.
    5. Return the ordering with lowest estimated total cost.

    The WSJF heuristic (from scheduling theory) minimizes expected total cost
    when phase failure requires re-executing prior phases.
    """
```

#### `runner.py` — Multi-Target Orchestrator

```python
def optimize_multi_target(
    pool_data: dict,
    target: CraftTarget,
    prices: PriceCache,
    config: OptimizerConfig | None = None,
    ordering: list[int] | None = None,
    max_orderings: int = 120,
) -> DecomposedResult:
    """Optimize a multi-target craft via sub-goal decomposition.

    Algorithm:
    1. If len(targets) <= 3, delegate to optimize() directly (monolithic is fine).
    2. Determine phase ordering (auto or user-specified).
    3. For each phase in order:
       a. Build PhaseTarget with starting mods from prior phases.
       b. Rebuild pool_data targets for just this phase's targets
          (but keep ALL target families as "protected" from annul).
       c. Run optimize() for this single phase.
       d. Record the best strategy and expected cost.
       e. Update starting state for next phase.
    4. Sum costs across phases.
    5. Compare vs trade price for verdict.

    Args:
        pool_data: mod pool from preflight
        target: full multi-target CraftTarget
        prices: economy prices
        config: GP parameters (applied to each phase)
        ordering: explicit phase order (indices into target.targets).
                  If None, auto-detect via WSJF heuristic.
        max_orderings: max permutations to evaluate for ordering search.
    """
```

### Changes to Existing Code

#### `evaluate.rs` — Starting State Support

Currently every trial starts from `ItemState::blank()`. To support sub-goal
decomposition, the evaluator needs to accept a starting item state.

```rust
// evaluate.rs — change ItemState::blank() to a parameter

pub fn evaluate_rulelist(
    rules: &[Rule],
    n_rules: usize,
    pool: &ModPool,
    prices: &[f32],
    max_currency_id: usize,
    n_trials: u32,
    max_steps: u32,
    seed: u64,
    initial_state: Option<&ItemState>,  // NEW: starting state for sub-goal phases
) -> EvalResult {
    // ...
    for _ in 0..n_trials {
        let mut item = match initial_state {
            Some(state) => {
                let mut s = state.clone();
                s.cost_spent = 0.0;   // reset cost for THIS phase
                s.step_count = 0;
                s
            }
            None => ItemState::blank(),
        };
        // ... rest unchanged
    }
}
```

#### `batch.rs` — Initial State Array

```rust
// batch.rs — add optional initial_state parameter

pub fn evaluate_population(
    // ... existing params ...
    // NEW: optional starting state (flat array, or empty for blank)
    initial_prefix_families: Option<PyReadonlyArray1<'py, u16>>,  // [3] u16
    initial_suffix_families: Option<PyReadonlyArray1<'py, u16>>,  // [3] u16
    initial_prefix_tiers: Option<PyReadonlyArray1<'py, u8>>,      // [3] u8
    initial_suffix_tiers: Option<PyReadonlyArray1<'py, u8>>,      // [3] u8
    initial_rarity: Option<u8>,
    initial_flags: Option<u8>,
    initial_fractured_mask: Option<u8>,
) -> PyResult<(...)> {
    // Build initial ItemState if any initial_ params are provided
    let initial_state = if initial_rarity.is_some() {
        Some(ItemState { /* from params */ })
    } else {
        None
    };
    // Pass to evaluate_rulelist
}
```

**Design choice:** The initial state is the SAME for all individuals in the
population within a single phase. This is correct because every individual
in phase K starts from the item state that phase K-1 produced. We pass it
once, not per-individual.

#### `bridge.py` — Forward Initial State

```python
def evaluate_population_rust(
    population: list[Individual],
    pool_data: dict[str, np.ndarray],
    prices: PriceCache,
    n_trials: int = 500,
    max_steps: int = 500,
    base_seed: int = 0,
    initial_state: dict | None = None,  # NEW
) -> None:
    # ... serialize initial_state into arrays, pass to Rust
```

#### `preflight.py` — Phase-Aware Target Building

```python
def preflight_phase(
    item_class: str,
    ilvl: int,
    phase_targets: list[tuple[str, str, int]],
    all_targets: list[tuple[str, str, int]],  # ALL targets (for annul protection)
    db_path: str | None = None,
) -> tuple[dict, PriceCache, CraftTarget]:
    """Preflight for a single phase of a decomposed craft.

    Like preflight(), but:
    - phase_targets: what THIS phase is trying to achieve
    - all_targets: ALL targets across all phases (so annul predicates
      protect mods from prior phases)

    The pool_data encodes all_targets as target families (for annul protection)
    but the Rust evaluator's success check uses only phase_targets.
    """
```

**Critical subtlety:** The `all_targets_at_tier()` check in Rust must only
check THIS phase's targets for success, but the `HAS_NON_TARGET_REMOVABLE`
predicate must protect ALL targets (including prior phases). This requires
splitting the target arrays:

```rust
// pool.rs — split targets into "success targets" and "protected targets"
pub struct ModPool {
    // ... existing fields ...

    // Phase success check — only this phase's targets
    pub phase_target_families: Vec<u16>,
    pub phase_target_max_tiers: Vec<u8>,

    // Annul protection — ALL targets across all phases
    pub all_target_families: Vec<u16>,  // already exists, just redefine semantics
    pub target_max_tiers: Vec<u8>,      // already exists
}
```

#### `seeds.py` — Phase-Aware Seeds

The seed strategies need adjustment for later phases. Phase 1 seeds are
normal (transmute, alchemy, chaos). Phase 2+ seeds should:
- Start with the item already having mods (skip the "make it rare" step)
- Focus on exalt/essence/annul strategies
- Include restart-to-phase-start (not restart-to-blank)

```python
def create_seeded_population_for_phase(
    pop_size: int,
    seed_fraction: float,
    phase: PhaseTarget,
) -> list[RuleList]:
    """Generate seed strategies appropriate for this phase.

    Phase 1 (starting blank): normal seeds (alt-regal, alchemy, chaos)
    Phase 2+ (starting with mods): exalt-focused seeds, essence seeds,
    annul+exalt seeds. Skip all "make it rare" strategies.
    """
```

---

## Phase Ordering Algorithm

### WSJF Heuristic (Weighted Shortest Job First)

For each target i, compute:
- `c_i` = estimated cost of achieving target i (from quick analytical)
- `p_i` = probability of success per attempt
- `r_i` = risk classification ("safe", "destructive", "full_restart")

Ordering rules (priority order):
1. **Deterministic phases first** — buy magic, essence. Cost is fixed, can't fail.
   These always go at the start regardless of WSJF score.
2. **Safe additive phases before destructive phases** — exalt into open slot
   before annul loops. Safe phases can't destroy prior work.
3. **Among same-risk phases, order by `c_i / (1 - p_i)` ascending** — this is
   the WSJF rule. Phases with low cost relative to failure rate go first,
   minimizing the expected restart cascade cost.

### Restart Cost Model

When phase K fails:
- If phase K is **safe** (exalt only): retry phase K. Cost = c_K / p_K.
  Prior phases are unaffected.
- If phase K is **destructive** (annul loop): with probability q, annul
  removes a prior-phase mod. Restart cost = sum(c_1..c_{K-1}) + c_K.
  The optimizer models this via the existing SCOUR/BUY_BASE restart logic.
- If phase K is **full_restart** (chaos/alchemy): always destroys prior work.
  Should only be used as phase 1.

Total expected cost accounting for restarts:

```
E[total] = sum over phases K:
    if safe:   c_K / p_K
    if risky:  c_K / p_K + (1 - p_K) * restart_probability * sum(c_1..c_{K-1})
```

For the ordering search, we use the quick analytical estimates. The full GP
runs only on the best ordering.

### Enumeration Strategy

| N targets | Orderings | Strategy |
|-----------|-----------|----------|
| 1-3       | 1-6       | Monolithic optimize() (no decomposition needed) |
| 4-5       | 24-120    | Enumerate all, quick-cost each, GP on best 3 |
| 6-7       | 720-5040  | Enumerate all, quick-cost each, GP on best 1 |
| 8+        | too many  | WSJF heuristic only, GP on that ordering |

---

## Free-Hit Detection

When a phase uses multi-mod currencies (alchemy, chaos, essence+regal), it
may accidentally hit targets from later phases. The orchestrator handles this:

```python
def detect_free_hits(
    phase_strategy: CraftingStrategy,
    remaining_targets: list[ModTarget],
    pool_data: dict,
) -> list[int]:
    """Identify which remaining targets might be hit for free.

    Run a small MC sample (100 trials) of the phase strategy and check
    what mods end up on the item. If a later-phase target appears in >30%
    of successful trials, flag it as a potential free hit.

    Returns indices of remaining_targets that can be skipped.
    """
```

When free hits are detected, the orchestrator skips those phases and adjusts
the total cost downward. This captures 90% of the "grouping" benefit from
Tier 3 without the complexity.

---

## Tier 2 Upgrade Path: Cooperative Coevolution

The Tier 1 design enables a natural CC upgrade:

```python
def optimize_cooperative(
    pool_data: dict,
    target: CraftTarget,
    prices: PriceCache,
    config: OptimizerConfig,
    ordering: list[int],
) -> DecomposedResult:
    """Cooperative coevolution: N sub-populations, one per phase.

    Each generation:
    1. For each phase K (in order):
       a. Evaluate phase K's population using:
          - Starting state from phase K-1's current champion
          - Phase K's own individuals
       b. Select survivors within phase K's population
       c. Breed offspring for phase K
    2. Repeat until convergence

    This allows phase strategies to co-adapt. If phase 1's champion
    changes (e.g., switches from alt-spam to buy-magic), phase 2's
    population automatically adjusts because it's evaluated on the
    new starting state.
    """
```

**What changes from Tier 1:**
- Instead of sequential optimize() calls, maintain N populations simultaneously
- Each population is evaluated in the context of the other phases' champions
- The evaluate_population_rust() call already supports initial_state
- Just need a new outer loop in runner.py

**What stays the same:**
- All data structures (PhaseTarget, DecomposedResult, PhaseResult)
- The ordering logic
- The Rust evaluator changes (initial_state support)
- The preflight phase-aware target building

---

## Tier 3 Upgrade Path: Hierarchical GP

Tier 3 adds an outer GP that evolves **target groupings** — which targets to
pursue together in a single phase vs. separately.

```python
@dataclass
class Grouping:
    """A partition of N targets into K groups (phases)."""
    groups: list[list[int]]    # e.g. [[0,1], [2], [3,4]] for 5 targets in 3 phases
    ordering: list[int]        # order of groups: [1, 0, 2] means group 1 first

    @property
    def n_phases(self) -> int:
        return len(self.groups)
```

The outer GP evolves Grouping individuals. Each is evaluated by running
Tier 1 (or Tier 2) on the grouped phases and summing costs.

**What changes from Tier 2:**
- New genome type (Grouping) with its own crossover/mutation operators
- Outer population of groupings, inner populations of phase strategies
- PhaseTarget.targets becomes a list (already supported in the design)

**What stays the same:**
- Everything in Tier 1 and Tier 2
- The Rust evaluator, bridge, preflight

---

## Implementation Plan

### Phase 1: Python Orchestration (no Rust changes)

1. Add `PhaseTarget`, `PhaseResult`, `DecomposedResult` to `gene.py`
2. Create `decompose.py` with ordering logic (WSJF, enumeration)
3. Add `optimize_multi_target()` to `runner.py`
4. Update CLI to auto-detect and decompose when targets > 3
5. Test with the 5-target Gloves case from the shortcomings doc

**Shortcut for Phase 1:** Instead of modifying Rust to accept initial_state,
encode the starting mods as rules at the top of the rule-list. For example,
if phase 2 starts with a Rare item that has FireDamage:

```python
# Inject "setup" rules at the top of every individual in phase 2's population
setup_rules = [
    Rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.BUY_MAGIC)),
    # BUY_MAGIC already places the first missing target (FireDamage)
    Rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.REGAL)),
]
```

This avoids Rust changes entirely — the GP will handle the setup as part of
its strategy. The cost of the setup rules is included in the MC simulation
naturally.

**Limitation:** This only works when prior-phase mods can be acquired via
BUY_MAGIC / ESSENCE_UPGRADE. For phases starting from arbitrary item states,
we'll need the Rust initial_state support (Phase 2).

### Phase 2: Rust Initial State Support

1. Add `initial_state: Option<&ItemState>` to `evaluate_rulelist()`
2. Add initial state arrays to `evaluate_population()` in batch.rs
3. Update `bridge.py` to serialize and pass initial state
4. Update `seeds.py` with phase-aware seed strategies
5. Add free-hit detection
6. Full integration testing

### Phase 3: Cooperative Coevolution (Tier 2)

1. Add `optimize_cooperative()` to runner.py
2. Maintain N sub-populations
3. Cross-evaluate with champion context
4. Compare results vs. Tier 1 sequential

### Phase 4: Hierarchical GP (Tier 3)

1. Add Grouping genome with crossover/mutation
2. Outer GP loop evaluating groupings
3. Bell number pruning for large N

---

## Example: 5-Target Gloves Craft

**Targets:**
- T2+ FireDamage (prefix)
- T2+ ColdDamage (prefix)
- T2+ PhysicalDamage (prefix)
- T5+ IncreasedAttackSpeed (suffix)
- ArcaneSurgeOnCrit (suffix, abyss mod via desecration)

### Ordering Analysis

| Target | Phase Type | Est. Cost | Success Rate | Risk | WSJF Score |
|--------|-----------|-----------|-------------|------|------------|
| FireDamage | BUY_MAGIC | 35c | 100% | safe | 0 (deterministic) |
| ColdDamage | ESSENCE | ~1c | ~100% | safe | 0 (deterministic) |
| PhysicalDamage | SINISTRAL_EXALT | ~500c | 3% | safe | 515 |
| AtkSpeed | DEXTRAL_EXALT | ~50c | 15% | safe | 59 |
| ArcaneSurge | DESECRATE+REVEAL | ~200c | 20% | safe* | 250 |

*Desecrate+Reveal adds a suffix — safe if suffix slot is open.

### Optimal Ordering (WSJF)

1. FireDamage (deterministic, 35c)
2. ColdDamage (deterministic, 1c) — via Regal first, then Essence
3. AtkSpeed (lowest WSJF=59, suffix exalt)
4. ArcaneSurge (WSJF=250, desecrate+reveal)
5. PhysicalDamage (highest WSJF=515, prefix exalt)

**Total estimated cost:** 35 + 1 + 50/0.15 + 200/0.20 + 500/0.03 ≈ 35 + 1 + 333 + 1000 + 16667 ≈ 18,036c

Note: all phases are "safe" (additive only — exalt into open slot, essence,
desecrate+reveal). No annul loops. So ordering among the probabilistic
phases doesn't matter for restart cost — WSJF is a tiebreaker for GP
signal quality (easier phases converge faster, providing better intermediate
results for user feedback).

### Phase 1 Shortcut Encoding

For Phase 1 implementation (no Rust initial_state), encode prior-phase
mods via setup rules:

```
Phase 3 (AtkSpeed) setup rules:
  IF rarity_is(NORMAL) THEN buy_magic        # gets FireDamage
  IF rarity_is(MAGIC)  THEN regal             # Magic → Rare
  IF no_essence_mod    THEN essence_upgrade   # gets ColdDamage
  # Now: Rare with Fire+Cold prefixes, 1 suffix open, 2 prefixes open
  # GP optimizes from here for AtkSpeed suffix
```

The setup cost (~36c) is included in the MC simulation. The GP only needs to
discover "dextral exalt until AtkSpeed hits" — a simple 1-target problem.

---

## Success Criteria

1. 5-target Gloves case produces a viable decomposed strategy with <20,000c
   estimated cost (vs. 42M c monolithic failure)
2. Each phase independently converges in <5 seconds
3. Total optimization time for 5 targets: <2 minutes (including ordering search)
4. Result output shows per-phase breakdown with costs and strategies
5. CLI: `poe2-optimize Gloves_int --target "..." --decompose` (auto for >3)

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `optimizer/decompose.py` | **NEW** — ordering logic, phase decomposition |
| `optimizer/gene.py` | Add PhaseTarget, PhaseResult, DecomposedResult |
| `optimizer/runner.py` | Add optimize_multi_target() |
| `optimizer/preflight.py` | Add preflight_phase() |
| `optimizer/seeds.py` | Add create_seeded_population_for_phase() |
| `optimizer/cli.py` | Add --decompose flag, multi-target output |
| `optimizer/bridge.py` | Add initial_state support (Phase 2) |
| `crates/.../evaluate.rs` | Add initial_state param (Phase 2) |
| `crates/.../batch.rs` | Add initial state arrays (Phase 2) |
| `crates/.../pool.rs` | Split phase vs protected targets (Phase 2) |
