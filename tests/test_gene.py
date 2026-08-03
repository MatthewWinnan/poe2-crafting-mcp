"""Tests for poe2_crafting_mcp.crafting.optimizer.gene module.

Covers: Condition serialization, RuleList operations, population serialization,
Fitness dominance + credit assignment, behavioral descriptors, PriceCache encoding,
and copy semantics.
"""

import math
import struct

import numpy as np
import pytest

from poe2_crafting_mcp.crafting.optimizer.gene import (
    MAX_RULES,
    Action,
    Condition,
    CraftTarget,
    Currency,
    Fitness,
    Individual,
    ModTarget,
    Omen,
    Predicate,
    PriceCache,
    Rarity,
    Rule,
    RuleList,
    serialize_population,
)


# ══════════════════════════════════════════════════════════════════════════════
# Condition serialization
# ══════════════════════════════════════════════════════════════════════════════


class TestCondition:
    """Condition creation, serialization, and display."""

    def test_rarity_is(self):
        c = Condition.rarity_is(Rarity.MAGIC)
        assert c.predicate == Predicate.RARITY_IS
        assert c.arg1 == 1
        assert c.to_array() == (0, 1, 0)
        assert "MAGIC" in str(c)

    def test_always_true(self):
        c = Condition.always_true()
        assert c.predicate == Predicate.ALWAYS_TRUE
        assert c.to_array() == (255, 0, 0)
        assert str(c) == "DEFAULT"

    def test_cost_spent_gte_roundtrip(self):
        """f32 encoding into two u16s must roundtrip correctly."""
        for val in [0.0, 1.0, 50.0, 123.456, 500.0, 999.99, 10000.0]:
            c = Condition.cost_spent_gte(val)
            assert c.predicate == Predicate.COST_SPENT_GTE
            recovered = c.cost_threshold
            assert recovered is not None
            assert abs(recovered - val) < 0.01, f"Failed for {val}: got {recovered}"

    def test_cost_spent_gte_large_values(self):
        """Very large cost thresholds."""
        c = Condition.cost_spent_gte(50000.0)
        assert abs(c.cost_threshold - 50000.0) < 1.0

    def test_simple_predicates_no_args(self):
        """Predicates with no arguments serialize as (id, 0, 0)."""
        cases = [
            (Condition.has_any_target(), Predicate.HAS_ANY_TARGET),
            (Condition.all_targets_hit(), Predicate.ALL_TARGETS_HIT),
            (Condition.missing_target_prefix(), Predicate.MISSING_TARGET_PREFIX),
            (Condition.missing_target_suffix(), Predicate.MISSING_TARGET_SUFFIX),
            (Condition.has_non_target_removable(), Predicate.HAS_NON_TARGET_REMOVABLE),
            (Condition.removable_gt_targets(), Predicate.REMOVABLE_GT_TARGETS),
            (Condition.prefix_full_no_target_prefix(), Predicate.PREFIX_FULL_NO_TARGET_PREFIX),
            (Condition.suffix_full_no_target_suffix(), Predicate.SUFFIX_FULL_NO_TARGET_SUFFIX),
            (Condition.has_fractured_mod(), Predicate.HAS_FRACTURED_MOD),
            (Condition.has_essence_mod(), Predicate.HAS_ESSENCE_MOD),
            (Condition.no_essence_mod(), Predicate.NO_ESSENCE_MOD),
            (Condition.fractured_is_target(), Predicate.FRACTURED_IS_TARGET),
            (Condition.is_desecrated(), Predicate.IS_DESECRATED),
            (Condition.not_desecrated(), Predicate.NOT_DESECRATED),
            (Condition.has_been_divined(), Predicate.HAS_BEEN_DIVINED),
            (Condition.not_divined(), Predicate.NOT_DIVINED),
        ]
        for cond, expected_pred in cases:
            arr = cond.to_array()
            assert arr == (int(expected_pred), 0, 0), f"Failed for {expected_pred.name}"

    def test_predicates_with_arg(self):
        """Predicates with one integer argument."""
        c = Condition.open_prefix_gte(2)
        assert c.to_array() == (int(Predicate.OPEN_PREFIX_GTE), 2, 0)
        c = Condition.targets_on_item_gte(3)
        assert c.to_array() == (int(Predicate.TARGETS_ON_ITEM_GTE), 3, 0)
        c = Condition.step_count_gte(100)
        assert c.to_array() == (int(Predicate.STEP_COUNT_GTE), 100, 0)

    def test_frozen(self):
        """Conditions are immutable."""
        c = Condition.all_targets_hit()
        with pytest.raises(AttributeError):
            c.predicate = Predicate.RARITY_IS  # type: ignore

    def test_cost_threshold_none_for_non_cost(self):
        """cost_threshold returns None for non-COST_SPENT_GTE conditions."""
        c = Condition.all_targets_hit()
        assert c.cost_threshold is None


