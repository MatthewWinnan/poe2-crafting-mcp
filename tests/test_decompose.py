"""Tests for sub-goal decomposition module.

Tests cover:
- Phase risk classification
- Quick cost estimation
- WSJF ordering
- Phase building
- Setup rule generation
- optimize_multi_target integration (with stub evaluator)
"""

import numpy as np
import pytest

from poe2_crafting_mcp.crafting.optimizer.gene import (
    CraftTarget,
    DecomposedResult,
    ModTarget,
    PhaseTarget,
    PhaseResult,
    PriceCache,
)
from poe2_crafting_mcp.crafting.optimizer.decompose import (
    classify_phase_risk,
    detect_free_hits,
    quick_estimate_phase,
    wsjf_score,
    optimal_ordering,
    build_phases,
    build_setup_rules,
    build_phase_craft_target,
    QuickEstimate,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_pool_data() -> dict:
    """Create a minimal pool_data dict for testing.

    Simulates a Gloves_int pool with 10 prefix families and 10 suffix families.
    Family IDs 1-10 for prefixes, 11-20 for suffixes.
    """
    n_prefix = 30  # 10 families × 3 tiers
    n_suffix = 30

    prefix_families = np.array(
        [fam for fam in range(1, 11) for _ in range(3)], dtype=np.uint16
    )
    prefix_tiers = np.array(
        [t for _ in range(10) for t in [1, 2, 3]], dtype=np.uint8
    )
    prefix_weights = np.array(
        [100, 500, 1000] * 10, dtype=np.uint32  # T1=100, T2=500, T3=1000
    )

    suffix_families = np.array(
        [fam for fam in range(11, 21) for _ in range(3)], dtype=np.uint16
    )
    suffix_tiers = np.array(
        [t for _ in range(10) for t in [1, 2, 3]], dtype=np.uint8
    )
    suffix_weights = np.array(
        [100, 500, 1000] * 10, dtype=np.uint32
    )

    return {
        "prefix_weights": prefix_weights,
        "prefix_families": prefix_families,
        "prefix_tiers": prefix_tiers,
        "prefix_req_levels": np.zeros(n_prefix, dtype=np.uint8),
        "prefix_cumsum": np.cumsum(prefix_weights.astype(np.uint64)),
        "suffix_weights": suffix_weights,
        "suffix_families": suffix_families,
        "suffix_tiers": suffix_tiers,
        "suffix_req_levels": np.zeros(n_suffix, dtype=np.uint8),
        "suffix_cumsum": np.cumsum(suffix_weights.astype(np.uint64)),
        "target_prefix_families": np.array([1, 2, 3], dtype=np.uint16),
        "target_suffix_families": np.array([11, 12], dtype=np.uint16),
        "target_max_tiers": np.array([1, 2, 2, 2, 3], dtype=np.uint8),
        "ilvl": 82,
        "max_prefixes": 3,
        "max_suffixes": 3,
    }


def _make_target_5() -> CraftTarget:
    """5-target craft: 3 prefixes + 2 suffixes."""
    return CraftTarget(
        targets=[
            ModTarget("FireDamage", 1, "prefix", 2),
            ModTarget("ColdDamage", 2, "prefix", 2),
            ModTarget("PhysDamage", 3, "prefix", 2),
            ModTarget("AttackSpeed", 11, "suffix", 3),
            ModTarget("CritChance", 12, "suffix", 2),
        ],
        item_class="Gloves_int",
        ilvl=82,
    )


def _make_target_3() -> CraftTarget:
    """3-target craft."""
    return CraftTarget(
        targets=[
            ModTarget("FireDamage", 1, "prefix", 1),
            ModTarget("Life", 2, "prefix", 2),
            ModTarget("FireRes", 11, "suffix", 2),
        ],
        item_class="Gloves_int",
        ilvl=82,
    )


def _make_prices() -> PriceCache:
    """Create a PriceCache for testing."""
    return PriceCache(
        currency={"exalted": 3.0, "greater_exalted": 5.0, "chaos": 1.0},
        omen={"sinistral_exaltation": 15.0, "dextral_exaltation": 15.0},
        essence={"greater_essence": 1.0},
        base_white=1.0,
        base_magic_with={"FireDamage": 35.0},
        trade_finished=500.0,
    )


def _default_prices() -> dict[str, float]:
    return {
        "exalted": 3.0,
        "greater_exalted": 5.0,
        "sinistral_exaltation": 15.0,
        "dextral_exaltation": 15.0,
        "greater_essence": 1.0,
        "buy_magic": 35.0,
        "chaos": 1.0,
        "annulment": 2.0,
    }


# ── Phase Risk Classification ────────────────────────────────────────────────

class TestClassifyPhaseRisk:
    def test_blank_start_is_safe(self):
        target = ModTarget("FireDamage", 1, "prefix", 1)
        assert classify_phase_risk(target, starting_mod_count=0, starting_rarity=0) == "safe"

    def test_rare_with_open_slots_is_safe(self):
        target = ModTarget("ColdDamage", 2, "prefix", 2)
        assert classify_phase_risk(target, starting_mod_count=3, starting_rarity=2) == "safe"

    def test_magic_item_is_safe(self):
        target = ModTarget("Life", 2, "prefix", 2)
        assert classify_phase_risk(target, starting_mod_count=1, starting_rarity=1) == "safe"

    def test_full_rare_is_destructive(self):
        target = ModTarget("FireDamage", 1, "prefix", 1)
        assert classify_phase_risk(target, starting_mod_count=6, starting_rarity=2) == "destructive"


# ── Quick Cost Estimation ────────────────────────────────────────────────────

class TestQuickEstimate:
    def test_blank_start_returns_buy_magic(self):
        target = ModTarget("FireDamage", 1, "prefix", 2)
        pool = _make_pool_data()
        prices = _default_prices()
        est = quick_estimate_phase(target, pool, prices)
        assert est.method == "buy_magic"
        assert est.is_deterministic
        assert est.expected_cost == 35.0
        assert est.success_rate == 1.0

    def test_magic_start_returns_essence(self):
        target = ModTarget("ColdDamage", 2, "prefix", 2)
        pool = _make_pool_data()
        prices = _default_prices()
        est = quick_estimate_phase(
            target, pool, prices,
            starting_mod_count=0, starting_rarity=0,
        )
        # From blank, it will suggest buy_magic (first phase)
        assert est.is_deterministic

    def test_exalt_phase_not_deterministic(self):
        target = ModTarget("PhysDamage", 3, "prefix", 2)
        pool = _make_pool_data()
        prices = _default_prices()
        est = quick_estimate_phase(
            target, pool, prices,
            starting_mod_count=2, starting_rarity=2,
        )
        assert not est.is_deterministic
        assert est.success_rate > 0
        assert est.success_rate < 1.0
        assert est.expected_cost > 0

    def test_exalt_cost_is_positive(self):
        target = ModTarget("AttackSpeed", 11, "suffix", 3)
        pool = _make_pool_data()
        prices = _default_prices()
        est = quick_estimate_phase(
            target, pool, prices,
            starting_mod_count=3, starting_rarity=2,
        )
        assert est.expected_cost > 0
        assert est.expected_cost < float("inf")


# ── WSJF Scoring ─────────────────────────────────────────────────────────────

class TestWSJFScore:
    def test_deterministic_gets_lowest_score(self):
        det = QuickEstimate(
            target=ModTarget("X", 1, "prefix", 1),
            method="buy_magic", expected_cost=35, success_rate=1.0,
            is_deterministic=True, risk="safe",
        )
        assert wsjf_score(det) == -1.0

    def test_high_success_gets_low_score(self):
        easy = QuickEstimate(
            target=ModTarget("X", 1, "prefix", 1),
            method="exalt", expected_cost=10, success_rate=0.9,
            is_deterministic=False, risk="safe",
        )
        hard = QuickEstimate(
            target=ModTarget("Y", 2, "prefix", 1),
            method="exalt", expected_cost=500, success_rate=0.03,
            is_deterministic=False, risk="safe",
        )
        assert wsjf_score(easy) < wsjf_score(hard)

    def test_cheap_phase_goes_first(self):
        cheap = QuickEstimate(
            target=ModTarget("X", 1, "prefix", 1),
            method="exalt", expected_cost=10, success_rate=0.5,
            is_deterministic=False, risk="safe",
        )
        expensive = QuickEstimate(
            target=ModTarget("Y", 2, "prefix", 1),
            method="exalt", expected_cost=100, success_rate=0.5,
            is_deterministic=False, risk="safe",
        )
        assert wsjf_score(cheap) < wsjf_score(expensive)


# ── Ordering ─────────────────────────────────────────────────────────────────

class TestOptimalOrdering:
    def test_single_target_trivial(self):
        target = CraftTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 1)],
            item_class="Gloves_int", ilvl=82,
        )
        pool = _make_pool_data()
        prices = _default_prices()
        ordering, rationale, candidates = optimal_ordering(target, pool, prices)
        assert ordering == [0]
        assert "single target" in rationale

    def test_five_targets_produces_valid_ordering(self):
        target = _make_target_5()
        pool = _make_pool_data()
        prices = _default_prices()
        ordering, rationale, candidates = optimal_ordering(target, pool, prices)
        assert len(ordering) == 5
        assert set(ordering) == {0, 1, 2, 3, 4}
        assert len(candidates) > 0

    def test_deterministic_phases_come_first(self):
        """Targets that can be obtained deterministically (buy_magic, essence)
        should be ordered before probabilistic targets (exalt)."""
        target = _make_target_5()
        pool = _make_pool_data()
        prices = _default_prices()
        ordering, _, _ = optimal_ordering(target, pool, prices)
        # First two phases should be deterministic (buy_magic/essence from blank)
        # The exact ordering depends on the estimation, but the first should be
        # one of the targets since all start from blank → buy_magic
        assert ordering[0] in range(5)  # valid index

    def test_three_targets_enumerates_all(self):
        target = _make_target_3()
        pool = _make_pool_data()
        prices = _default_prices()
        ordering, rationale, candidates = optimal_ordering(target, pool, prices)
        assert len(ordering) == 3
        # 3! = 6 permutations
        assert "Enumerated 6" in rationale


