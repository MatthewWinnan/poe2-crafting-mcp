"""Genetic operators for the crafting optimizer.

Implements crossover (one-point splice) and 6 mutation types with credit-guided
targeting from PPL-ST. Simplified design informed by BASIL (2025): fewer operator
types, relying on QD archive for exploration diversity.

Operator weights:
  - mutate_action:    30%  (change currency/omen on a rule)
  - swap_priority:    20%  (swap two rules' positions)
  - mutate_condition: 15%  (change predicate or nudge argument)
  - replace_rule:     15%  (remove harmful rule, insert new random one)
  - insert_rule:      10%  (add a random rule)
  - delete_rule:      10%  (remove a dead/harmful rule)
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .gene import (
    MAX_RULES,
    Action,
    Condition,
    Currency,
    Fitness,
    Omen,
    Predicate,
    Rarity,
    Rule,
    RuleList,
)

if TYPE_CHECKING:
    from .gene import Individual


# ── Operator Configuration ────────────────────────────────────────────────────

CROSSOVER_RATE = 0.7
MUTATION_RATE = 0.3

# Mutation type weights (must sum to 1.0)
MUTATION_WEIGHTS = {
    "mutate_action": 0.30,
    "swap_priority": 0.20,
    "mutate_condition": 0.15,
    "replace_rule": 0.15,
    "insert_rule": 0.10,
    "delete_rule": 0.10,
}

# Currencies that can appear in random rules (exclude terminal/meta actions)
_CRAFTABLE_CURRENCIES = [
    c for c in Currency
    if c not in (Currency.DONE, Currency.FAIL)
]

# Currencies that can benefit from omens (based on OMENS applies_to in simulator.py).
# Only these should be paired with omens during random action generation.
_OMEN_COMPATIBLE_CURRENCIES = {
    Currency.EXALTED, Currency.GREATER_EXALTED, Currency.PERFECT_EXALTED,
    Currency.ANNULMENT,
    Currency.CHAOS, Currency.GREATER_CHAOS, Currency.PERFECT_CHAOS,
    Currency.REGAL, Currency.GREATER_REGAL, Currency.PERFECT_REGAL,
    Currency.ALCHEMY,
    Currency.ESSENCE_PERFECT,
    Currency.DIVINE,
    Currency.VAAL,
    Currency.DESECRATE,
    Currency.REVEAL,
}

# Predicates that can appear in random rules
_ALL_PREDICATES = list(Predicate)

# Omens that can be paired with currencies
_ALL_OMENS = list(Omen)

# Omens specific to REVEAL (desecration) — other omens are wasted on reveal
_REVEAL_OMENS = [
    Omen.ABYSSAL_ECHOES,
    Omen.SINISTRAL_NECROMANCY,
    Omen.DEXTRAL_NECROMANCY,
]

# Cost threshold range for cost_spent_gte conditions
_COST_THRESHOLDS = [50, 100, 150, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000]

# Slot counts for open_prefix/suffix_gte conditions
_SLOT_COUNTS = [1, 2, 3]

# Target counts for targets_on_item_gte
_TARGET_COUNTS = [1, 2, 3]


# ── Credit-Guided Targeting ───────────────────────────────────────────────────

def _select_mutation_target(rulelist: RuleList, fitness: Fitness | None) -> int:
    """Pick a rule index to mutate, weighted by harmfulness.

    Credit-guided: harmful rules get mutated first, key rules are protected.
    Falls back to uniform random if no fitness data available.
    """
    n = rulelist.size
    if n == 0:
        return 0

    if fitness is None or not fitness.fire_on_success:
        return random.randint(0, n - 1)

    weights: list[float] = []
    for i in range(n):
        if fitness.rule_is_dead(i):
            weights.append(3.0)
        elif fitness.rule_is_harmful(i):
            weights.append(5.0)
        elif fitness.rule_is_key(i):
            weights.append(0.1)
        else:
            weights.append(1.0)

    return random.choices(range(n), weights=weights, k=1)[0]


# ── Random Rule Generation ────────────────────────────────────────────────────

def random_condition() -> Condition:
    """Generate a random condition from the predicate vocabulary."""
    # Weight toward common useful predicates
    common_predicates = [
        Predicate.RARITY_IS,
        Predicate.ALL_TARGETS_HIT,
        Predicate.HAS_ANY_TARGET,
        Predicate.MISSING_TARGET_PREFIX,
        Predicate.MISSING_TARGET_SUFFIX,
        Predicate.OPEN_PREFIX_GTE,
        Predicate.OPEN_SUFFIX_GTE,
        Predicate.COST_SPENT_GTE,
        Predicate.HAS_NON_TARGET_REMOVABLE,
        Predicate.REMOVABLE_GT_TARGETS,
        Predicate.ALWAYS_TRUE,
    ]

    pred = random.choice(common_predicates)

    if pred == Predicate.RARITY_IS:
        return Condition.rarity_is(random.choice(list(Rarity)))
    elif pred == Predicate.OPEN_PREFIX_GTE:
        return Condition.open_prefix_gte(random.choice(_SLOT_COUNTS))
    elif pred == Predicate.OPEN_SUFFIX_GTE:
        return Condition.open_suffix_gte(random.choice(_SLOT_COUNTS))
    elif pred == Predicate.COST_SPENT_GTE:
        return Condition.cost_spent_gte(float(random.choice(_COST_THRESHOLDS)))
    elif pred == Predicate.TARGETS_ON_ITEM_GTE:
        return Condition.targets_on_item_gte(random.choice(_TARGET_COUNTS))
    elif pred == Predicate.MOD_COUNT_GTE:
        return Condition.mod_count_gte(random.randint(2, 5))
    elif pred == Predicate.MOD_COUNT_LTE:
        return Condition.mod_count_lte(random.randint(2, 5))
    elif pred == Predicate.STEP_COUNT_GTE:
        return Condition.step_count_gte(random.choice([50, 100, 200, 300]))
    else:
        # No-arg predicates
        factory = {
            Predicate.ALL_TARGETS_HIT: Condition.all_targets_hit,
            Predicate.HAS_ANY_TARGET: Condition.has_any_target,
            Predicate.MISSING_TARGET_PREFIX: Condition.missing_target_prefix,
            Predicate.MISSING_TARGET_SUFFIX: Condition.missing_target_suffix,
            Predicate.HAS_NON_TARGET_REMOVABLE: Condition.has_non_target_removable,
            Predicate.REMOVABLE_GT_TARGETS: Condition.removable_gt_targets,
            Predicate.PREFIX_FULL_NO_TARGET_PREFIX: Condition.prefix_full_no_target_prefix,
            Predicate.SUFFIX_FULL_NO_TARGET_SUFFIX: Condition.suffix_full_no_target_suffix,
            Predicate.HAS_FRACTURED_MOD: Condition.has_fractured_mod,
            Predicate.HAS_ESSENCE_MOD: Condition.has_essence_mod,
            Predicate.NO_ESSENCE_MOD: Condition.no_essence_mod,
            Predicate.IS_DESECRATED: Condition.is_desecrated,
            Predicate.NOT_DESECRATED: Condition.not_desecrated,
            Predicate.HAS_BEEN_DIVINED: Condition.has_been_divined,
            Predicate.NOT_DIVINED: Condition.not_divined,
            Predicate.ALWAYS_TRUE: Condition.always_true,
        }
        fn = factory.get(pred, Condition.always_true)
        return fn()


def random_action() -> Action:
    """Generate a random action (currency + optional omen).

    Only pairs omens with currencies that can actually use them
    (exalted, chaos, regal, alchemy, annulment, divine, vaal, desecrate,
    perfect_essence). Currencies like reforge, transmute, essences, scour,
    fracturing etc. cannot use omens.
    """
    currency = random.choice(_CRAFTABLE_CURRENCIES)

    # 20% chance of adding an omen, but only if the currency supports it
    if random.random() < 0.2 and currency in _OMEN_COMPATIBLE_CURRENCIES:
        omen = random.choice(_REVEAL_OMENS if currency == Currency.REVEAL else _ALL_OMENS)
    else:
        omen = Omen.NONE

    return Action(currency, omen)


def random_rule() -> Rule:
    """Generate a completely random rule."""
    return Rule(random_condition(), random_action())


# ── Crossover ─────────────────────────────────────────────────────────────────

def crossover_one_point(parent_a: RuleList, parent_b: RuleList) -> RuleList:
    """One-point splice crossover.

    Takes the first portion of parent_a and the last portion of parent_b.
    Result is capped at MAX_RULES, minimum 3 rules.
    """
    if parent_a.size == 0 or parent_b.size == 0:
        return parent_a.copy() if parent_a.size > 0 else parent_b.copy()

    cut_a = random.randint(1, parent_a.size - 1)
    cut_b = random.randint(1, parent_b.size - 1)

    # Take first cut_a rules from A, remaining from B after cut_b
    child_rules = [
        Rule(r.condition, r.action, r.label)
        for r in parent_a.rules[:cut_a]
    ] + [
        Rule(r.condition, r.action, r.label)
        for r in parent_b.rules[cut_b:]
    ]

    # Enforce size constraints
    child_rules = child_rules[:MAX_RULES]
    if len(child_rules) < 3:
        # Pad with remaining rules from parent_a
        for r in parent_a.rules[cut_a:]:
            if len(child_rules) >= 3:
                break
            child_rules.append(Rule(r.condition, r.action, r.label))

    return RuleList(rules=child_rules)


# ── Mutations ─────────────────────────────────────────────────────────────────

def mutate_action(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Change the currency or omen on a random rule (credit-guided)."""
    rl = rulelist.copy()
    if rl.size == 0:
        return rl

    idx = _select_mutation_target(rl, fitness)
    old_rule = rl.rules[idx]

    # 50% chance: change currency, 50% chance: toggle/change omen
    if random.random() < 0.5:
        new_currency = random.choice(_CRAFTABLE_CURRENCIES)
        # Strip omen if new currency can't use it
        new_omen = old_rule.action.omen
        if new_currency not in _OMEN_COMPATIBLE_CURRENCIES:
            new_omen = Omen.NONE
        elif new_currency == Currency.REVEAL and new_omen not in _REVEAL_OMENS:
            new_omen = Omen.NONE
        new_action = Action(new_currency, new_omen)
    else:
        currency = old_rule.action.currency
        omen_pool = _REVEAL_OMENS if currency == Currency.REVEAL else _ALL_OMENS
        # Only toggle/add omens on compatible currencies
        if currency not in _OMEN_COMPATIBLE_CURRENCIES:
            new_action = Action(currency, Omen.NONE)
        elif old_rule.action.has_omen:
            # Remove omen or swap to different one
            if random.random() < 0.3:
                new_action = Action(currency, Omen.NONE)
            else:
                new_action = Action(currency, random.choice(omen_pool))
        else:
            new_action = Action(currency, random.choice(omen_pool))

    rl.rules[idx] = Rule(old_rule.condition, new_action, old_rule.label)
    return rl


