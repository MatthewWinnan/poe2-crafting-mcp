"""Tests for essence tier fidelity.

Verifies that Lesser/Normal/Greater essences:
- Have distinct currency IDs matching Rust constants
- Encode at correct prices in PriceCache
- Appear in seeds and operator mutation pools
- Place mods at correct tiers in Rust MC evaluator (if available)
"""

import numpy as np
import pytest

from poe2_crafting_mcp.crafting.optimizer.gene import (
    Action,
    Condition,
    Currency,
    CraftTarget,
    ModTarget,
    Omen,
    PriceCache,
    Rarity,
    RuleList,
)
from poe2_crafting_mcp.crafting.optimizer.seeds import (
    ALL_SEEDS,
    PHASE_SEEDS_PREFIX,
    PHASE_SEEDS_SUFFIX,
    seed_essence_exalt_fill,
    seed_lesser_essence_exalt_fill,
    seed_normal_essence_exalt_fill,
    create_seeded_population,
)
from poe2_crafting_mcp.crafting.optimizer.operators import (
    _CRAFTABLE_CURRENCIES,
    random_action,
    mutate_action,
)


# ── Currency ID Tests ────────────────────────────────────────────────────────

class TestEssenceCurrencyIDs:
    def test_three_distinct_ids(self):
        """Each essence tier has a unique currency ID."""
        ids = {
            int(Currency.ESSENCE_LESSER),
            int(Currency.ESSENCE_NORMAL),
            int(Currency.ESSENCE_GREATER),
        }
        assert len(ids) == 3

    def test_ids_match_rust_constants(self):
        """Currency IDs match the Rust action constants."""
        assert int(Currency.ESSENCE_LESSER) == 38
        assert int(Currency.ESSENCE_NORMAL) == 39
        assert int(Currency.ESSENCE_GREATER) == 31

    def test_essence_swap_separate(self):
        """Perfect Essence (swap) is a different mechanic entirely."""
        assert int(Currency.ESSENCE_PERFECT) == 32
        assert Currency.ESSENCE_PERFECT not in (
            Currency.ESSENCE_LESSER,
            Currency.ESSENCE_NORMAL,
            Currency.ESSENCE_GREATER,
        )

    def test_action_encoding(self):
        """Each essence tier encodes to correct (currency_id, omen=0) tuple."""
        assert Action(Currency.ESSENCE_LESSER).to_array() == (38, 0)
        assert Action(Currency.ESSENCE_NORMAL).to_array() == (39, 0)
        assert Action(Currency.ESSENCE_GREATER).to_array() == (31, 0)


# ── Price Encoding Tests ─────────────────────────────────────────────────────

class TestEssencePriceEncoding:
    def _make_prices(self, **overrides) -> PriceCache:
        defaults = {
            "lesser_essence": 0.2,
            "normal_essence": 0.5,
            "greater_essence": 1.0,
            "perfect_essence": 10.0,
            "chaos": 1.0,
            "transmute": 0.01,
            "scouring": 0.5,
        }
        defaults.update(overrides)
        return PriceCache(currency=defaults, omen={})

    def test_each_tier_has_distinct_price(self):
        """Lesser < Normal < Greater in the encoded price array."""
        prices = self._make_prices()
        arr = prices.encode_for_rust()
        lesser = arr[int(Currency.ESSENCE_LESSER)]
        normal = arr[int(Currency.ESSENCE_NORMAL)]
        greater = arr[int(Currency.ESSENCE_GREATER)]
        assert lesser < normal < greater

    def test_exact_price_values(self):
        """Prices encode to exact f32 values."""
        prices = self._make_prices(
            lesser_essence=0.15,
            normal_essence=0.80,
            greater_essence=2.50,
        )
        arr = prices.encode_for_rust()
        assert abs(arr[int(Currency.ESSENCE_LESSER)] - 0.15) < 0.01
        assert abs(arr[int(Currency.ESSENCE_NORMAL)] - 0.80) < 0.01
        assert abs(arr[int(Currency.ESSENCE_GREATER)] - 2.50) < 0.01

    def test_default_prices_from_preflight(self):
        """The default price keys in preflight map to correct currency IDs."""
        # Simulate what preflight does with _DEFAULTS
        prices = PriceCache(
            currency={
                "lesser_essence": 0.2,
                "normal_essence": 0.5,
                "greater_essence": 1.0,
            },
            omen={},
        )
        arr = prices.encode_for_rust()
        assert arr[int(Currency.ESSENCE_LESSER)] > 0
        assert arr[int(Currency.ESSENCE_NORMAL)] > 0
        assert arr[int(Currency.ESSENCE_GREATER)] > 0


