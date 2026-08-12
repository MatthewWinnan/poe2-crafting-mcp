"""Sub-goal decomposition for multi-target crafting optimization.

Breaks an N-target craft into sequential single-target phases, determines
optimal ordering via WSJF heuristic, and provides the orchestration logic
for running the GP on each phase independently.

References:
- Layered Learning (Stone & Veloso, 2000)
- Options / SMDP (Sutton, Precup & Singh, 1999)
- WSJF ordering from scheduling theory
"""

from __future__ import annotations

import itertools
import logging
import math
from dataclasses import dataclass

import numpy as np

from .gene import (
    Action,
    Condition,
    CraftTarget,
    Currency,
    Grouping,
    ModTarget,
    Omen,
    PhaseTarget,
    Rarity,
    Rule,
    RuleList,
)

log = logging.getLogger(__name__)


# ── Phase Classification ────────────────────────────────────────────────────

def classify_phase_risk(
    target: ModTarget,
    starting_mod_count: int,
    starting_rarity: int,
) -> str:
    """Classify whether a phase can destroy prior-phase mods.

    Returns:
        "safe"         — only adds mods (exalt, essence, desecrate+reveal).
        "destructive"  — uses annul/chaos, can remove prior mods.
        "full_restart" — scour/alchemy, definitely destroys prior work.
    """
    # Phase 1 starting from blank is always safe (nothing to destroy)
    if starting_mod_count == 0:
        return "safe"

    # If item is already Rare with open slots, exalt/essence/reveal are safe
    if starting_rarity == 2 and starting_mod_count < 6:
        return "safe"

    # If item is Magic and needs regal, that's safe (regal only adds)
    if starting_rarity == 1:
        return "safe"

    # If all slots are full, annulling is required → destructive
    return "destructive"


# ── Quick Cost Estimation ────────────────────────────────────────────────────

@dataclass
class QuickEstimate:
    """Quick analytical cost estimate for one target."""
    target: ModTarget
    method: str           # "buy_magic", "essence", "exalt", "sinistral_exalt", etc.
    expected_cost: float
    success_rate: float
    is_deterministic: bool
    risk: str