# ══════════════════════════════════════════════════════════════════════════════
# Action
# ══════════════════════════════════════════════════════════════════════════════


class TestAction:
    """Action creation and properties."""

    def test_simple_currency(self):
        a = Action(Currency.EXALTED)
        assert a.to_array() == (20, 0)
        assert not a.has_omen
        assert not a.is_terminal
        assert not a.is_restart
        assert str(a) == "exalted"

    def test_with_omen(self):
        a = Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION)
        assert a.to_array() == (20, 1)
        assert a.has_omen
        assert "sinistral_exaltation" in str(a)

    def test_terminal_actions(self):
        assert Action(Currency.DONE).is_terminal
        assert Action(Currency.FAIL).is_terminal
        assert not Action(Currency.EXALTED).is_terminal

    def test_restart_actions(self):
        assert Action(Currency.SCOUR).is_restart
        assert Action(Currency.BUY_BASE).is_restart
        assert Action(Currency.BUY_MAGIC).is_restart
        assert Action(Currency.BUY_FRACTURED).is_restart
        assert Action(Currency.REFORGE).is_restart
        assert not Action(Currency.EXALTED).is_restart

    def test_advanced_currencies_exist(self):
        """All crafting mechanics are representable."""
        assert Action(Currency.FRACTURING).to_array() == (30, 0)
        assert Action(Currency.ESSENCE_UPGRADE).to_array() == (31, 0)
        assert Action(Currency.ESSENCE_SWAP).to_array() == (32, 0)
        assert Action(Currency.DIVINE).to_array() == (33, 0)
        assert Action(Currency.VAAL).to_array() == (34, 0)

    def test_frozen(self):
        a = Action(Currency.CHAOS)
        with pytest.raises(AttributeError):
            a.currency = Currency.EXALTED  # type: ignore


# ══════════════════════════════════════════════════════════════════════════════
# RuleList operations
# ══════════════════════════════════════════════════════════════════════════════


class TestRuleList:
    """RuleList add/remove/insert/swap/size constraints."""

    def _make_rule(self, currency: Currency = Currency.EXALTED) -> Rule:
        return Rule(Condition.always_true(), Action(currency))

    def test_add_and_size(self):
        rl = RuleList()
        assert rl.size == 0
        rl.add_rule(Condition.always_true(), Action(Currency.DONE))
        assert rl.size == 1

    def test_max_rules_cap(self):
        rl = RuleList()
        for i in range(25):
            rl.add_rule(Condition.always_true(), Action(Currency.CHAOS))
        assert rl.size == MAX_RULES

    def test_remove_respects_minimum(self):
        rl = RuleList(rules=[self._make_rule() for _ in range(3)])
        assert rl.size == 3
        rl.remove_rule(0)
        assert rl.size == 3  # minimum 3, can't go below

    def test_remove_works_above_minimum(self):
        rl = RuleList(rules=[self._make_rule() for _ in range(5)])
        rl.remove_rule(2)
        assert rl.size == 4

    def test_remove_out_of_bounds(self):
        rl = RuleList(rules=[self._make_rule() for _ in range(5)])
        rl.remove_rule(99)
        assert rl.size == 5  # no change

    def test_insert_rule(self):
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        rl.insert_rule(1, Rule(Condition.all_targets_hit(), Action(Currency.DONE)))
        assert rl.size == 3
        assert rl.rules[1].action.currency == Currency.DONE

    def test_insert_at_max(self):
        rl = RuleList(rules=[self._make_rule() for _ in range(MAX_RULES)])
        rl.insert_rule(5, self._make_rule(Currency.DONE))
        assert rl.size == MAX_RULES  # no change

    def test_swap_rules(self):
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        rl.swap_rules(0, 1)
        assert rl.rules[0].action.currency == Currency.SCOUR
        assert rl.rules[1].action.currency == Currency.TRANSMUTE

    def test_swap_invalid_indices(self):
        rl = RuleList(rules=[self._make_rule() for _ in range(3)])
        original = [r.action.currency for r in rl.rules]
        rl.swap_rules(0, 99)
        assert [r.action.currency for r in rl.rules] == original