def mutate_swap_priority(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Swap the positions of two rules."""
    rl = rulelist.copy()
    if rl.size < 2:
        return rl

    i = random.randint(0, rl.size - 1)
    j = random.randint(0, rl.size - 1)
    while j == i:
        j = random.randint(0, rl.size - 1)

    rl.swap_rules(i, j)
    return rl


def mutate_condition(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Change the predicate or nudge argument on a rule (credit-guided)."""
    rl = rulelist.copy()
    if rl.size == 0:
        return rl

    idx = _select_mutation_target(rl, fitness)
    old_rule = rl.rules[idx]

    # 60% chance: entirely new condition, 40% chance: nudge argument
    if random.random() < 0.6 or old_rule.condition.predicate == Predicate.ALWAYS_TRUE:
        new_cond = random_condition()
    else:
        # Nudge: for threshold-based predicates, adjust the value
        pred = old_rule.condition.predicate
        if pred == Predicate.COST_SPENT_GTE:
            current = old_rule.condition.cost_threshold or 500.0
            # Nudge by ±20-50%
            factor = random.uniform(0.5, 1.5)
            new_cond = Condition.cost_spent_gte(max(10.0, current * factor))
        elif pred in (Predicate.OPEN_PREFIX_GTE, Predicate.OPEN_SUFFIX_GTE):
            new_arg = random.choice(_SLOT_COUNTS)
            new_cond = Condition(pred, new_arg)
        elif pred == Predicate.TARGETS_ON_ITEM_GTE:
            new_arg = random.choice(_TARGET_COUNTS)
            new_cond = Condition(pred, new_arg)
        else:
            new_cond = random_condition()

    rl.rules[idx] = Rule(new_cond, old_rule.action, old_rule.label)
    return rl


def mutate_replace_rule(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Remove a harmful/dead rule and insert a new random one at same position."""
    rl = rulelist.copy()
    if rl.size == 0:
        return rl

    idx = _select_mutation_target(rl, fitness)
    rl.rules[idx] = random_rule()
    return rl


def mutate_insert_rule(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Add a new random rule at a random position."""
    rl = rulelist.copy()
    if rl.size >= MAX_RULES:
        return rl

    idx = random.randint(0, rl.size)
    rl.insert_rule(idx, random_rule())
    return rl


def mutate_delete_rule(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Remove a rule (credit-guided: prefer dead/harmful rules)."""
    rl = rulelist.copy()
    if rl.size <= 3:
        return rl

    idx = _select_mutation_target(rl, fitness)
    rl.remove_rule(idx)
    return rl


# ── Main Operator Interface ───────────────────────────────────────────────────

_MUTATION_FUNCTIONS = {
    "mutate_action": mutate_action,
    "swap_priority": mutate_swap_priority,
    "mutate_condition": mutate_condition,
    "replace_rule": mutate_replace_rule,
    "insert_rule": mutate_insert_rule,
    "delete_rule": mutate_delete_rule,
}


def mutate(rulelist: RuleList, fitness: Fitness | None = None) -> RuleList:
    """Apply one random mutation (weighted by type probabilities).

    Credit-guided: uses fitness.fire_on_success/fire_on_failure to target
    harmful/dead rules preferentially.
    """
    mutation_type = random.choices(
        list(MUTATION_WEIGHTS.keys()),
        weights=list(MUTATION_WEIGHTS.values()),
        k=1,
    )[0]

    fn = _MUTATION_FUNCTIONS[mutation_type]
    return fn(rulelist, fitness)


def breed(
    parent_a: RuleList,
    parent_b: RuleList,
    fitness_a: Fitness | None = None,
    fitness_b: Fitness | None = None,
) -> RuleList:
    """Produce one offspring from two parents via crossover + mutation.

    - With CROSSOVER_RATE probability: one-point splice crossover
    - With MUTATION_RATE probability: apply one mutation
    - Can do both (crossover then mutate) or neither (copy of better parent)
    """
    # Crossover
    if random.random() < CROSSOVER_RATE:
        child = crossover_one_point(parent_a, parent_b)
        child_fitness = None  # crossover creates new individual, no credit data
    else:
        # Copy better parent (or random if no fitness)
        if fitness_a and fitness_b:
            child = parent_a.copy() if fitness_a.dominates(fitness_b) else parent_b.copy()
            child_fitness = fitness_a if fitness_a.dominates(fitness_b) else fitness_b
        else:
            child = random.choice([parent_a, parent_b]).copy()
            child_fitness = None

    # Mutation
    if random.random() < MUTATION_RATE:
        child = mutate(child, child_fitness)

    return child


def prune_dead_rules(rulelist: RuleList, fitness: Fitness) -> RuleList:
    """Remove rules that never fired in any MC trial (dead code).

    Called once per generation after evaluation. Minimum 3 rules preserved.
    """
    if not fitness.fire_on_success or rulelist.size <= 3:
        return rulelist

    rl = rulelist.copy()
    # Work backwards to avoid index shifting
    for i in range(rl.size - 1, -1, -1):
        if rl.size <= 3:
            break
        if fitness.rule_is_dead(i):
            rl.rules.pop(i)

    return rl