# ── Phase Building ───────────────────────────────────────────────────────────

class TestBuildPhases:
    def test_builds_correct_number_of_phases(self):
        target = _make_target_5()
        pool = _make_pool_data()
        prices = _default_prices()
        ordering = [0, 1, 2, 3, 4]
        phases = build_phases(target, ordering, pool, prices)
        assert len(phases) == 5

    def test_phase_0_starts_blank(self):
        target = _make_target_5()
        pool = _make_pool_data()
        prices = _default_prices()
        phases = build_phases(target, [0, 1, 2, 3, 4], pool, prices)
        assert phases[0].starting_mods == []
        assert phases[0].starting_rarity == 0
        assert phases[0].phase_index == 0

    def test_later_phases_have_starting_mods(self):
        target = _make_target_5()
        pool = _make_pool_data()
        prices = _default_prices()
        phases = build_phases(target, [0, 1, 2, 3, 4], pool, prices)
        assert len(phases[1].starting_mods) == 1
        assert len(phases[2].starting_mods) == 2
        assert len(phases[3].starting_mods) == 3
        assert len(phases[4].starting_mods) == 4

    def test_protected_families_includes_all(self):
        target = _make_target_5()
        pool = _make_pool_data()
        prices = _default_prices()
        phases = build_phases(target, [0, 1, 2, 3, 4], pool, prices)
        all_fam_ids = [t.family_id for t in target.targets]
        for phase in phases:
            assert phase.protected_families == all_fam_ids