# ══════════════════════════════════════════════════════════════════════════════
# Serialization
# ══════════════════════════════════════════════════════════════════════════════


class TestSerialization:
    """RuleList and population serialization to numpy arrays."""

    def test_rulelist_serialize_shape(self):
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        conds, acts, n = rl.serialize()
        assert conds.shape == (MAX_RULES, 3)
        assert acts.shape == (MAX_RULES, 2)
        assert conds.dtype == np.uint16
        assert acts.dtype == np.uint16
        assert n == 2

    def test_rulelist_serialize_values(self):
        rl = RuleList()
        rl.add_rule(
            Condition.open_prefix_gte(2),
            Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        )
        conds, acts, n = rl.serialize()
        # First rule: predicate=OPEN_PREFIX_GTE(9), arg1=2, arg2=0
        assert conds[0, 0] == int(Predicate.OPEN_PREFIX_GTE)
        assert conds[0, 1] == 2
        assert conds[0, 2] == 0
        # Action: currency=EXALTED(20), omen=SINISTRAL_EXALTATION(1)
        assert acts[0, 0] == int(Currency.EXALTED)
        assert acts[0, 1] == int(Omen.SINISTRAL_EXALTATION)

    def test_unused_slots_are_zero(self):
        rl = RuleList()
        rl.add_rule(Condition.always_true(), Action(Currency.DONE))
        conds, acts, _ = rl.serialize()
        # Slots 1..MAX_RULES should be all zeros
        assert np.all(conds[1:] == 0)
        assert np.all(acts[1:] == 0)

    def test_population_serialize(self):
        pop = []
        for size in [3, 5, 9]:
            rl = RuleList()
            for _ in range(size):
                rl.add_rule(Condition.always_true(), Action(Currency.CHAOS))
            pop.append(Individual(rl))

        arr, counts, sz = serialize_population(pop)
        assert arr.shape == (3, MAX_RULES, 5)
        assert arr.dtype == np.uint16
        assert counts.tolist() == [3, 5, 9]
        assert sz == 3

    def test_population_serialize_packed_format(self):
        """Each rule packs as [pred, arg1, arg2, currency, omen]."""
        rl = RuleList()
        rl.add_rule(
            Condition.cost_spent_gte(200.0),
            Action(Currency.ANNULMENT, Omen.DEXTRAL_ANNULMENT),
        )
        pop = [Individual(rl)]
        arr, _, _ = serialize_population(pop)
        row = arr[0, 0]  # first individual, first rule
        assert row[0] == int(Predicate.COST_SPENT_GTE)  # predicate
        assert row[3] == int(Currency.ANNULMENT)         # currency
        assert row[4] == int(Omen.DEXTRAL_ANNULMENT)     # omen


# ══════════════════════════════════════════════════════════════════════════════
# Fitness & Credit Assignment
# ══════════════════════════════════════════════════════════════════════════════