def quick_estimate_phase(
    target: ModTarget,
    pool_data: dict,
    prices: dict[str, float],
    starting_mod_count: int = 0,
    starting_rarity: int = 0,
    open_prefix: int = 3,
    open_suffix: int = 3,
) -> QuickEstimate:
    """Quick analytical cost estimate for achieving one target.

    Uses pool weight ratios for probability, no GP or MC needed.
    Used for ordering heuristics only — the real optimization uses the GP.
    """
    family_id = target.family_id
    affix = target.affix_type
    max_tier = target.max_tier

    # Desecrated (abyss) mods use desecrate+reveal, not exalt/essence
    if target.pool_source == "desecrated":
        return _estimate_desecrated_phase(target, prices, starting_mod_count, starting_rarity)

    # Get pool arrays
    if affix == "prefix":
        families = pool_data["prefix_families"]
        tiers = pool_data["prefix_tiers"]
        weights = pool_data["prefix_weights"]
        total_weight = int(np.sum(weights))
    else:
        families = pool_data["suffix_families"]
        tiers = pool_data["suffix_tiers"]
        weights = pool_data["suffix_weights"]
        total_weight = int(np.sum(weights))

    # Target weight: sum of weights for matching family + tier <= max_tier
    target_weight = 0
    for i in range(len(families)):
        if families[i] == family_id and tiers[i] <= max_tier:
            target_weight += int(weights[i])

    # Probability of hitting target in one exalt
    prob = target_weight / total_weight if total_weight > 0 else 0.0

    # Adjust for omen targeting (sinistral/dextral forces prefix/suffix)
    # When using an omen, only the matching pool is considered
    prefix_total = int(np.sum(pool_data["prefix_weights"]))
    suffix_total = int(np.sum(pool_data["suffix_weights"]))
    combined_total = prefix_total + suffix_total

    if affix == "prefix" and combined_total > 0:
        # Without omen: prob = target_weight / combined_total
        # With sinistral: prob = target_weight / prefix_total
        prob_natural = target_weight / combined_total if combined_total > 0 else 0.0
        prob_omen = target_weight / prefix_total if prefix_total > 0 else 0.0
    elif affix == "suffix" and combined_total > 0:
        prob_natural = target_weight / combined_total if combined_total > 0 else 0.0
        prob_omen = target_weight / suffix_total if suffix_total > 0 else 0.0
    else:
        prob_natural = prob
        prob_omen = prob

    risk = classify_phase_risk(target, starting_mod_count, starting_rarity)

    # Determine best method and cost
    exalt_price = prices.get("exalted", 3.0)
    sinistral_price = prices.get("sinistral_exaltation", 15.0)
    dextral_price = prices.get("dextral_exaltation", 15.0)
    essence_price = prices.get("greater_essence", 1.0)
    buy_magic_price = prices.get("buy_magic", 35.0)

    # Phase 1 from blank: buy magic is deterministic
    if starting_mod_count == 0 and starting_rarity == 0:
        return QuickEstimate(
            target=target,
            method="buy_magic",
            expected_cost=buy_magic_price,
            success_rate=1.0,
            is_deterministic=True,
            risk="safe",
        )

    # Essence: deterministic if Magic item has no essence mod yet
    if starting_rarity == 1 or (starting_rarity == 0 and starting_mod_count == 0):
        return QuickEstimate(
            target=target,
            method="essence",
            expected_cost=essence_price + 0.02,  # + regal cost if needed
            success_rate=1.0,
            is_deterministic=True,
            risk="safe",
        )

    # Exalt with omen targeting
    omen_key = "sinistral_exaltation" if affix == "prefix" else "dextral_exaltation"
    omen_price = sinistral_price if affix == "prefix" else dextral_price
    cost_with_omen = (exalt_price + omen_price) / prob_omen if prob_omen > 0 else float("inf")
    cost_natural = exalt_price / prob_natural if prob_natural > 0 else float("inf")

    if cost_with_omen < cost_natural:
        method = f"{'sinistral' if affix == 'prefix' else 'dextral'}_exalt"
        cost = cost_with_omen
        p = prob_omen
    else:
        method = "exalt"
        cost = cost_natural
        p = prob_natural

    return QuickEstimate(
        target=target,
        method=method,
        expected_cost=cost,
        success_rate=min(p, 1.0),
        is_deterministic=False,
        risk=risk,
    )


def _estimate_desecrated_phase(
    target: ModTarget,
    prices: dict[str, float],
    starting_mod_count: int,
    starting_rarity: int,
) -> QuickEstimate:
    """Cost estimate for a desecrated (abyss) mod via desecrate+reveal.

    Desecrated mods come from a small pool (~14 families per slot).
    Reveal shows 3 options, player picks best: P(hit) ≈ 1-(1-1/N)^3.
    If missed, need Omen of Light (annul abyss only) or annul+retry.
    """
    # Desecrate cost is negligible (bone fragment ~0.1c)
    desecrate_cost = prices.get("desecrate", 0.1)
    # Omen of Light: targeted annul of abyss mod for clean retry
    light_price = prices.get("light", 5.0)
    annul_price = prices.get("annulment", 2.0)

    # ~20% chance per reveal attempt (14 families, pick 3)
    prob_per_reveal = 0.20
    # With Omen of Light retry: cost per attempt = desecrate + light_if_miss
    # E[cost] = desecrate / prob + (1-prob) * (light + annul) / prob
    cost_per_attempt = desecrate_cost + (1.0 - prob_per_reveal) * (light_price + annul_price)
    expected_cost = cost_per_attempt / prob_per_reveal

    risk = classify_phase_risk(target, starting_mod_count, starting_rarity)

    return QuickEstimate(
        target=target,
        method="desecrate_reveal",
        expected_cost=expected_cost,
        success_rate=prob_per_reveal,
        is_deterministic=False,
        risk=risk,
    )


# ── Ordering ─────────────────────────────────────────────────────────────────

def wsjf_score(estimate: QuickEstimate) -> float:
    """WSJF ordering score: c / (1 - p). Lower = should go first.

    Deterministic phases get score -1 to always go first.
    """
    if estimate.is_deterministic:
        return -1.0
    if estimate.success_rate >= 1.0:
        return -1.0
    return estimate.expected_cost / (1.0 - estimate.success_rate)