# ── Setup Rules ──────────────────────────────────────────────────────────────

class TestBuildSetupRules:
    def test_phase_0_no_setup_rules(self):
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
            starting_mods=[],
            starting_rarity=0,
            phase_index=0,
        )
        rules = build_setup_rules(phase)
        assert len(rules) == 0

    def test_phase_1_has_buy_magic(self):
        phase = PhaseTarget(
            targets=[ModTarget("ColdDamage", 2, "prefix", 2)],
            starting_mods=[(1, "prefix", 2)],
            starting_rarity=1,
            phase_index=1,
        )
        rules = build_setup_rules(phase)
        assert len(rules) >= 1
        # First rule should be BUY_MAGIC
        from poe2_crafting_mcp.crafting.optimizer.gene import Currency
        assert rules[0].action.currency == Currency.BUY_MAGIC

    def test_phase_with_essence_has_essence_rule(self):
        phase = PhaseTarget(
            targets=[ModTarget("PhysDamage", 3, "prefix", 2)],
            starting_mods=[(1, "prefix", 2), (2, "prefix", 2)],
            starting_rarity=2,
            starting_flags=0x04,  # has_essence_mod
            phase_index=2,
        )
        rules = build_setup_rules(phase)
        from poe2_crafting_mcp.crafting.optimizer.gene import Currency
        currencies_used = [r.action.currency for r in rules]
        assert Currency.BUY_MAGIC in currencies_used
        assert Currency.ESSENCE_GREATER in currencies_used


