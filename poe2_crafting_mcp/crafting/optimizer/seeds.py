"""Hand-written seed strategies for the GP initial population.

These encode the real crafting patterns players use in the 0.5 Runes of Aldur
league. They provide the GP with a 40% head start — known-good strategies that
evolution can refine, combine, and improve upon.

Sources:
- Switchblade Gaming orb sequence guide (June 2026)
- Timesaver.gg 0.5 crafting guide
- r/PathOfExile2 crafting threads
- Community meta: essence + desecrate + exalt fill is THE standard loop
"""

from .gene import (
    Action,
    Condition,
    Currency,
    Omen,
    Rarity,
    RuleList,
)


def seed_alt_regal_exalt() -> RuleList:
    """Seed 1: Transmute-Regal-Exalt (budget, conservative).

    The classic SSF/budget approach: transmute until a target mod appears,
    regal to rare, then exalt to fill. Cheap per attempt, many restarts.
    In PoE2 there's no Alteration or Scouring — "scour" = buy a new white base.
    """
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL), "promote to rare")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "bad magic → new base")
    rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.EXALTED), "exalt prefix")
    rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.EXALTED), "exalt suffix")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_greater_alt_regal() -> RuleList:
    """Seed 2: Greater Currency Variant.

    Same structure but with Greater currencies. Narrowed mod pool
    (min_lv 35-44) means higher chance of T1-T3. Costs more per use.
    """
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.GREATER_TRANSMUTE), "start")
    rl.add_rule(Condition.has_any_target(), Action(Currency.GREATER_REGAL), "promote")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "bad magic → new base")
    rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.GREATER_EXALTED), "greater exalt")
    rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.GREATER_EXALTED), "greater exalt")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_perfect_currency() -> RuleList:
    """Seed 3: Perfect Currency Variant.

    Perfect currencies enforce min_lv 50-70 — extremely narrow pool on high-ilvl
    bases. Expensive per use but dramatically better odds for T1. Only viable
    on ilvl 82+ bases.
    """
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.PERFECT_TRANSMUTE), "start")
    rl.add_rule(Condition.has_any_target(), Action(Currency.PERFECT_REGAL), "promote")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "no target → new base")
    rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.PERFECT_EXALTED), "perfect exalt")
    rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.PERFECT_EXALTED), "perfect exalt")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_essence_exalt_fill() -> RuleList:
    """Seed 4: Essence + Exalt Fill (Greater Essence).

    Lock one guaranteed mod with Greater essence (best tier), then exalt to fill
    remaining slots. The 0.5 meta baseline — one crafted mod + random exalts.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_GREATER), "greater essence (T1)")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(400), Action(Currency.SCOUR), "restart")
    rl.add_rule(
        Condition.open_prefix_gte(1),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "exalt prefix (targeted)",
    )
    rl.add_rule(
        Condition.open_suffix_gte(1),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "exalt suffix (targeted)",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_essence_desecrate_exalt() -> RuleList:
    """Seed 5: Essence + Desecrate + Exalt (THE 0.5 meta pattern).

    Two guaranteed anchors: one crafted (essence/alloy) + one desecrated (abyss).
    Then fill the remaining 4 slots with targeted exalts. This is what experienced
    players run in Runes of Aldur for endgame gear.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_GREATER), "lock crafted mod")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(600), Action(Currency.SCOUR), "restart")
    # Abyss layer: desecrate then reveal for second guaranteed mod
    rl.add_rule(Condition.not_desecrated(), Action(Currency.DESECRATE), "apply bone")
    rl.add_rule(Condition.is_desecrated(), Action(Currency.REVEAL), "reveal abyss mod")
    # Fill remaining with targeted exalts
    rl.add_rule(
        Condition.missing_target_prefix(),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "exalt prefix",
    )
    rl.add_rule(
        Condition.missing_target_suffix(),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "exalt suffix",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_lesser_essence_exalt_fill() -> RuleList:
    """Seed 4b: Lesser Essence + Exalt Fill (budget).

    Like seed 4 but uses Lesser Essence (cheapest tier, worst mod tier).
    Good when the target mod family has many tiers and you just need any hit.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_LESSER), "lesser essence")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(300), Action(Currency.SCOUR), "restart")
    rl.add_rule(
        Condition.open_prefix_gte(1),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "exalt prefix (targeted)",
    )
    rl.add_rule(
        Condition.open_suffix_gte(1),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "exalt suffix (targeted)",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_normal_essence_exalt_fill() -> RuleList:
    """Seed 4c: Normal Essence + Exalt Fill (mid-tier).

    Uses Normal Essence (mid-price, mid-tier). A balanced option between
    the cheap Lesser and expensive Greater essences.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_NORMAL), "normal essence")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(350), Action(Currency.SCOUR), "restart")
    rl.add_rule(
        Condition.open_prefix_gte(1),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "exalt prefix (targeted)",
    )
    rl.add_rule(
        Condition.open_suffix_gte(1),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "exalt suffix (targeted)",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_chaos_whittling() -> RuleList:
    """Seed 6: Chaos + Omen of Whittling (targeted mod swap).

    Alchemy to rare, then chaos-swap with Whittling omen to replace the worst
    mod (lowest ilvl requirement = lowest tier). Cheap iteration that targets
    the weakest link each time.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.ALCHEMY), "alchemy to rare")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(2000), Action(Currency.FAIL), "budget exceeded")
    rl.add_rule(
        Condition.has_non_target_removable(),
        Action(Currency.CHAOS, Omen.WHITTLING),
        "whittling chaos: swap worst mod",
    )
    rl.add_rule(Condition.always_true(), Action(Currency.CHAOS), "plain chaos swap")
    return rl


def seed_omen_targeted_exalts() -> RuleList:
    """Seed 7: Omen-Targeted Exalts (sinistral/dextral on every slam).

    Alt-regal into rare, then every exalt uses a side-targeting omen.
    More expensive per slam but dramatically better odds of landing the
    target mod on the correct side. The control-oriented approach.
    """
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL), "promote")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "no target → new base")
    rl.add_rule(
        Condition.missing_target_prefix(),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "sinistral exalt for prefix",
    )
    rl.add_rule(
        Condition.missing_target_suffix(),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "dextral exalt for suffix",
    )
    rl.add_rule(
        Condition.removable_gt_targets(),
        Action(Currency.ANNULMENT, Omen.SINISTRAL_ANNULMENT),
        "targeted annul",
    )
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_fracture_workflow() -> RuleList:
    """Seed 8: Divine → Fracture (endgame, high-investment).

    Get a target mod, strip to isolate it, divine to max roll, fracture to lock
    permanently. Then fill remaining slots around the fractured mod. The
    highest-EV path for single-mod items (weapons, amulets).
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.ALCHEMY), "alchemy to rare")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(1500), Action(Currency.SCOUR), "restart")
    # Phase 1: get target on item
    rl.add_rule(
        Condition.missing_target_prefix(),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "slam for target prefix",
    )
    # Phase 2: strip non-targets
    rl.add_rule(
        Condition.has_non_target_removable(),
        Action(Currency.ANNULMENT),
        "annul junk before fracture",
    )
    # Phase 3: divine to max roll
    rl.add_rule(Condition.not_divined(), Action(Currency.DIVINE), "divine to max")
    # Phase 4: fracture the max-rolled mod
    rl.add_rule(Condition.has_been_divined(), Action(Currency.FRACTURING), "lock the mod")
    # Phase 5: fill around fractured mod
    rl.add_rule(
        Condition.has_fractured_mod(),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "fill around fracture",
    )
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback restart")
    return rl