def optimal_ordering(
    target: CraftTarget,
    pool_data: dict,
    prices: dict[str, float],
    max_orderings: int = 120,
) -> tuple[list[int], str, list[tuple[list[int], float]]]:
    """Find the optimal phase ordering.

    Returns:
        ordering: list of indices into target.targets
        rationale: human-readable explanation
        candidates: top orderings evaluated with (ordering, est_cost)
    """
    n = len(target.targets)

    if n <= 1:
        return [0], "single target", []

    # Get quick estimates for each target (as if it were the only target)
    estimates = []
    for i, t in enumerate(target.targets):
        est = quick_estimate_phase(t, pool_data, prices)
        estimates.append(est)

    # WSJF heuristic ordering
    scored = [(wsjf_score(estimates[i]), i) for i in range(n)]
    scored.sort(key=lambda x: x[0])
    wsjf_order = [idx for _, idx in scored]

    if n <= 7 and math.factorial(n) <= max_orderings:
        # Enumerate all permutations and score each
        candidates = []
        for perm in itertools.permutations(range(n)):
            cost = _estimate_ordering_cost(list(perm), estimates, target, pool_data, prices)
            candidates.append((list(perm), cost))
        candidates.sort(key=lambda x: x[1])

        best_order = candidates[0][0]
        best_cost = candidates[0][1]
        wsjf_cost = _estimate_ordering_cost(wsjf_order, estimates, target, pool_data, prices)

        rationale = (
            f"Enumerated {len(candidates)} orderings. "
            f"Best: {best_cost:.0f}c. WSJF: {wsjf_cost:.0f}c."
        )
        return best_order, rationale, candidates[:10]
    else:
        # Too many permutations — use WSJF heuristic
        wsjf_cost = _estimate_ordering_cost(wsjf_order, estimates, target, pool_data, prices)
        rationale = f"WSJF heuristic (N={n}, {math.factorial(n)} permutations too many). Est: {wsjf_cost:.0f}c."
        return wsjf_order, rationale, [(wsjf_order, wsjf_cost)]


def _estimate_ordering_cost(
    ordering: list[int],
    estimates: list[QuickEstimate],
    target: CraftTarget,
    pool_data: dict,
    prices: dict[str, float],
) -> float:
    """Estimate total cost of a specific ordering (quick, no GP).

    Models restart cascades: if a destructive phase fails and destroys
    prior mods, we pay the cost of all prior phases again.

    Penalizes desecrated targets in non-final positions because later
    phases would need to recreate them probabilistically on restart.
    """
    total = 0.0
    prior_cost = 0.0
    mod_count = 0
    n_phases = len(ordering)

    for phase_idx, target_idx in enumerate(ordering):
        est = estimates[target_idx]

        # Re-estimate with correct starting state
        t = target.targets[target_idx]
        re_est = quick_estimate_phase(
            t, pool_data, prices,
            starting_mod_count=mod_count,
            starting_rarity=2 if mod_count > 0 else 0,
            open_prefix=3 - sum(1 for j in ordering[:phase_idx]
                                if target.targets[j].affix_type == "prefix"),
            open_suffix=3 - sum(1 for j in ordering[:phase_idx]
                                if target.targets[j].affix_type == "suffix"),
        )

        phase_cost = re_est.expected_cost

        # Add restart cascade cost for destructive phases
        if re_est.risk == "destructive" and re_est.success_rate < 1.0:
            # Probability of destroying prior work per attempt
            # Simplified: assume ~30% chance annul hits a prior mod
            destroy_prob = 0.3 * (1.0 - re_est.success_rate)
            phase_cost += destroy_prob * prior_cost

        # Penalize desecrated targets NOT in the final position.
        # Desecrate+reveal is probabilistic (~20% hit rate), so later phases
        # would pay ~5x the desecrate cost per restart cycle to recreate it.
        # In practice, players always do abyss last to avoid this penalty.
        if t.pool_source == "desecrated" and phase_idx < n_phases - 1:
            remaining_phases = n_phases - phase_idx - 1
            # Each later phase restart needs ~5 reveals (1/0.20) to recreate
            recreation_penalty = re_est.expected_cost * 4.0 * remaining_phases
            phase_cost += recreation_penalty

        total += phase_cost
        prior_cost += phase_cost
        mod_count += len([t])

    return total