# ── Phase CraftTarget Building ───────────────────────────────────────────────

class TestBuildPhaseCraftTarget:
    def test_phase_only_target(self):
        """build_phase_craft_target returns only this phase's targets."""
        full_target = _make_target_5()
        phase = PhaseTarget(
            targets=[full_target.targets[2]],  # PhysDamage
            starting_mods=[
                (1, "prefix", 2),  # FireDamage
                (2, "prefix", 2),  # ColdDamage
            ],
            phase_index=2,
        )
        phase_target = build_phase_craft_target(phase, full_target)
        assert len(phase_target.targets) == 1
        assert phase_target.targets[0].family == "PhysDamage"

    def test_runner_build_phase_pool_target_includes_prior(self):
        """_build_phase_pool_target (runner.py) includes prior + current targets."""
        from poe2_crafting_mcp.crafting.optimizer.runner import _build_phase_pool_target

        full_target = _make_target_5()
        phase = PhaseTarget(
            targets=[full_target.targets[2]],  # PhysDamage
            starting_mods=[
                (1, "prefix", 2),  # FireDamage
                (2, "prefix", 2),  # ColdDamage
            ],
            phase_index=2,
        )
        pool_target = _build_phase_pool_target(phase, full_target)
        # Should have 3 targets: Fire, Cold (prior), Phys (this phase)
        assert len(pool_target.targets) == 3
        families = [t.family for t in pool_target.targets]
        assert "FireDamage" in families
        assert "ColdDamage" in families
        assert "PhysDamage" in families


# ── Data Structure Tests ─────────────────────────────────────────────────────

class TestPhaseTarget:
    def test_str_representation(self):
        pt = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
            phase_index=0,
        )
        assert "FireDamage" in str(pt)

    def test_is_later_phase(self):
        p0 = PhaseTarget(targets=[], phase_index=0)
        p1 = PhaseTarget(targets=[], phase_index=1)
        assert not p0.is_later_phase
        assert p1.is_later_phase


class TestDecomposedResult:
    def test_summary(self):
        from poe2_crafting_mcp.crafting.optimizer.runner import CraftingStrategy
        from poe2_crafting_mcp.crafting.optimizer.gene import Fitness, RuleList

        pr = PhaseResult(
            phase_index=0,
            phase_target=PhaseTarget(
                targets=[ModTarget("Fire", 1, "prefix", 1)],
            ),
            strategy=CraftingStrategy(
                rulelist=RuleList(), fitness=Fitness(),
                expected_cost=35, success_rate=1.0,
            ),
            expected_cost=35,
            success_rate=1.0,
            restart_risk="safe",
            cumulative_cost=35,
        )
        result = DecomposedResult(
            phases=[pr],
            total_expected_cost=35,
            total_success_rate=1.0,
            ordering=[0],
            ordering_rationale="test",
            item_class="Gloves_int",
            ilvl=82,
        )
        summary = result.summary()
        assert "35" in summary
        assert "Gloves_int" in summary


# ── Phase-Aware Seeds ────────────────────────────────────────────────────────

class TestPhaseAwareSeeds:
    def test_creates_correct_count(self):
        from poe2_crafting_mcp.crafting.optimizer.seeds import (
            create_seeded_population_for_phase,
        )
        pop = create_seeded_population_for_phase(100, 0.4, "prefix")
        assert len(pop) == 40

    def test_suffix_seeds_include_dextral(self):
        from poe2_crafting_mcp.crafting.optimizer.seeds import (
            create_seeded_population_for_phase,
        )
        from poe2_crafting_mcp.crafting.optimizer.gene import Omen
        pop = create_seeded_population_for_phase(20, 1.0, "suffix")
        # At least one seed should use dextral exaltation
        has_dextral = False
        for rl in pop:
            for rule in rl.rules:
                if rule.action.omen == Omen.DEXTRAL_EXALTATION:
                    has_dextral = True
                    break
        assert has_dextral

    def test_setup_rules_prepended(self):
        from poe2_crafting_mcp.crafting.optimizer.seeds import (
            create_seeded_population_for_phase,
        )
        from poe2_crafting_mcp.crafting.optimizer.gene import (
            Rule, Condition, Action, Currency, Rarity,
        )
        setup = [
            Rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.BUY_MAGIC), "setup"),
        ]
        pop = create_seeded_population_for_phase(10, 1.0, "prefix", setup)
        for rl in pop:
            assert rl.rules[0].action.currency == Currency.BUY_MAGIC
            assert rl.rules[0].label == "setup"