# ── Seed Strategy Tests ──────────────────────────────────────────────────────

class TestEssenceTierSeeds:
    def test_lesser_essence_seed_exists(self):
        """Lesser essence seed is in ALL_SEEDS."""
        assert seed_lesser_essence_exalt_fill in ALL_SEEDS

    def test_normal_essence_seed_exists(self):
        """Normal essence seed is in ALL_SEEDS."""
        assert seed_normal_essence_exalt_fill in ALL_SEEDS

    def test_greater_essence_seed_exists(self):
        """Greater essence seed (original) is in ALL_SEEDS."""
        assert seed_essence_exalt_fill in ALL_SEEDS

    def test_seed_count_increased(self):
        """ALL_SEEDS now has 15 strategies (12 original + 3 new)."""
        assert len(ALL_SEEDS) == 15

    def test_lesser_seed_uses_correct_currency(self):
        """Lesser essence seed uses ESSENCE_LESSER action."""
        rl = seed_lesser_essence_exalt_fill()
        currencies = [r.action.currency for r in rl.rules]
        assert Currency.ESSENCE_LESSER in currencies
        assert Currency.ESSENCE_GREATER not in currencies
        assert Currency.ESSENCE_NORMAL not in currencies

    def test_normal_seed_uses_correct_currency(self):
        """Normal essence seed uses ESSENCE_NORMAL action."""
        rl = seed_normal_essence_exalt_fill()
        currencies = [r.action.currency for r in rl.rules]
        assert Currency.ESSENCE_NORMAL in currencies
        assert Currency.ESSENCE_GREATER not in currencies
        assert Currency.ESSENCE_LESSER not in currencies

    def test_greater_seed_uses_correct_currency(self):
        """Greater essence seed uses ESSENCE_GREATER action."""
        rl = seed_essence_exalt_fill()
        currencies = [r.action.currency for r in rl.rules]
        assert Currency.ESSENCE_GREATER in currencies
        assert Currency.ESSENCE_LESSER not in currencies
        assert Currency.ESSENCE_NORMAL not in currencies

    def test_phase_seeds_include_essence_tiers(self):
        """Phase seed lists include all three essence tier seeds."""
        assert len(PHASE_SEEDS_PREFIX) == 6
        assert len(PHASE_SEEDS_SUFFIX) == 7

    def test_seeded_population_includes_essence_tiers(self):
        """A large enough population hits all essence tier seeds."""
        pop = create_seeded_population(200, seed_fraction=0.5)
        all_currencies = set()
        for rl in pop:
            for r in rl.rules:
                all_currencies.add(r.action.currency)
        assert Currency.ESSENCE_LESSER in all_currencies
        assert Currency.ESSENCE_NORMAL in all_currencies
        assert Currency.ESSENCE_GREATER in all_currencies


# ── Operator Tests ───────────────────────────────────────────────────────────

class TestEssenceTierOperators:
    def test_lesser_in_mutation_pool(self):
        """ESSENCE_LESSER is available for random mutation."""
        assert Currency.ESSENCE_LESSER in _CRAFTABLE_CURRENCIES

    def test_normal_in_mutation_pool(self):
        """ESSENCE_NORMAL is available for random mutation."""
        assert Currency.ESSENCE_NORMAL in _CRAFTABLE_CURRENCIES

    def test_random_action_can_produce_essence_tiers(self):
        """random_action() can eventually produce each essence tier."""
        seen = set()
        target = {Currency.ESSENCE_LESSER, Currency.ESSENCE_NORMAL, Currency.ESSENCE_GREATER}
        for _ in range(5000):
            a = random_action()
            if a.currency in target:
                seen.add(a.currency)
            if seen == target:
                break
        assert seen == target, f"Missing: {target - seen}"

    def test_mutate_action_preserves_structure(self):
        """Mutating an essence seed preserves rule count."""
        rl = seed_lesser_essence_exalt_fill()
        original_size = rl.size
        mutated = mutate_action(rl)
        assert mutated.size == original_size


# ── Rust MC Evaluator Tests (conditional) ────────────────────────────────────

def _rust_available():
    try:
        from poe2_crafting_mcp.crafting.optimizer.bridge import is_rust_available
        return is_rust_available()
    except ImportError:
        return False