# ── Phase Building ───────────────────────────────────────────────────────────

def build_phases(
    target: CraftTarget,
    ordering: list[int],
    pool_data: dict,
    prices: dict[str, float],
) -> list[PhaseTarget]:
    """Build PhaseTarget list from an ordering.

    Each phase knows its starting state (mods from prior phases),
    its targets, and the full set of protected families.
    """
    all_family_ids = [t.family_id for t in target.targets]
    phases: list[PhaseTarget] = []

    starting_mods: list[tuple[int, str, int, str]] = []
    starting_rarity = 0
    starting_flags = 0

    for phase_idx, target_idx in enumerate(ordering):
        t = target.targets[target_idx]

        phase = PhaseTarget(
            targets=[t],
            starting_mods=list(starting_mods),
            starting_rarity=starting_rarity,
            starting_flags=starting_flags,
            phase_index=phase_idx,
            protected_families=all_family_ids,
        )
        phases.append(phase)

        # Update starting state for next phase.
        # Phase 0 produces a Magic item (transmute/buy_magic → 1 mod, minimal slots used).
        # Phase 1+ should regal to Rare internally, keeping prior mods lean.
        starting_mods.append((t.family_id, t.affix_type, t.max_tier, t.pool_source))
        if starting_rarity == 0:
            starting_rarity = 1  # transmute/buy_magic → Magic
        elif starting_rarity == 1:
            starting_rarity = 2  # regal/essence in Phase 1 → Rare

        # Track essence/desecration usage
        est = quick_estimate_phase(
            t, pool_data, prices,
            starting_mod_count=len(starting_mods) - 1,
            starting_rarity=phase.starting_rarity,
        )
        if est.method == "essence":
            starting_flags |= 0x04  # has_essence_mod
        if est.method == "desecrate_reveal":
            starting_flags |= 0x08  # has_been_desecrated_ever

    return phases


# ── Setup Rules ──────────────────────────────────────────────────────────────

def build_setup_rules(phase: PhaseTarget) -> list[Rule]:
    """Build setup rules that recreate prior-phase item state.

    Prepends rules that bring a blank item to the state expected by this
    phase (all prior-phase mods present). The GP evolves the remaining rules.

    Strategy depends on how prior mods were obtained:
    - Normal pool mods: BUY_MAGIC (trade) or EXALT
    - Desecrated mods: must craft to Rare then DESECRATE + REVEAL
    - Essence mods: ESSENCE_GREATER (Magic → Rare + guaranteed)
    """
    if not phase.starting_mods:
        return []

    rules: list[Rule] = []
    has_essence = phase.starting_flags & 0x04 != 0
    has_desecrated = phase.starting_flags & 0x08 != 0
    n_prior = len(phase.starting_mods)

    # Check if first prior mod is desecrated (can't buy from trade)
    first_pool = phase.starting_mods[0][3] if len(phase.starting_mods[0]) > 3 else "normal"
    first_is_desecrated = first_pool == "desecrated"

    if first_is_desecrated:
        # Can't buy a desecrated mod from trade. Must craft to Rare, then desecrate+reveal.
        rules.append(Rule(
            Condition.rarity_is(Rarity.NORMAL),
            Action(Currency.TRANSMUTE),
            label="setup: transmute",
        ))
        rules.append(Rule(
            Condition.rarity_is(Rarity.MAGIC),
            Action(Currency.REGAL),
            label="setup: regal to rare",
        ))
        rules.append(Rule(
            Condition.not_desecrated(),
            Action(Currency.DESECRATE),
            label="setup: desecrate for abyss mod",
        ))
        rules.append(Rule(
            Condition.is_desecrated(),
            Action(Currency.REVEAL),
            label="setup: reveal abyss mod",
        ))
    else:
        # Normal mod: buy from trade
        rules.append(Rule(
            Condition.rarity_is(Rarity.NORMAL),
            Action(Currency.BUY_MAGIC),
            label="setup: buy magic with first target",
        ))

    # Get to Rare if not already
    if not first_is_desecrated:
        if n_prior == 1 and not has_essence:
            rules.append(Rule(
                Condition.rarity_is(Rarity.MAGIC),
                Action(Currency.REGAL),
                label="setup: regal to rare",
            ))
        elif n_prior >= 2 and has_essence:
            rules.append(Rule(
                Condition.no_essence_mod(),
                Action(Currency.ESSENCE_GREATER),
                label="setup: essence for guaranteed mod",
            ))
        else:
            rules.append(Rule(
                Condition.rarity_is(Rarity.MAGIC),
                Action(Currency.REGAL),
                label="setup: regal to rare",
            ))

    # Add remaining prior mods via exalt or desecrate
    start_idx = 1
    for i in range(start_idx, n_prior):
        mod = phase.starting_mods[i]
        affix = mod[1]
        mod_pool = mod[3] if len(mod) > 3 else "normal"

        if mod_pool == "desecrated":
            # Prior desecrated mod: desecrate + reveal
            rules.append(Rule(
                Condition.not_desecrated(),
                Action(Currency.DESECRATE),
                label=f"setup: desecrate #{i}",
            ))
            rules.append(Rule(
                Condition.is_desecrated(),
                Action(Currency.REVEAL),
                label=f"setup: reveal #{i}",
            ))
        elif affix == "prefix":
            rules.append(Rule(
                Condition.missing_target_prefix(),
                Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
                label=f"setup: exalt prefix #{i}",
            ))
        else:
            rules.append(Rule(
                Condition.missing_target_suffix(),
                Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
                label=f"setup: exalt suffix #{i}",
            ))

    return rules