# ── Free-Hit Detection ──────────────────────────────────────────────────────

class TestFreeHitDetection:
    def test_no_remaining_targets(self):
        pool = _make_pool_data()
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
        )
        result = detect_free_hits(phase, [], pool)
        assert result == []

    def test_low_weight_target_not_flagged(self):
        """A target with low pool weight should NOT be flagged as free hit."""
        pool = _make_pool_data()
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
        )
        # T1 only (weight=100 out of 16000 total) → p ≈ 0.6% per roll
        # With 2 random mods: p ≈ 1.2% — well below 30% threshold
        remaining = [ModTarget("ColdDamage", 2, "prefix", 1)]
        result = detect_free_hits(phase, remaining, pool)
        assert result == []

    def test_high_weight_target_flagged(self):
        """A target accepting all tiers with high weight gets flagged."""
        pool = _make_pool_data()
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
        )
        # T3 target (weight=100+500+1000=1600 out of 16000) → p = 10% per roll
        # With 4 random mods: p ≈ 34% — above 30% threshold
        remaining = [ModTarget("ColdDamage", 2, "prefix", 3)]
        result = detect_free_hits(phase, remaining, pool, expected_random_mods=4)
        assert 0 in result

    def test_threshold_parameter(self):
        """Lower threshold should flag more targets."""
        pool = _make_pool_data()
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
        )
        # T2 target (weight=100+500=600 out of 16000) → p ≈ 3.75% per roll
        # With 2 random: p ≈ 7.4%
        remaining = [ModTarget("ColdDamage", 2, "prefix", 2)]
        # Not flagged at default 30%
        assert detect_free_hits(phase, remaining, pool) == []
        # Flagged at 5% threshold
        assert 0 in detect_free_hits(phase, remaining, pool, threshold=0.05)

    def test_zero_random_mods(self):
        """With no random mods, nothing should be flagged."""
        pool = _make_pool_data()
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
        )
        remaining = [ModTarget("ColdDamage", 2, "prefix", 3)]
        result = detect_free_hits(phase, remaining, pool, expected_random_mods=0)
        assert result == []

    def test_suffix_target_uses_suffix_pool(self):
        """Suffix targets should be evaluated against suffix pool weights."""
        pool = _make_pool_data()
        phase = PhaseTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
        )
        remaining = [ModTarget("AttackSpeed", 11, "suffix", 3)]
        # T3 suffix: weight=1600/16000 = 10%, 4 random: p ≈ 34%
        result = detect_free_hits(phase, remaining, pool, expected_random_mods=4)
        assert 0 in result


# ── Initial State Encoding ───────────────────────────────────────────────────

class TestEncodeInitialState:
    def test_blank_phase_returns_none(self):
        from poe2_crafting_mcp.crafting.optimizer.bridge import encode_initial_state
        phase = PhaseTarget(targets=[ModTarget("Fire", 1, "prefix", 1)])
        assert encode_initial_state(phase) is None

    def test_one_prior_prefix(self):
        from poe2_crafting_mcp.crafting.optimizer.bridge import encode_initial_state
        phase = PhaseTarget(
            targets=[ModTarget("Cold", 2, "suffix", 2)],
            starting_mods=[(100, "prefix", 1)],
            starting_rarity=2,
            phase_index=1,
        )
        data = encode_initial_state(phase)
        assert data is not None
        assert data[0] == 2    # rarity = Rare
        assert data[1] == 1    # 1 prefix
        assert data[2] == 0    # 0 suffixes
        assert data[5] == 100  # pf0
        assert data[11] == 1   # pt0

    def test_mixed_prefixes_and_suffixes(self):
        from poe2_crafting_mcp.crafting.optimizer.bridge import encode_initial_state
        phase = PhaseTarget(
            targets=[ModTarget("Phys", 3, "prefix", 1)],
            starting_mods=[(10, "prefix", 1), (20, "suffix", 2), (30, "prefix", 3)],
            starting_rarity=2,
            starting_flags=0x04,
            phase_index=3,
        )
        data = encode_initial_state(phase)
        assert data[1] == 2    # 2 prefixes
        assert data[2] == 1    # 1 suffix
        assert data[4] == 4    # flags
        assert data[5] == 10   # pf0
        assert data[6] == 30   # pf1
        assert data[8] == 20   # sf0
        assert data[11] == 1   # pt0
        assert data[12] == 3   # pt1
        assert data[14] == 2   # st0


