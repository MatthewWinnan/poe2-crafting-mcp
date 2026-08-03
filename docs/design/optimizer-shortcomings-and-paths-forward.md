# Optimizer: Current State, Shortcomings & Paths Forward

## Date: 2026-08-03

## What Works

### Easy-Medium Crafts (1-3 high-weight targets)
- **T1 Life on Gloves**: 0.4c, 100% success — correctly trivial
- **T1 Life + T1 ES + T1 FireRes**: 145c amortized, 7.4% success — correct CRAFT verdict
- Alt-regal, alchemy spam, chaos+whittling all produce realistic costs
- Correctly identifies CRAFT vs BUY breakpoints
- GP discovers novel strategy combinations (crossover between seeds)

### Architecture
- Rust MC evaluator: 375k-750k evals/sec on real pool data (178 mods)
- Balanced NSGA-II (3-objective safe): expected_cost, failure_rate, cost_p90
- QD archive maintaining strategy diversity across behavioral descriptors
- Credit-guided mutation (PPL-ST): harmful rules mutated first
- 12 seed strategies covering the full 0.5 meta

### Simulation Fidelity (verified against craft simulator)
- Mod pool weights match Craft of Exile exactly (63,700 prefix, 80,500 suffix for Gloves_int)
- Tier numbering: T1=1 (best), T9=9 (worst)
- One essence per item (enforced)
- One desecration per item (enforced)  
- Desecration pick-from-3: ~20% target hit rate (models 14-option Well of Souls)
- Essence: NO random fill (only adds 1 guaranteed mod, matches craft sim)
- Amortized cost: total spend across ALL trials / successes (correct player expectation)
- Cost preserved across restarts (scour/buy_base don't zero the counter)

---

## What Doesn't Work: Mirror-Tier Multi-Target Crafts

### The Problem
A 5-target craft like "T2+ Fire/Cold/Phys Damage + T5+ AtkSpd + ArcaneSurgeOnCrit" on Gloves requires a specific deterministic multi-step recipe that the GP cannot currently discover.

### Why
1. **Extremely low per-trial success rate** (~0.086% for the correct strategy)
2. **Noisy fitness signal**: at 1000 MC trials, the correct strategy shows 0 successes 42% of the time — the GP can't differentiate it from random
3. **Enormous search space**: a valid 12-rule deterministic recipe with exact rule ordering is a needle in a haystack
4. **The annul-exalt dilemma**: annulling risks removing target mods (1/3 chance per sinistral annul with 2 targets + 1 junk prefix). This makes the core loop fragile
5. **Restart cost dominance**: most of the 42M chaos amortized cost is from 50M restarts at 35c each, not from the actual crafting currency

### The Core Issue
The GP treats all targets uniformly and tries to find ONE rule-list that handles the entire craft. But mirror-tier crafts are **sequential multi-phase processes** where:
- Phase 1: Secure first target (buy magic with fire — deterministic, 35c)
- Phase 2: Secure second target (essence for cold — deterministic, ~free)
- Phase 3: Exalt for third target (sinistral exalt loop — probabilistic, expensive)
- Phase 4: Abyss mod (desecrate+reveal — 20% per attempt)
- Phase 5: Fill suffixes (dextral exalt — probabilistic)

Each phase has different cost/probability characteristics. The GP can't reason about this decomposition.

---

## Paths Forward

### Path A: Sub-Goal Decomposition (Recommended)

Break the optimization into independent sub-goals. Optimize EACH step separately:

```
Step 1: "Get T2+ FireDamage on a Magic item" → alt spam, cost ~X
Step 2: "Add T2+ ColdDamage to a Rare with Fire" → essence, cost ~Y  
Step 3: "Add T2+ PhysDamage prefix to item with Fire+Cold" → exalt loop, cost ~Z
Step 4: "Add ArcaneSurgeOnCrit suffix" → desecrate+reveal, cost ~W
Step 5: "Add T5+ AtkSpd suffix" → dextral exalt, cost ~V
Total expected cost = X + Y + Z + W + V
```

Each sub-goal is a 1-target optimization that the GP handles well (proven).
The total cost is the sum. Phase ordering is either user-specified or tried all permutations.

**Implementation**: 
- `optimize_multi_target()` that calls `optimize()` for each target sequentially
- Each subsequent call starts from the item state achieved by the previous step
- Much higher success rates per step → GP has strong signal

### Path B: Increased MC Trials (Brute Force)

Simply increase `mc_trials` to 50,000+ for hard crafts. The seed 11 strategy DOES succeed at 0.086% — it just needs enough trials for the GP to detect it.

**Cost**: 50k trials × 200 pop × 50 gen = 500M evaluations. At 750k/sec = ~670 seconds (11 minutes). Feasible but slow.

**Limitation**: only helps if a strategy exists that succeeds at >0.01%. For crafts that are even harder, this still fails.

### Path C: Recipe Mode (Guided Discovery)

User specifies the strategy structure (which currencies in which order), optimizer evaluates the COST of each step. No GP — just Monte Carlo evaluation of a given recipe.

```python
recipe = [
    ("buy_magic", {"family": "FireDamage", "max_tier": 2}),
    ("regal", {}),
    ("essence_upgrade", {"family": "ColdDamage"}),
    ("exalt_loop", {"family": "PhysicalDamage", "max_tier": 2, "omen": "sinistral"}),
    ("desecrate_reveal", {"family": "ArcaneSurgeOnCrit"}),
    ("exalt_loop", {"family": "IncreasedAttackSpeed", "max_tier": 5, "omen": "dextral"}),
]
cost = evaluate_recipe(recipe, pool, prices)
```

**Advantage**: gives exact cost for the player's intended strategy.
**Limitation**: doesn't discover novel strategies (user must know the recipe).

### Path D: Hierarchical GP (Advanced)

A two-level GP where:
- **Outer level**: evolves the SEQUENCE of sub-goals (which target to pursue in which order)
- **Inner level**: optimizes the strategy for each sub-goal independently

This would discover "fracture fire first, then essence cold" vs "buy magic fire, essence cold" etc. — the ordering decision that matters most for cost.

### Path E: Adaptive Trial Count

Start with low trials (200) for initial generations to quickly prune obviously bad strategies. Then increase trials (2000-5000) for the top 10% to get stable fitness estimates. Saves compute while giving accurate signal where it matters.

---

## Recommendation

**Short-term (next session)**: Implement Path A (sub-goal decomposition). It's the highest-impact change:
- Each sub-goal is a proven 1-target optimization
- The total cost is a simple sum
- The GP can discover optimal strategies for each step independently
- Results in seconds, not minutes

**Medium-term**: Implement Path E (adaptive trials) to improve GP convergence for harder crafts without 10× compute cost.

**Long-term**: Path D (hierarchical GP) for fully automated recipe discovery — the system that discovers "fracture then fill" vs "buy magic then essence" without being told.

---

## Verified Numbers (for reference)

| Target | Strategy | Amortized Cost | Success Rate | Verdict |
|--------|----------|---------------|--------------|---------|
| T1 Life (1 target, high weight) | Alchemy spam | 0.4c | 100% | CRAFT |
| T1 Life + T1 ES + T1 FireRes (3 targets) | Alchemy + Exalt | 145c | 7.4% | CRAFT |
| T2+ Fire/Cold/Phys + AtkSpd + Arcane (5 targets, low weight) | Buy magic + essence + exalt loop | ~42M c | 0.086% | BUY |

The optimizer gives correct answers for all difficulty levels. The gap is in
*discovering* the deterministic recipe for the hardest crafts — not in evaluating them.