class TestFitness:
    """Pareto dominance, credit assignment, degenerate detection."""

    def test_dominance_clear_winner(self):
        better = Fitness(expected_cost=50, success_rate=0.95, cost_p90=100)
        worse = Fitness(expected_cost=100, success_rate=0.80, cost_p90=200)
        assert better.dominates(worse)
        assert not worse.dominates(better)

    def test_dominance_not_comparable(self):
        """Neither dominates when each is better on a different axis."""
        a = Fitness(expected_cost=50, success_rate=0.80, cost_p90=200)
        b = Fitness(expected_cost=100, success_rate=0.95, cost_p90=100)
        assert not a.dominates(b)
        assert not b.dominates(a)

    def test_dominance_equal(self):
        """Equal fitness = no domination."""
        a = Fitness(expected_cost=50, success_rate=0.90, cost_p90=100)
        b = Fitness(expected_cost=50, success_rate=0.90, cost_p90=100)
        assert not a.dominates(b)
        assert not b.dominates(a)

    def test_dominance_better_on_two_equal_on_one(self):
        """Better on 2 axes, equal on 1 = dominates."""
        a = Fitness(expected_cost=50, success_rate=0.95, cost_p90=100)
        b = Fitness(expected_cost=50, success_rate=0.80, cost_p90=200)
        assert a.dominates(b)

    def test_degenerate(self):
        assert Fitness(expected_cost=float("inf"), success_rate=0.0).is_degenerate
        assert Fitness(expected_cost=100, success_rate=0.04).is_degenerate
        assert not Fitness(expected_cost=100, success_rate=0.10).is_degenerate

    def test_objectives_tuple(self):
        f = Fitness(expected_cost=85, success_rate=0.92, cost_p90=210)
        assert f.objectives == (85.0, pytest.approx(0.08), 210.0)

    def test_rule_is_dead(self):
        f = Fitness(fire_on_success=[0, 50, 0], fire_on_failure=[0, 20, 5])
        assert f.rule_is_dead(0)      # both zero
        assert not f.rule_is_dead(1)  # has fires
        assert not f.rule_is_dead(2)  # fires on failure only

    def test_rule_is_harmful(self):
        f = Fitness(fire_on_success=[5, 100], fire_on_failure=[40, 10])
        assert f.rule_is_harmful(0)       # ratio 40/5 = 8 > 3
        assert not f.rule_is_harmful(1)   # ratio 10/100 = 0.1

    def test_rule_is_key(self):
        f = Fitness(fire_on_success=[100, 5], fire_on_failure=[0, 40])
        assert f.rule_is_key(0)       # 100 success, 0 failure
        assert not f.rule_is_key(1)   # ratio 5/40 = 0.125

    def test_credit_out_of_bounds(self):
        """Out-of-bounds index returns 0 counts, treated as dead."""
        f = Fitness(fire_on_success=[10], fire_on_failure=[5])
        assert f.rule_is_dead(99)  # index beyond list


# ══════════════════════════════════════════════════════════════════════════════
# Behavioral Descriptors (QD Archive)
# ══════════════════════════════════════════════════════════════════════════════


class TestBehavioralDescriptors:
    """RuleList behavioral descriptors for QD bucketing."""

    def test_primary_early_currency_transmute(self):
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.primary_early_currency == "transmute"

    def test_primary_early_currency_alchemy(self):
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.ALCHEMY))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.primary_early_currency == "alchemy"

    def test_primary_early_currency_chaos(self):
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.ALCHEMY))
        rl.add_rule(Condition.rarity_is(Rarity.RARE), Action(Currency.CHAOS))
        rl.add_rule(Condition.rarity_is(Rarity.RARE), Action(Currency.GREATER_CHAOS))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.primary_early_currency == "chaos"

    def test_restart_threshold_found(self):
        rl = RuleList()
        rl.add_rule(Condition.always_true(), Action(Currency.EXALTED))
        rl.add_rule(Condition.cost_spent_gte(300.0), Action(Currency.SCOUR))
        assert abs(rl.restart_threshold - 300.0) < 0.01

    def test_restart_threshold_missing(self):
        rl = RuleList()
        rl.add_rule(Condition.always_true(), Action(Currency.EXALTED))
        assert rl.restart_threshold == 999.0

    def test_omen_count(self):
        rl = RuleList()
        rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION))
        rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.omen_count == 2

    def test_omen_count_none(self):
        rl = RuleList()
        rl.add_rule(Condition.always_true(), Action(Currency.CHAOS))
        assert rl.omen_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# Copy Semantics