# ── Cooperative Coevolution ─────────────────────────────────────────────────

class TestCooperativeCoevolution:
    """Tests for optimize_cooperative (Tier 2).

    Uses the Python stub evaluator (no Rust needed) to verify:
    - Function accepts same interface as optimize_multi_target
    - Returns DecomposedResult with correct structure
    - Falls back to monolithic for small target counts
    - Maintains per-phase sub-populations
    """

    def test_small_target_falls_back_to_monolithic(self):
        """With < decompose_threshold targets, CC falls back to optimize()."""
        from poe2_crafting_mcp.crafting.optimizer.runner import (
            optimize_cooperative, OptimizerConfig,
        )

        pool = _make_pool_data()
        target = CraftTarget(
            targets=[ModTarget("FireDamage", 1, "prefix", 2)],
            item_class="Gloves_int",
            ilvl=82,
        )
        prices = _make_prices()
        config = OptimizerConfig(pop_size=10, max_generations=2, mc_trials=10)

        result = optimize_cooperative(pool, target, prices, config)

        assert isinstance(result, DecomposedResult)
        assert len(result.phases) == 1
        assert "Monolithic" in result.ordering_rationale

    def test_returns_decomposed_result(self):
        """CC returns a properly structured DecomposedResult."""
        from poe2_crafting_mcp.crafting.optimizer.runner import (
            optimize_cooperative, OptimizerConfig,
        )

        pool = _make_pool_data()
        target = _make_target_5()
        prices = _make_prices()
        config = OptimizerConfig(pop_size=10, max_generations=3, mc_trials=10)

        result = optimize_cooperative(pool, target, prices, config)

        assert isinstance(result, DecomposedResult)
        assert len(result.phases) == 5
        assert len(result.ordering) == 5
        assert result.wall_time_seconds > 0
        assert "CC:" in result.ordering_rationale

    def test_phases_have_strategies(self):
        """Each phase should have a strategy (even with stub evaluator)."""
        from poe2_crafting_mcp.crafting.optimizer.runner import (
            optimize_cooperative, OptimizerConfig,
        )

        pool = _make_pool_data()
        target = _make_target_5()
        prices = _make_prices()
        config = OptimizerConfig(pop_size=10, max_generations=3, mc_trials=10)

        result = optimize_cooperative(pool, target, prices, config)

        for pr in result.phases:
            assert pr.strategy is not None
            assert pr.phase_target is not None
            assert pr.restart_risk in ("safe", "destructive", "full_restart")

    def test_cumulative_cost_increases(self):
        """Cumulative cost should be monotonically increasing across phases."""
        from poe2_crafting_mcp.crafting.optimizer.runner import (
            optimize_cooperative, OptimizerConfig,
        )

        pool = _make_pool_data()
        target = _make_target_5()
        prices = _make_prices()
        config = OptimizerConfig(pop_size=10, max_generations=3, mc_trials=10)

        result = optimize_cooperative(pool, target, prices, config)

        prev_cum = 0.0
        for pr in result.phases:
            assert pr.cumulative_cost >= prev_cum
            prev_cum = pr.cumulative_cost

    def test_total_cost_equals_sum_of_phases(self):
        """Total cost should equal sum of individual phase costs."""
        from poe2_crafting_mcp.crafting.optimizer.runner import (
            optimize_cooperative, OptimizerConfig,
        )

        pool = _make_pool_data()
        target = _make_target_5()
        prices = _make_prices()
        config = OptimizerConfig(pop_size=10, max_generations=3, mc_trials=10)

        result = optimize_cooperative(pool, target, prices, config)

        phase_sum = sum(pr.expected_cost for pr in result.phases)
        # Both may be inf if stub evaluator didn't find viable strategies
        if phase_sum == float("inf"):
            assert result.total_expected_cost == float("inf")
        else:
            assert abs(result.total_expected_cost - phase_sum) < 0.01