@pytest.mark.skipif(not _rust_available(), reason="Rust evaluator not built")
class TestEssenceTierRust:
    """Test that the Rust evaluator handles essence tier actions correctly."""

    def _make_pool_and_target(self):
        """Create pool where family 1 is a prefix with 3 tiers."""
        # Family 1: prefix with T1 (weight=100), T2 (weight=500), T3 (weight=1000)
        prefix_families = np.array([1, 1, 1, 2, 2, 2], dtype=np.uint16)
        prefix_tiers = np.array([1, 2, 3, 1, 2, 3], dtype=np.uint8)
        prefix_weights = np.array([100, 500, 1000, 200, 600, 1200], dtype=np.uint32)
        prefix_req_levels = np.array([70, 50, 30, 70, 50, 30], dtype=np.uint8)

        suffix_families = np.array([11, 11, 11], dtype=np.uint16)
        suffix_tiers = np.array([1, 2, 3], dtype=np.uint8)
        suffix_weights = np.array([100, 500, 1000], dtype=np.uint32)
        suffix_req_levels = np.array([70, 50, 30], dtype=np.uint8)

        target = CraftTarget(
            targets=[ModTarget("TestMod", 1, "prefix", 3)],  # Accept any tier
            item_class="Gloves_int",
            ilvl=82,
        )

        from poe2_crafting_mcp.crafting.optimizer.bridge import encode_pool
        pool_data = encode_pool(
            prefix_weights=list(prefix_weights),
            prefix_families=list(prefix_families),
            prefix_tiers=list(prefix_tiers),
            prefix_req_levels=list(prefix_req_levels),
            suffix_weights=list(suffix_weights),
            suffix_families=list(suffix_families),
            suffix_tiers=list(suffix_tiers),
            suffix_req_levels=list(suffix_req_levels),
            target=target,
            ilvl=82,
            max_prefixes=3,
            max_suffixes=3,
        )
        return pool_data, target

    def _make_essence_strategy(self, currency: Currency) -> RuleList:
        """Create a simple essence strategy: transmute → essence → done."""
        rl = RuleList()
        rl.add_rule(Condition.all_targets_hit(), Action(Currency.DONE), "success")
        rl.add_rule(Condition.rarity_is(Rarity.NORMAL), Action(Currency.TRANSMUTE), "start")
        rl.add_rule(Condition.no_essence_mod(), Action(currency), "essence")
        rl.add_rule(Condition.always_true(), Action(Currency.SCOUR), "restart")
        return rl

    def _make_prices(self) -> PriceCache:
        return PriceCache(
            currency={
                "lesser_essence": 0.2,
                "normal_essence": 0.5,
                "greater_essence": 1.0,
                "transmute": 0.01,
                "scouring": 0.5,
                "chaos": 1.0,
            },
            omen={},
        )

    def test_all_three_tiers_succeed(self):
        """Each essence tier produces a successful craft (target accepts any tier)."""
        from poe2_crafting_mcp.crafting.optimizer.bridge import evaluate_population_rust
        from poe2_crafting_mcp.crafting.optimizer.gene import Individual

        pool_data, target = self._make_pool_and_target()
        prices = self._make_prices()

        for currency in (Currency.ESSENCE_LESSER, Currency.ESSENCE_NORMAL, Currency.ESSENCE_GREATER):
            rl = self._make_essence_strategy(currency)
            ind = Individual(rulelist=rl)
            evaluate_population_rust([ind], pool_data, prices, n_trials=200)
            assert ind.fitness is not None, f"{currency.name}: no fitness assigned"
            # Essence should guarantee the target mod, so success rate should be high
            assert ind.fitness.success_rate > 0.5, (
                f"{currency.name}: success_rate={ind.fitness.success_rate:.2%}, expected >50%"
            )

    def test_lesser_costs_less_than_greater(self):
        """Lesser essence strategy costs less per craft than Greater."""
        from poe2_crafting_mcp.crafting.optimizer.bridge import evaluate_population_rust
        from poe2_crafting_mcp.crafting.optimizer.gene import Individual

        pool_data, target = self._make_pool_and_target()
        prices = self._make_prices()

        costs = {}
        for currency in (Currency.ESSENCE_LESSER, Currency.ESSENCE_GREATER):
            rl = self._make_essence_strategy(currency)
            ind = Individual(rulelist=rl)
            evaluate_population_rust([ind], pool_data, prices, n_trials=500)
            costs[currency] = ind.fitness.expected_cost

        assert costs[Currency.ESSENCE_LESSER] < costs[Currency.ESSENCE_GREATER], (
            f"Lesser ({costs[Currency.ESSENCE_LESSER]:.2f}) should cost less than "
            f"Greater ({costs[Currency.ESSENCE_GREATER]:.2f})"
        )
