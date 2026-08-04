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
    """
    total = 0.0
    prior_cost = 0.0
    mod_count = 0

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

    starting_mods: list[tuple[int, str, int]] = []
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

        # Update starting state for next phase
        starting_mods.append((t.family_id, t.affix_type, t.max_tier))
        if starting_rarity == 0:
            starting_rarity = 1  # transmute/buy_magic → Magic
        if starting_rarity == 1 and phase_idx >= 1:
            starting_rarity = 2  # regal/essence → Rare

        # Track essence usage
        est = quick_estimate_phase(
            t, pool_data, prices,
            starting_mod_count=len(starting_mods) - 1,
            starting_rarity=phase.starting_rarity,
        )
        if est.method == "essence":
            starting_flags |= 0x04  # has_essence_mod

    return phases


# ── Setup Rules ──────────────────────────────────────────────────────────────

def build_setup_rules(phase: PhaseTarget) -> list[Rule]:
    """Build setup rules that recreate prior-phase item state.

    This is the Phase 1 shortcut: instead of modifying Rust to accept
    initial_state, we prepend rules that bring the item to the right
    starting state. The GP evolves the remaining rules.

    Strategy:
    - Phase 0 (blank start): no setup rules.
    - Phase 1+ with 1 prior mod: BUY_MAGIC → REGAL if needed.
    - Phase 1+ with essence needed: BUY_MAGIC → REGAL → ESSENCE.
    - Later phases: BUY_MAGIC → REGAL → ESSENCE → EXALT... for each prior mod.
    """
    if not phase.starting_mods:
        return []

    rules: list[Rule] = []
    has_essence = phase.starting_flags & 0x04 != 0
    n_prior = len(phase.starting_mods)

    # Step 1: Get to Magic with first target mod
    rules.append(Rule(
        Condition.rarity_is(Rarity.NORMAL),
        Action(Currency.BUY_MAGIC),
        label="setup: buy magic with first target",
    ))

    if n_prior == 1 and not has_essence:
        # Just need a Rare item with one mod — regal it
        rules.append(Rule(
            Condition.rarity_is(Rarity.MAGIC),
            Action(Currency.REGAL),
            label="setup: regal to rare",
        ))
    elif n_prior >= 2 and has_essence:
        # Essence: Magic → Rare + guaranteed mod
        rules.append(Rule(
            Condition.no_essence_mod(),
            Action(Currency.ESSENCE_GREATER),
            label="setup: essence for second target",
        ))

        # If we need more mods beyond essence, exalt them
        for i in range(2, n_prior):
            mod = phase.starting_mods[i]
            affix = mod[1]
            if affix == "prefix":
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
    else:
        # Simple case: just regal
        rules.append(Rule(
            Condition.rarity_is(Rarity.MAGIC),
            Action(Currency.REGAL),
            label="setup: regal to rare",
        ))

        # Exalt for additional prior mods
        for i in range(1, n_prior):
            mod = phase.starting_mods[i]
            affix = mod[1]
            if affix == "prefix":
                rules.append(Rule(
                    Condition.open_prefix_gte(1),
                    Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
                    label=f"setup: exalt prefix #{i}",
                ))
            else:
                rules.append(Rule(
                    Condition.open_suffix_gte(1),
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