# ── Free-Hit Detection ───────────────────────────────────────────────────────

def detect_free_hits(
    phase: PhaseTarget,
    remaining_targets: list[ModTarget],
    pool_data: dict,
    expected_random_mods: int = 2,
    threshold: float = 0.30,
) -> list[int]:
    """Identify which remaining targets might be hit for free during this phase.

    When a phase uses multi-mod currencies (alchemy, chaos, essence+regal),
    random mods are added alongside the target. If a later-phase target has
    high enough weight in the pool, it may appear naturally.

    Uses an analytical estimate: for each remaining target, compute
    P(hit in N random rolls) = 1 - (1 - p)^N where p = target_weight / total_weight
    and N = expected_random_mods (how many random mods this phase typically adds).

    Args:
        phase: current phase being optimized
        remaining_targets: targets from later phases
        pool_data: encoded mod pool
        expected_random_mods: how many random mods the phase typically adds
            (e.g., alchemy adds ~4 random mods, regal adds 1-2)
        threshold: probability threshold to flag a free hit (default 30%)

    Returns:
        Indices into remaining_targets that are likely free hits.
    """
    if not remaining_targets or expected_random_mods == 0:
        return []

    free_hit_indices: list[int] = []

    prefix_weights = pool_data.get("prefix_weights", np.array([], dtype=np.uint32))
    suffix_weights = pool_data.get("suffix_weights", np.array([], dtype=np.uint32))
    prefix_families = pool_data.get("prefix_families", np.array([], dtype=np.uint16))
    suffix_families = pool_data.get("suffix_families", np.array([], dtype=np.uint16))
    prefix_tiers = pool_data.get("prefix_tiers", np.array([], dtype=np.uint8))
    suffix_tiers = pool_data.get("suffix_tiers", np.array([], dtype=np.uint8))

    prefix_total = int(np.sum(prefix_weights)) if len(prefix_weights) > 0 else 0
    suffix_total = int(np.sum(suffix_weights)) if len(suffix_weights) > 0 else 0

    for idx, target in enumerate(remaining_targets):
        if target.affix_type == "prefix":
            families = prefix_families
            tiers = prefix_tiers
            weights = prefix_weights
            total_weight = prefix_total
        else:
            families = suffix_families
            tiers = suffix_tiers
            weights = suffix_weights
            total_weight = suffix_total

        if total_weight == 0:
            continue

        # Sum weights for this target family at acceptable tiers
        target_weight = 0
        for i in range(len(families)):
            if families[i] == target.family_id and tiers[i] <= target.max_tier:
                target_weight += int(weights[i])

        p_single = target_weight / total_weight
        p_hit = 1.0 - (1.0 - p_single) ** expected_random_mods

        if p_hit >= threshold:
            log.debug(
                f"Free hit detected: {target.family} ({target.affix_type}) "
                f"p={p_hit:.1%} >= {threshold:.0%}"
            )
            free_hit_indices.append(idx)

    return free_hit_indices


