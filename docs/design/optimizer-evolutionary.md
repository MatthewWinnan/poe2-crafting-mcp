# Module Card: Evolutionary Crafting Optimizer

## Overview

A batch-simulation system that discovers optimal crafting paths by evolving
thousands of items through crafting steps, pruning failures, and learning
which strategies yield the best cost/success ratio.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Crafting Optimizer                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐ │
│  │ 10k Items│──▶│Apply Step│──▶│ Evaluate │──▶│ Decide │ │
│  │ (blank)  │   │ (batch)  │   │ (prune)  │   │ (next) │ │
│  └──────────┘   └──────────┘   └──────────┘   └────────┘ │
│       ▲                                            │       │
│       └────────────────────────────────────────────┘       │
│                    (repeat until target or budget)          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Inputs:                                                    │
│    - Base item class + ilvl                                 │
│    - Target mods (families + min tier)                      │
│    - Budget cap (max chaos to spend)                        │
│    - Available currencies + prices                          │
│                                                             │
│  Outputs:                                                   │
│    - Optimal crafting path (sequence of steps)              │
│    - Success rate at budget                                 │
│    - Cost distribution (avg, median, p90)                   │
│    - Comparison vs trade price                              │
├─────────────────────────────────────────────────────────────┤
│  Decision Engine (hybrid):                                  │
│    1. Heuristic rules (from crafting guide research):       │
│       - "If item has 0 target mods → transmute spam"       │
│       - "If item has 1 target prefix → regal to rare"      │
│       - "If prefixes full, no targets → annul + retry"     │
│       - "If 2/3 targets hit → exalt for 3rd"               │
│    2. Learned rules (from simulation feedback):             │
│       - Track which decisions led to success/failure        │
│       - Adjust thresholds based on cost outcomes            │
│       - "Greater transmute better than regular for T1"     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Performance Requirements:                                  │
│    - 10,000 items × 50 steps = 500k pool evaluations       │
│    - Target: <5 seconds for full optimization               │
│    - Solution: Rust inner loop (PyO3) or numpy vectorized   │
│    - Pool data pre-computed as numpy arrays                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  State per Item:                                            │
│    - rarity (u8: 0=normal, 1=magic, 2=rare)                │
│    - prefix_families: [u16; 3] (0 = empty)                 │
│    - suffix_families: [u16; 3] (0 = empty)                 │
│    - fractured_mask: u8                                     │
│    - total_cost_spent: f32                                  │
│    - step_count: u16                                        │
│    - status: alive | success | failed                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Decision Tree (Initial Heuristics)

```
START (Normal item, 0 mods)
  │
  ├─ targets are all prefixes?
  │   ├─ YES: Transmute spam until 1st target prefix → Aug (suffix) → Regal
  │   └─ NO: Alchemy and evaluate
  │
  ├─ item has 1 target mod?
  │   ├─ Magic: Regal to Rare
  │   └─ Rare: continue to exalt
  │
  ├─ item is Rare, has open prefix slots, target prefixes remaining?
  │   ├─ Use Sinistral Exalt omen if target is prefix + omen is cheap
  │   ├─ Use regular Exalt if pool is favorable
  │   └─ If prefixes full with non-targets: Annul (risk!) or start over
  │
  ├─ all target prefixes hit?
  │   ├─ Fill suffixes (exalt, or bench craft)
  │   └─ SUCCESS
  │
  └─ budget exceeded? → FAIL (report cost so far)
```

## Integration Points

- **Data**: get_craftable_mods() for pool weights
- **Prices**: _get_live_prices() for currency costs
- **Trade**: compare result cost vs trade listing prices
- **PoB**: simulate final item to verify DPS gain
- **MCP**: optimize_craft_path(base, targets, budget)
- **CLI**: poe2-lookup craft-optimize "Gold Gloves" --target "PhysicalDamage:1,FireDamage:1,ColdDamage:1"

## Dependencies

- Rust toolchain + maturin + pyo3 (added to Nix flake) — MC inner loop from day one
- rayon (Rust) — parallel evaluation of population across CPU cores
- numpy (Python) — zero-copy array passing across PyO3 boundary
- Existing mod_weights data (poe2db seeded)
- Live economy prices (poe.ninja cached)

## Implementation Order

1. **Nix flake**: add rustc, cargo, maturin, rust-analyzer to devShell
2. **Rust crate scaffold**: `crates/poe2-optimizer/` with PyO3 boilerplate
3. **item_state.rs + pool.rs**: compact types, weighted sampling
4. **conditions.rs + actions.rs**: predicate eval, currency application
5. **evaluate.rs**: single rule-list MC evaluation (validate correctness)
6. **batch.rs**: rayon parallel population evaluation
7. **Python bridge.py**: serialize RuleList/pool/prices to flat arrays
8. **Python gene.py**: dataclasses for Rule, RuleList, Condition, Action, CraftTarget
9. **Python nsga2.py + operators.py**: selection + genetic operators
10. **Python seeds.py**: hand-written heuristic rule-lists
11. **Python runner.py + CLI**: end-to-end optimization flow
12. **clustering.py**: post-convergence strategy family output