def seed_buy_fractured_base() -> RuleList:
    """Seed 9: Buy Fractured Base (skip the fracture gamble).

    Start with a fractured base from trade that already has the target mod
    locked. Fill remaining slots. Trades currency for certainty — no risk
    of fracturing the wrong mod.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.BUY_FRACTURED), "buy fracture")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.cost_spent_gte(600), Action(Currency.FAIL), "budget exceeded")
    rl.add_rule(
        Condition.missing_target_prefix(),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "exalt prefix",
    )
    rl.add_rule(
        Condition.missing_target_suffix(),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "exalt suffix",
    )
    rl.add_rule(
        Condition.removable_gt_targets(),
        Action(Currency.ANNULMENT),
        "annul junk",
    )
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def seed_aggressive_restart() -> RuleList:
    """Seed 10: Aggressive Restart (low threshold, fast iteration).

    Very low cost threshold before restarting. Bets on getting lucky with a
    quick transmute→regal→exalt run. Wastes less on doomed items but needs
    more base items. Good when bases are cheap and currency is scarce.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL), "promote")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
    rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL), "promote")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "no target → new base")
    rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.EXALTED), "one exalt try")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "give up fast")
    return rl


def seed_deterministic_multimod() -> RuleList:
    """Seed 11: Deterministic Multi-Target (endgame sequential recipe).

    The sequential path endgame crafters use for mirror-tier items:
    buy magic(target1) → regal → essence(target2) → targeted exalt(target3)
    → desecrate+reveal(abyss target) → fill suffixes

    The key insight: find_first_missing_target makes each action pursue
    the NEXT unfilled target, so the rule priority encodes the crafting ORDER.
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.BUY_MAGIC), "buy magic w/ target 1")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.REGAL), "regal to rare")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_GREATER), "essence target 2")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "all targets done")
    # Targeted exalts — only when open slots exist
    rl.add_rule(
        Condition.open_prefix_gte(1),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "sinistral exalt for prefix target",
    )
    # Desecrate + reveal for abyss suffix target
    rl.add_rule(Condition.not_desecrated(), Action(Currency.DESECRATE), "desecrate for abyss")
    rl.add_rule(Condition.is_desecrated(), Action(Currency.REVEAL), "reveal abyss mod")
    # Dextral exalt for suffix targets (attack speed)
    rl.add_rule(
        Condition.open_suffix_gte(1),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "dextral exalt for suffix target",
    )
    # If prefixes are full but we're missing a target prefix → SCOUR AND RESTART
    # (don't annul — too risky to lose target mods we already have)
    rl.add_rule(Condition.missing_target_prefix(), Action(Currency.SCOUR), "restart: bad prefix fill")
    rl.add_rule(Condition.missing_target_suffix(), Action(Currency.SCOUR), "restart: bad suffix fill")
    rl.add_rule(Condition.cost_spent_gte(2000), Action(Currency.FAIL), "budget exceeded")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def seed_fracture_then_fill() -> RuleList:
    """Seed 12: Fracture First → Essence Second → Fill (high-investment).

    buy magic(target1) → regal → divine → fracture → essence(target2)
    → desecrate → reveal → targeted exalts for rest
    """
    rl = RuleList()
    rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.BUY_MAGIC), "buy magic target 1")
    rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.REGAL), "regal")
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "done")
    rl.add_rule(Condition.cost_spent_gte(1000), Action(Currency.SCOUR), "restart")
    rl.add_rule(Condition.not_divined(), Action(Currency.DIVINE), "divine to max")
    rl.add_rule(Condition.has_been_divined(), Action(Currency.FRACTURING), "fracture target 1")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_GREATER), "essence target 2")
    rl.add_rule(Condition.not_desecrated(), Action(Currency.DESECRATE), "desecrate")
    rl.add_rule(Condition.is_desecrated(), Action(Currency.REVEAL), "reveal abyss")
    rl.add_rule(
        Condition.missing_target_prefix(),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "exalt prefix",
    )
    rl.add_rule(
        Condition.missing_target_suffix(),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "exalt suffix",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback")
    return rl


# ── Population Seeding ────────────────────────────────────────────────────────

ALL_SEEDS = [
    seed_alt_regal_exalt,
    seed_greater_alt_regal,
    seed_perfect_currency,
    seed_essence_exalt_fill,
    seed_lesser_essence_exalt_fill,
    seed_normal_essence_exalt_fill,
    seed_essence_desecrate_exalt,
    seed_chaos_whittling,
    seed_omen_targeted_exalts,
    seed_fracture_workflow,
    seed_buy_fractured_base,
    seed_aggressive_restart,
    seed_deterministic_multimod,
    seed_fracture_then_fill,
]


def create_seeded_population(pop_size: int, seed_fraction: float = 0.4) -> list[RuleList]:
    """Create initial population with seed_fraction% from heuristics.

    Args:
        pop_size: total population size (e.g. 200)
        seed_fraction: fraction of population to fill with seeds (default 40%)

    Returns:
        List of RuleLists. First N are seeds (cycled if needed), rest are empty
        (to be filled with random individuals by the caller).
    """
    n_seeds = int(pop_size * seed_fraction)
    population: list[RuleList] = []

    # Cycle through seeds to fill the seeded portion
    for i in range(n_seeds):
        seed_fn = ALL_SEEDS[i % len(ALL_SEEDS)]
        population.append(seed_fn())

    return population


# ── Phase-Aware Seeds (for sub-goal decomposition) ───────────────────────────

def _seed_phase_exalt_prefix() -> RuleList:
    """Phase seed: simple sinistral exalt loop for a prefix target."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(
        Condition.open_prefix_gte(1),
        Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        "sinistral exalt",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_exalt_suffix() -> RuleList:
    """Phase seed: simple dextral exalt loop for a suffix target."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(
        Condition.open_suffix_gte(1),
        Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        "dextral exalt",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_exalt_natural() -> RuleList:
    """Phase seed: exalt without omen (natural prefix/suffix roll)."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.EXALTED), "natural exalt")
    rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.EXALTED), "natural exalt")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_greater_exalt_prefix() -> RuleList:
    """Phase seed: greater sinistral exalt for narrow pool prefix."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(
        Condition.open_prefix_gte(1),
        Action(Currency.GREATER_EXALTED, Omen.SINISTRAL_EXALTATION),
        "greater sinistral exalt",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_greater_exalt_suffix() -> RuleList:
    """Phase seed: greater dextral exalt for narrow pool suffix."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(
        Condition.open_suffix_gte(1),
        Action(Currency.GREATER_EXALTED, Omen.DEXTRAL_EXALTATION),
        "greater dextral exalt",
    )
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_lesser_essence() -> RuleList:
    """Phase seed: lesser essence for budget guaranteed mod."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_LESSER), "lesser essence")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_normal_essence() -> RuleList:
    """Phase seed: normal essence for mid-tier guaranteed mod."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_NORMAL), "normal essence")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_greater_essence() -> RuleList:
    """Phase seed: greater essence for best-tier guaranteed mod."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_GREATER), "greater essence")
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
    rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


def _seed_phase_desecrate_reveal() -> RuleList:
    """Phase seed: desecrate + reveal for an abyss suffix target."""
    rl = RuleList()
    rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
    rl.add_rule(Condition.not_desecrated(), Action(Currency.DESECRATE), "desecrate")
    rl.add_rule(Condition.is_desecrated(), Action(Currency.REVEAL), "reveal abyss")
    # If reveal didn't hit, annul the bad abyss mod and retry
    rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul bad reveal")
    rl.add_rule(Condition.cost_spent_gte(800), Action(Currency.FAIL), "budget")
    rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
    return rl


PHASE_SEEDS_PREFIX = [
    _seed_phase_exalt_prefix,
    _seed_phase_greater_exalt_prefix,
    _seed_phase_exalt_natural,
    _seed_phase_lesser_essence,
    _seed_phase_normal_essence,
    _seed_phase_greater_essence,
]

PHASE_SEEDS_SUFFIX = [
    _seed_phase_exalt_suffix,
    _seed_phase_greater_exalt_suffix,
    _seed_phase_exalt_natural,
    _seed_phase_desecrate_reveal,
    _seed_phase_lesser_essence,
    _seed_phase_normal_essence,
    _seed_phase_greater_essence,
]


def create_seeded_population_for_phase(
    pop_size: int,
    seed_fraction: float,
    phase_target_affix: str,
    setup_rules: list | None = None,
) -> list[RuleList]:
    """Generate seed strategies appropriate for a decomposed phase.

    Later phases (phase_index > 0) use exalt-focused seeds since the item
    is already Rare with prior-phase mods. Setup rules are prepended to
    recreate the starting state.

    Args:
        pop_size: total population size
        seed_fraction: fraction to fill with seeds
        phase_target_affix: "prefix" or "suffix" (determines seed set)
        setup_rules: rules to prepend (recreate prior-phase state)
    """
    from .gene import Rule

    seeds = PHASE_SEEDS_PREFIX if phase_target_affix == "prefix" else PHASE_SEEDS_SUFFIX
    n_seeds = int(pop_size * seed_fraction)
    population: list[RuleList] = []

    for i in range(n_seeds):
        seed_fn = seeds[i % len(seeds)]
        rl = seed_fn()

        # Prepend setup rules if provided
        if setup_rules:
            combined = RuleList()
            for rule in setup_rules:
                combined.add_rule(rule.condition, rule.action, rule.label)
            for rule in rl.rules:
                combined.add_rule(rule.condition, rule.action, rule.label)
            population.append(combined)
        else:
            population.append(rl)

    return population