def build_phase_craft_target(
    phase: PhaseTarget,
    all_target: CraftTarget,
) -> CraftTarget:
    """Build a CraftTarget for a single phase.

    The phase target includes ONLY this phase's mods for success checking,
    but ALL target family IDs are present in the pool data for annul
    protection (handled via pool_data targets).
    """
    return CraftTarget(
        targets=phase.targets,
        item_class=all_target.item_class,
        ilvl=all_target.ilvl,
    )


# ── Grouping Operators (Tier 3 Hierarchical GP) ─────────────────────────────

import random as _random


def build_phases_from_grouping(
    target: CraftTarget,
    grouping: Grouping,
    pool_data: dict,
    prices: dict[str, float],
) -> list[PhaseTarget]:
    """Convert a Grouping genome into PhaseTarget list.

    Like build_phases() but supports multi-target groups.
    Each group in execution order becomes one PhaseTarget with potentially
    multiple targets.
    """
    all_family_ids = [t.family_id for t in target.targets]
    phases: list[PhaseTarget] = []

    starting_mods: list[tuple[int, str, int, str]] = []
    starting_rarity = 0
    starting_flags = 0

    for phase_idx, group in enumerate(grouping.ordered_groups()):
        group_targets = [target.targets[i] for i in group]

        phase = PhaseTarget(
            targets=group_targets,
            starting_mods=list(starting_mods),
            starting_rarity=starting_rarity,
            starting_flags=starting_flags,
            phase_index=phase_idx,
            protected_families=all_family_ids,
        )
        phases.append(phase)

        # Update starting state for next phase
        for t in group_targets:
            starting_mods.append((t.family_id, t.affix_type, t.max_tier, t.pool_source))
            if starting_rarity == 0:
                starting_rarity = 1
            elif starting_rarity == 1:
                starting_rarity = 2

            est = quick_estimate_phase(
                t, pool_data, prices,
                starting_mod_count=len(starting_mods) - 1,
                starting_rarity=phase.starting_rarity,
            )
            if est.method == "essence":
                starting_flags |= 0x04
            if est.method == "desecrate_reveal":
                starting_flags |= 0x08

    return phases


def grouping_crossover(a: Grouping, b: Grouping) -> Grouping:
    """Crossover two Grouping genomes.

    Pick a random target and swap its group membership from parent B into
    a copy of parent A.
    """
    child = a.copy()
    n_targets = a.n_targets

    # Pick a random target
    target_idx = _random.randrange(n_targets)

    # Find which group it's in for parent B
    b_group_idx = None
    for gi, group in enumerate(b.groups):
        if target_idx in group:
            b_group_idx = gi
            break
    if b_group_idx is None:
        return child

    # Find other targets in the same group in B
    b_group_members = set(b.groups[b_group_idx])

    # In child, merge all groups that contain any of these members
    merged = set()
    remaining_groups = []
    for group in child.groups:
        if b_group_members & set(group):
            merged.update(group)
        else:
            remaining_groups.append(group)

    remaining_groups.append(sorted(merged))
    child.groups = remaining_groups
    child.ordering = list(range(len(child.groups)))
    child.fitness = float("inf")
    return child


def grouping_mutation(g: Grouping) -> Grouping:
    """Mutate a Grouping genome. Picks one of 4 operators uniformly."""
    child = g.copy()
    op = _random.randrange(4)

    if op == 0:
        _mutation_split(child)
    elif op == 1:
        _mutation_merge(child)
    elif op == 2:
        _mutation_move(child)
    else:
        _mutation_reorder(child)

    # Remove empty groups
    child.groups = [g for g in child.groups if g]
    child.ordering = list(range(len(child.groups)))
    child.fitness = float("inf")
    return child


def _mutation_split(g: Grouping) -> None:
    """Split a group with 2+ targets into two groups."""
    multi = [i for i, group in enumerate(g.groups) if len(group) >= 2]
    if not multi:
        return
    gi = _random.choice(multi)
    group = g.groups[gi]
    split_point = _random.randint(1, len(group) - 1)
    _random.shuffle(group)
    g.groups[gi] = group[:split_point]
    g.groups.append(group[split_point:])