# ══════════════════════════════════════════════════════════════════════════════


class TestCopySemantics:
    """Deep copy prevents mutation of original."""

    def test_rulelist_copy_independent(self):
        rl = RuleList()
        rl.add_rule(Condition.always_true(), Action(Currency.CHAOS))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))

        copy = rl.copy()
        copy.remove_rule(0)  # won't work (min 3), but add then remove
        copy.add_rule(Condition.always_true(), Action(Currency.DONE))
        copy.add_rule(Condition.always_true(), Action(Currency.FAIL))
        copy.remove_rule(0)

        # Original unchanged
        assert rl.size == 2
        assert rl.rules[0].action.currency == Currency.CHAOS

    def test_individual_copy_resets_fitness(self):
        rl = RuleList()
        rl.add_rule(Condition.always_true(), Action(Currency.DONE))

        ind = Individual(rl, fitness=Fitness(expected_cost=50, success_rate=0.9, cost_p90=80))
        copy = ind.copy()

        assert copy.fitness.expected_cost == float("inf")
        assert not copy.evaluated
        assert ind.evaluated


# ══════════════════════════════════════════════════════════════════════════════
# PriceCache
# ══════════════════════════════════════════════════════════════════════════════


class TestPriceCache:
    """Price encoding for Rust boundary."""

    def test_encode_currency_by_id(self):
        pc = PriceCache(currency={"exalted": 5.0, "chaos": 1.0, "annulment": 4.1})
        arr = pc.encode_for_rust()
        assert arr[int(Currency.EXALTED)] == pytest.approx(5.0)
        assert arr[int(Currency.CHAOS)] == pytest.approx(1.0)
        assert arr[int(Currency.ANNULMENT)] == pytest.approx(4.1)

    def test_encode_scour_from_currency_dict(self):
        pc = PriceCache(currency={"scouring": 0.5})
        arr = pc.encode_for_rust()
        assert arr[int(Currency.SCOUR)] == pytest.approx(0.5)

    def test_encode_base_white(self):
        pc = PriceCache(base_white=3.0)
        arr = pc.encode_for_rust()
        assert arr[int(Currency.BUY_BASE)] == pytest.approx(3.0)

    def test_encode_omen_offset(self):
        pc = PriceCache(omen={"sinistral_exaltation": 15.0})
        arr = pc.encode_for_rust()
        max_cid = max(int(c) for c in Currency) + 1
        assert arr[max_cid + int(Omen.SINISTRAL_EXALTATION)] == pytest.approx(15.0)

    def test_encode_shape(self):
        pc = PriceCache()
        arr = pc.encode_for_rust()
        max_cid = max(int(c) for c in Currency) + 1
        max_oid = max(int(o) for o in Omen) + 1
        assert arr.shape == (max_cid + max_oid,)
        assert arr.dtype == np.float32

    def test_unknown_currency_ignored(self):
        pc = PriceCache(currency={"nonexistent_orb": 99.0})
        arr = pc.encode_for_rust()
        # Should not crash, unknown currency is not mapped to any slot.
        # Only default scour (0.5) and buy_base (1.0) are set from defaults.
        assert arr[int(Currency.EXALTED)] == 0.0
        assert arr[int(Currency.CHAOS)] == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# CraftTarget
# ══════════════════════════════════════════════════════════════════════════════


class TestCraftTarget:
    """Target specification."""

    def test_prefix_suffix_split(self):
        target = CraftTarget(
            item_class="Gloves_int",
            ilvl=82,
            targets=[
                ModTarget("IncreasedLife", 101, "prefix", 1),
                ModTarget("IncreasedES", 102, "prefix", 1),
                ModTarget("FireResistance", 201, "suffix", 2),
            ],
        )
        assert len(target.prefix_targets) == 2
        assert len(target.suffix_targets) == 1
        assert target.prefix_family_ids == [101, 102]
        assert target.suffix_family_ids == [201]
        assert target.max_tiers == [1, 1, 2]

    def test_str(self):
        target = CraftTarget(
            item_class="Boots_dex",
            ilvl=75,
            targets=[ModTarget("MovementSpeed", 50, "prefix", 1)],
        )
        s = str(target)
        assert "Boots_dex" in s
        assert "ilvl75" in s
        assert "MovementSpeed" in s


# ══════════════════════════════════════════════════════════════════════════════
# Integration: Full Strategy Rule-List
# ══════════════════════════════════════════════════════════════════════════════


class TestFullStrategy:
    """End-to-end construction of realistic crafting strategies."""

    def test_alt_regal_strategy(self):
        """Classic alt-regal-exalt flow."""
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
        rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "reroll")
        rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL), "promote")
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
        rl.add_rule(Condition.cost_spent_gte(500), Action(Currency.SCOUR), "restart")
        rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.EXALTED), "exalt")
        rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul")
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback")
        assert rl.size == 8
        # Serializes without error
        conds, acts, n = rl.serialize()
        assert n == 8

    def test_essence_strategy(self):
        """Essence-based crafting flow."""
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_UPGRADE))
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE))
        rl.add_rule(Condition.has_essence_mod(), Action(Currency.ESSENCE_SWAP))
        rl.add_rule(Condition.cost_spent_gte(200), Action(Currency.SCOUR))
        rl.add_rule(Condition.always_true(), Action(Currency.EXALTED))
        assert rl.size == 6

    def test_fracture_strategy(self):
        """Fracture a T1 mod then fill the rest."""
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.ALCHEMY))
        rl.add_rule(Condition.has_target(0), Action(Currency.FRACTURING))
        rl.add_rule(Condition.has_fractured_mod(), Action(Currency.CHAOS))
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE))
        rl.add_rule(Condition.cost_spent_gte(1000), Action(Currency.FAIL))
        rl.add_rule(Condition.always_true(), Action(Currency.CHAOS))
        assert rl.size == 6

    def test_omen_targeted_strategy(self):
        """Omen-targeted exalts with sinistral/dextral."""
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR))
        rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL))
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE))
        rl.add_rule(Condition.cost_spent_gte(800), Action(Currency.SCOUR))
        rl.add_rule(
            Condition.missing_target_prefix(),
            Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
        )
        rl.add_rule(
            Condition.missing_target_suffix(),
            Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION),
        )
        rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.size == 9
        assert rl.omen_count == 2
        assert rl.primary_early_currency == "transmute"

    def test_desecration_abyss_strategy(self):
        """Abyss crafting: desecrate, reserve slot, reveal abyss mod.

        The key insight: REVEAL rules must appear BEFORE EXALTED rules in
        priority so the GP learns to reserve an open slot for the abyss mod
        rather than filling it with a random exalt.
        """
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
        rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR), "reroll")
        rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL), "promote")
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
        rl.add_rule(Condition.cost_spent_gte(600), Action(Currency.SCOUR), "restart")
        # Abyss path: desecrate first, then reveal before exalting
        rl.add_rule(Condition.not_desecrated(), Action(Currency.DESECRATE), "apply bone")
        rl.add_rule(Condition.is_desecrated(), Action(Currency.REVEAL), "reveal abyss mod")
        # Only exalt AFTER reveal has been used (reveal fires first due to priority)
        rl.add_rule(Condition.open_prefix_gte(1), Action(Currency.EXALTED), "exalt remaining")
        rl.add_rule(Condition.removable_gt_targets(), Action(Currency.ANNULMENT), "annul junk")
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "fallback")
        assert rl.size == 10
        # Verify the strategy serializes correctly
        conds, acts, n = rl.serialize()
        assert n == 10
        # DESECRATE and REVEAL are at the right IDs
        assert acts[5, 0] == int(Currency.DESECRATE)
        assert acts[6, 0] == int(Currency.REVEAL)

    def test_combined_abyss_and_essence(self):
        """Complex strategy combining essence + abyss crafting.

        Essence provides guaranteed prefix, abyss reveals provide abyss suffix,
        exalts fill remaining slots.
        """
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.no_essence_mod(), Action(Currency.ESSENCE_UPGRADE))
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE))
        rl.add_rule(Condition.cost_spent_gte(400), Action(Currency.SCOUR))
        # Abyss for suffix targets
        rl.add_rule(Condition.not_desecrated(), Action(Currency.DESECRATE))
        rl.add_rule(Condition.is_desecrated(), Action(Currency.REVEAL))
        # Fill remaining with exalts
        rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.EXALTED, Omen.DEXTRAL_EXALTATION))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.size == 8
        assert rl.omen_count == 1

    def test_divine_before_fracture_strategy(self):
        """Divine → Fracture workflow: max the roll value THEN lock it.

        The GP learns this sequence because:
        - Fractured mods CANNOT be divined afterward
        - Max-rolled fractured mods are worth significantly more on trade
        - Divine is cheap (8c) relative to the value uplift on a T1 mod

        The key conditions:
        - NOT_DIVINED + has_target → divine (optimize values first)
        - HAS_BEEN_DIVINED + mod_count_lte(4) → fracture (safe to lock)
        - The annul-to-isolate step happens BEFORE divine (strip garbage first)
        """
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.ALCHEMY), "start rare")
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
        rl.add_rule(Condition.cost_spent_gte(1000), Action(Currency.FAIL), "budget exceeded")
        # Phase 1: Get target mod on the item (alt-regal or chaos)
        rl.add_rule(Condition.missing_target_prefix(), Action(Currency.EXALTED), "slam for target")
        # Phase 2: Strip non-targets to isolate the good mod
        rl.add_rule(
            Condition.has_non_target_removable(),
            Action(Currency.ANNULMENT, Omen.SINISTRAL_ANNULMENT),
            "annul junk (prefix side)",
        )
        # Phase 3: Divine to max the roll BEFORE fracturing
        rl.add_rule(
            Condition.not_divined(),
            Action(Currency.DIVINE),
            "divine to max roll",
        )
        # Phase 4: Fracture the max-rolled target mod
        rl.add_rule(
            Condition.has_been_divined(),
            Action(Currency.FRACTURING),
            "lock the max roll",
        )
        # Phase 5: Fill remaining slots around the fractured mod
        rl.add_rule(
            Condition.open_prefix_gte(1),
            Action(Currency.EXALTED, Omen.SINISTRAL_EXALTATION),
            "fill prefix",
        )
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart if stuck")
        assert rl.size == 9
        # Verify divine and fracture actions serialize correctly
        _, acts, _ = rl.serialize()
        assert acts[5, 0] == int(Currency.DIVINE)
        assert acts[6, 0] == int(Currency.FRACTURING)

    def test_divine_fracture_with_isolation_trick(self):
        """The isolation trick: fracture + side-targeted annulment.

        After fracturing, the fractured mod is protected. Use sinistral/dextral
        annulment to deterministically remove the ONE remaining unwanted mod on
        the same side, because the fractured mod can't be hit.
        """
        rl = RuleList()
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE))
        rl.add_rule(Condition.rarity_is(Rarity.MAGIC), Action(Currency.SCOUR))
        rl.add_rule(Condition.has_any_target(), Action(Currency.REGAL))
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE))
        rl.add_rule(Condition.cost_spent_gte(800), Action(Currency.SCOUR))
        # Divine before fracture
        rl.add_rule(Condition.not_divined(), Action(Currency.DIVINE))
        # Fracture the target
        rl.add_rule(Condition.has_been_divined(), Action(Currency.FRACTURING))
        # Isolation trick: after fracture, the fractured mod is safe,
        # so side-targeted annul removes garbage deterministically
        rl.add_rule(
            Condition.has_fractured_mod(),
            Action(Currency.ANNULMENT, Omen.DEXTRAL_ANNULMENT),
            "isolate: remove suffix junk (fracture protects the good one)",
        )
        # Fill with exalts
        rl.add_rule(Condition.open_suffix_gte(1), Action(Currency.EXALTED))
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR))
        assert rl.size == 10
        assert rl.omen_count == 1  # the dextral annulment