def _mutation_merge(g: Grouping) -> None:
    """Merge two groups into one."""
    if len(g.groups) < 2:
        return
    i = _random.randrange(len(g.groups))
    j = _random.randrange(len(g.groups))
    while j == i:
        j = _random.randrange(len(g.groups))
    g.groups[i] = sorted(g.groups[i] + g.groups[j])
    g.groups[j] = []


def _mutation_move(g: Grouping) -> None:
    """Move a random target to a different group."""
    if len(g.groups) < 2:
        return
    src = _random.randrange(len(g.groups))
    while not g.groups[src]:
        src = _random.randrange(len(g.groups))
    dst = _random.randrange(len(g.groups))
    while dst == src:
        dst = _random.randrange(len(g.groups))
    target_idx = _random.choice(g.groups[src])
    g.groups[src].remove(target_idx)
    g.groups[dst].append(target_idx)
    g.groups[dst].sort()


def _mutation_reorder(g: Grouping) -> None:
    """Swap two groups in the execution order."""
    if len(g.ordering) < 2:
        return
    i = _random.randrange(len(g.ordering))
    j = _random.randrange(len(g.ordering))
    while j == i:
        j = _random.randrange(len(g.ordering))
    g.ordering[i], g.ordering[j] = g.ordering[j], g.ordering[i]


def generate_seed_groupings(
    n_targets: int,
    affix_types: list[str],
    pool_sources: list[str] | None = None,
) -> list[Grouping]:
    """Generate diverse seed groupings for the outer GP.

    Args:
        n_targets: number of targets
        affix_types: list of "prefix"/"suffix" per target index
        pool_sources: list of "normal"/"desecrated" per target index
    """
    if pool_sources is None:
        pool_sources = ["normal"] * n_targets

    seeds: list[Grouping] = []

    # 1. All-singles (Tier 1 baseline): each target in its own phase
    singles = Grouping(
        groups=[[i] for i in range(n_targets)],
        ordering=list(range(n_targets)),
    )
    seeds.append(singles)

    # 2. All-monolithic: all targets in one phase
    mono = Grouping(
        groups=[list(range(n_targets))],
        ordering=[0],
    )
    seeds.append(mono)

    # 3. By affix type: prefixes together, suffixes together
    prefixes = [i for i in range(n_targets) if affix_types[i] == "prefix"]
    suffixes = [i for i in range(n_targets) if affix_types[i] == "suffix"]
    if prefixes and suffixes:
        by_affix = Grouping(
            groups=[prefixes, suffixes],
            ordering=[0, 1],
        )
        seeds.append(by_affix)
        # Also reversed order
        seeds.append(Grouping(
            groups=[prefixes, suffixes],
            ordering=[1, 0],
        ))

    # 4. Desecrated-last: normal targets grouped, desecrated targets last
    normal_targets = [i for i in range(n_targets) if pool_sources[i] == "normal"]
    desecrated_targets = [i for i in range(n_targets) if pool_sources[i] == "desecrated"]
    if normal_targets and desecrated_targets:
        desc_last = Grouping(
            groups=[normal_targets, desecrated_targets],
            ordering=[0, 1],
        )
        seeds.append(desc_last)

    # 5. Pairs: group targets in pairs
    if n_targets >= 4:
        pairs: list[list[int]] = []
        remaining = list(range(n_targets))
        _random.shuffle(remaining)
        while len(remaining) >= 2:
            pairs.append([remaining.pop(), remaining.pop()])
        if remaining:
            pairs.append(remaining)
        seeds.append(Grouping(
            groups=pairs,
            ordering=list(range(len(pairs))),
        ))

    # 6. Random partitions (2-3 extras)
    for _ in range(min(3, max(1, 10 - len(seeds)))):
        groups: list[list[int]] = [[] for _ in range(_random.randint(2, max(2, n_targets - 1)))]
        for i in range(n_targets):
            groups[_random.randrange(len(groups))].append(i)
        groups = [g for g in groups if g]  # remove empties
        seeds.append(Grouping(
            groups=groups,
            ordering=list(range(len(groups))),
        ))

    return seeds
