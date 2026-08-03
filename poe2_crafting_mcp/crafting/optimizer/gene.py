"""Core data structures for the crafting optimizer.

Defines Rule, RuleList, Condition, Action, CraftTarget, Fitness, Individual,
and PriceCache — the genome representation for the GP engine. Rule-lists are
serialized to flat numpy arrays for the Rust MC evaluation loop.

References:
- PPL-ST (Bishop et al., 2023): Pittsburgh LCS for explainable RL
- BASIL (Shahnazari et al., 2025): QD-evolved symbolic rule policies
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Self

import numpy as np


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_RULES = 20
MAX_STEPS = 500


# ── Rarity ────────────────────────────────────────────────────────────────────

class Rarity(IntEnum):
    NORMAL = 0
    MAGIC = 1
    RARE = 2


# ── Predicate IDs (must match crates/poe2-optimizer/src/conditions.rs) ────────

class Predicate(IntEnum):
    """Condition predicates — evaluated against item state in Rust."""
    RARITY_IS = 0
    HAS_ANY_TARGET = 1
    HAS_TARGET = 2
    ALL_TARGETS_HIT = 3
    ALL_TARGETS_AT_TIER = 4
    MISSING_TARGET_PREFIX = 5
    MISSING_TARGET_SUFFIX = 6
    HAS_NON_TARGET_REMOVABLE = 7
    TARGETS_ON_ITEM_GTE = 8
    OPEN_PREFIX_GTE = 9
    OPEN_SUFFIX_GTE = 10
    MOD_COUNT_GTE = 11
    MOD_COUNT_LTE = 12
    COST_SPENT_GTE = 13
    STEP_COUNT_GTE = 14
    REMOVABLE_GT_TARGETS = 15
    PREFIX_FULL_NO_TARGET_PREFIX = 16
    SUFFIX_FULL_NO_TARGET_SUFFIX = 17
    # Advanced state checks
    HAS_FRACTURED_MOD = 18       # item has at least one fractured mod
    HAS_ESSENCE_MOD = 19         # item has an essence-guaranteed mod (only 1 allowed)
    NO_ESSENCE_MOD = 20          # item does NOT have an essence mod (can apply essence)
    FRACTURED_IS_TARGET = 21     # the fractured mod is one of our targets
    # Abyss / desecration state
    IS_DESECRATED = 22           # item is in desecrated state (can reveal)
    NOT_DESECRATED = 23          # item is NOT desecrated (can desecrate)
    # Divine / fracture workflow
    HAS_BEEN_DIVINED = 24        # item has been divined (values optimized, ready to fracture)
    NOT_DIVINED = 25             # item has NOT been divined (should divine before fracturing)
    ALWAYS_TRUE = 255


# ── Currency IDs (must match crates/poe2-optimizer/src/actions.rs) ─────────────

class Currency(IntEnum):
    """Crafting currency actions."""
    # Terminal
    DONE = 0
    FAIL = 1
    # Restart
    SCOUR = 2
    BUY_BASE = 3
    BUY_MAGIC = 4
    BUY_FRACTURED = 5
    REFORGE = 6
    # Basic crafting
    TRANSMUTE = 10
    GREATER_TRANSMUTE = 11
    PERFECT_TRANSMUTE = 12
    ALTERATION = 13
    AUGMENT = 14
    GREATER_AUGMENT = 15
    PERFECT_AUGMENT = 16
    REGAL = 17
    GREATER_REGAL = 18
    PERFECT_REGAL = 19
    EXALTED = 20
    GREATER_EXALTED = 21
    PERFECT_EXALTED = 22
    ANNULMENT = 23
    CHAOS = 24
    GREATER_CHAOS = 25
    PERFECT_CHAOS = 26
    ALCHEMY = 27
    # Advanced crafting
    FRACTURING = 30
    ESSENCE_UPGRADE = 31   # Greater Essence: Magic → Rare + guaranteed mod
    ESSENCE_SWAP = 32      # Perfect Essence: remove 1, add 1 guaranteed
    DIVINE = 33            # Reroll mod values within tier ranges
    VAAL = 34              # Corruption (terminal — no further mods)
    # Abyss crafting (desecration / Well of Souls)
    DESECRATE = 35         # Apply bone — item enters desecrated state
    REVEAL = 36            # At Well of Souls — place an abyss mod (uses open slot)


class Omen(IntEnum):
    """Omen modifiers applied alongside a currency."""
    NONE = 0
    SINISTRAL_EXALTATION = 1   # force prefix on exalt
    DEXTRAL_EXALTATION = 2     # force suffix on exalt
    GREATER_EXALTATION = 3     # add 2 mods on exalt
    SINISTRAL_ANNULMENT = 4    # remove prefix only
    DEXTRAL_ANNULMENT = 5      # remove suffix only
    SINISTRAL_CORONATION = 6   # regal adds prefix
    DEXTRAL_CORONATION = 7     # regal adds suffix
    WHITTLING = 8              # chaos targets lowest-req mod for removal
    ABYSSAL_ECHOES = 9         # re-roll desecration reveal options
    SINISTRAL_NECROMANCY = 10  # desecration reveal targets prefixes only
    DEXTRAL_NECROMANCY = 11    # desecration reveal targets suffixes only


# ── Condition ─────────────────────────────────────────────────────────────────

def _float_to_u16_pair(value: float) -> tuple[int, int]:
    """Encode a float as two u16s (high/low bits of f32)."""
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return (bits >> 16) & 0xFFFF, bits & 0xFFFF


def _u16_pair_to_float(high: int, low: int) -> float:
    """Decode two u16s back to a float."""
    bits = (high << 16) | low
    return struct.unpack("<f", struct.pack("<I", bits))[0]


@dataclass(frozen=True, slots=True)
class Condition:
    """A single testable predicate about the item state.

    Serialized as 3 × u16 for the Rust evaluator: (predicate, arg1, arg2).
    """
    predicate: Predicate
    arg1: int = 0
    arg2: int = 0

    # ── Factory methods ──

    @classmethod
    def rarity_is(cls, rarity: Rarity) -> Self:
        return cls(Predicate.RARITY_IS, int(rarity))

    @classmethod
    def has_any_target(cls) -> Self:
        return cls(Predicate.HAS_ANY_TARGET)

    @classmethod
    def has_target(cls, family_idx: int) -> Self:
        return cls(Predicate.HAS_TARGET, family_idx)

    @classmethod
    def all_targets_hit(cls) -> Self:
        return cls(Predicate.ALL_TARGETS_HIT)

    @classmethod
    def all_targets_at_tier(cls) -> Self:
        return cls(Predicate.ALL_TARGETS_AT_TIER)

    @classmethod
    def missing_target_prefix(cls) -> Self:
        return cls(Predicate.MISSING_TARGET_PREFIX)

    @classmethod
    def missing_target_suffix(cls) -> Self:
        return cls(Predicate.MISSING_TARGET_SUFFIX)

    @classmethod
    def has_non_target_removable(cls) -> Self:
        return cls(Predicate.HAS_NON_TARGET_REMOVABLE)

    @classmethod
    def targets_on_item_gte(cls, n: int) -> Self:
        return cls(Predicate.TARGETS_ON_ITEM_GTE, n)

    @classmethod
    def open_prefix_gte(cls, n: int) -> Self:
        return cls(Predicate.OPEN_PREFIX_GTE, n)

    @classmethod
    def open_suffix_gte(cls, n: int) -> Self:
        return cls(Predicate.OPEN_SUFFIX_GTE, n)

    @classmethod
    def mod_count_gte(cls, n: int) -> Self:
        return cls(Predicate.MOD_COUNT_GTE, n)

    @classmethod
    def mod_count_lte(cls, n: int) -> Self:
        return cls(Predicate.MOD_COUNT_LTE, n)

    @classmethod
    def cost_spent_gte(cls, threshold: float) -> Self:
        high, low = _float_to_u16_pair(threshold)
        return cls(Predicate.COST_SPENT_GTE, high, low)

    @classmethod
    def step_count_gte(cls, n: int) -> Self:
        return cls(Predicate.STEP_COUNT_GTE, n)

    @classmethod
    def removable_gt_targets(cls) -> Self:
        return cls(Predicate.REMOVABLE_GT_TARGETS)

    @classmethod
    def prefix_full_no_target_prefix(cls) -> Self:
        return cls(Predicate.PREFIX_FULL_NO_TARGET_PREFIX)

    @classmethod
    def suffix_full_no_target_suffix(cls) -> Self:
        return cls(Predicate.SUFFIX_FULL_NO_TARGET_SUFFIX)

    @classmethod
    def always_true(cls) -> Self:
        return cls(Predicate.ALWAYS_TRUE)

    @classmethod
    def has_fractured_mod(cls) -> Self:
        return cls(Predicate.HAS_FRACTURED_MOD)

    @classmethod
    def has_essence_mod(cls) -> Self:
        return cls(Predicate.HAS_ESSENCE_MOD)

    @classmethod
    def no_essence_mod(cls) -> Self:
        return cls(Predicate.NO_ESSENCE_MOD)

    @classmethod
    def fractured_is_target(cls) -> Self:
        return cls(Predicate.FRACTURED_IS_TARGET)

    @classmethod
    def is_desecrated(cls) -> Self:
        return cls(Predicate.IS_DESECRATED)

    @classmethod
    def not_desecrated(cls) -> Self:
        return cls(Predicate.NOT_DESECRATED)

    @classmethod
    def has_been_divined(cls) -> Self:
        return cls(Predicate.HAS_BEEN_DIVINED)

    @classmethod
    def not_divined(cls) -> Self:
        return cls(Predicate.NOT_DIVINED)

    def to_array(self) -> tuple[int, int, int]:
        """Serialize for Rust: (predicate_id, arg1, arg2)."""
        return (int(self.predicate), self.arg1, self.arg2)

    @property
    def cost_threshold(self) -> float | None:
        """If this is a COST_SPENT_GTE condition, return the threshold."""
        if self.predicate == Predicate.COST_SPENT_GTE:
            return _u16_pair_to_float(self.arg1, self.arg2)
        return None

    def __str__(self) -> str:
        if self.predicate == Predicate.ALWAYS_TRUE:
            return "DEFAULT"
        if self.predicate == Predicate.RARITY_IS:
            return f"rarity_is({Rarity(self.arg1).name})"
        if self.predicate == Predicate.COST_SPENT_GTE:
            return f"cost_spent_gte({self.cost_threshold:.0f})"
        name = self.predicate.name.lower()
        if self.arg1 == 0 and self.arg2 == 0:
            return name
        if self.arg2 == 0:
            return f"{name}({self.arg1})"
        return f"{name}({self.arg1}, {self.arg2})"


# ── Action ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Action:
    """What currency to apply when a rule fires.

    Serialized as 2 × u16 for the Rust evaluator: (currency_id, omen_id).
    """
    currency: Currency
    omen: Omen = Omen.NONE

    def to_array(self) -> tuple[int, int]:
        return (int(self.currency), int(self.omen))

    @property
    def is_terminal(self) -> bool:
        return self.currency in (Currency.DONE, Currency.FAIL)

    @property
    def is_restart(self) -> bool:
        return self.currency in (Currency.SCOUR, Currency.BUY_BASE,
                                 Currency.BUY_MAGIC, Currency.BUY_FRACTURED,
                                 Currency.REFORGE)

    @property
    def has_omen(self) -> bool:
        return self.omen != Omen.NONE

    def __str__(self) -> str:
        name = self.currency.name.lower()
        if self.omen != Omen.NONE:
            return f"{name} + {self.omen.name.lower()}"
        return name


# ── Rule ──────────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class Rule:
    """A single IF-THEN rule in the crafting strategy."""
    condition: Condition
    action: Action
    label: str = ""

    def __str__(self) -> str:
        lbl = f"  ({self.label})" if self.label else ""
        return f"IF {self.condition} THEN {self.action}{lbl}"


# ── RuleList (the genome) ─────────────────────────────────────────────────────

@dataclass
class RuleList:
    """An ordered list of rules — the genome of one individual in the GP.

    Evaluated top-to-bottom by the Rust MC engine. First matching rule fires.
    """
    rules: list[Rule] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.rules)

    def add_rule(self, condition: Condition, action: Action, label: str = "") -> None:
        if len(self.rules) >= MAX_RULES:
            return
        self.rules.append(Rule(condition, action, label))

    def remove_rule(self, idx: int) -> None:
        if len(self.rules) <= 3:
            return
        if 0 <= idx < len(self.rules):
            self.rules.pop(idx)

    def insert_rule(self, idx: int, rule: Rule) -> None:
        if len(self.rules) >= MAX_RULES:
            return
        idx = max(0, min(idx, len(self.rules)))
        self.rules.insert(idx, rule)

    def swap_rules(self, i: int, j: int) -> None:
        if 0 <= i < len(self.rules) and 0 <= j < len(self.rules):
            self.rules[i], self.rules[j] = self.rules[j], self.rules[i]

    def serialize(self) -> tuple[np.ndarray, np.ndarray, int]:
        """Serialize to flat arrays for the Rust evaluator.

        Returns:
            conditions: (MAX_RULES, 3) uint16 array
            actions: (MAX_RULES, 2) uint16 array
            n_rules: actual rule count
        """
        conditions = np.zeros((MAX_RULES, 3), dtype=np.uint16)
        actions = np.zeros((MAX_RULES, 2), dtype=np.uint16)
        for i, rule in enumerate(self.rules):
            conditions[i] = rule.condition.to_array()
            actions[i] = rule.action.to_array()
        return conditions, actions, len(self.rules)

    def copy(self) -> RuleList:
        return RuleList(rules=[Rule(r.condition, r.action, r.label) for r in self.rules])

    # ── Behavioral descriptor (for QD archive) ──

    @property
    def primary_early_currency(self) -> str:
        """Which currency dominates the first few rules (for QD bucketing)."""
        early_currencies = []
        for rule in self.rules[:5]:
            c = rule.action.currency
            if c in (Currency.TRANSMUTE, Currency.GREATER_TRANSMUTE,
                     Currency.PERFECT_TRANSMUTE, Currency.ALTERATION):
                early_currencies.append("transmute")
            elif c == Currency.ALCHEMY:
                early_currencies.append("alchemy")
            elif c in (Currency.CHAOS, Currency.GREATER_CHAOS, Currency.PERFECT_CHAOS):
                early_currencies.append("chaos")
        if not early_currencies:
            return "alchemy"
        # Most common early currency
        from collections import Counter
        return Counter(early_currencies).most_common(1)[0][0]

    @property
    def restart_threshold(self) -> float:
        """Cost threshold of the first SCOUR/restart rule (for QD bucketing)."""
        for rule in self.rules:
            if rule.action.is_restart and rule.condition.predicate == Predicate.COST_SPENT_GTE:
                t = rule.condition.cost_threshold
                if t is not None:
                    return t
        return 999.0  # No explicit restart threshold

    @property
    def omen_count(self) -> int:
        """Number of rules using omens (for QD bucketing)."""
        return sum(1 for r in self.rules if r.action.has_omen)

    def __str__(self) -> str:
        lines = []
        for i, rule in enumerate(self.rules, 1):
            lines.append(f"  {i:2d}. {rule}")
        return "\n".join(lines)


# ── CraftTarget ───────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ModTarget:
    """A single target mod specification."""
    family: str        # mod family name (e.g. "IncreasedLife")
    family_id: int     # numeric ID used in pool/Rust arrays
    affix_type: str    # "prefix" or "suffix"
    max_tier: int      # highest acceptable tier (1=T1 only, 3=T1-T3)


@dataclass
class CraftTarget:
    """What the optimizer is trying to achieve on the item."""
    targets: list[ModTarget] = field(default_factory=list)
    item_class: str = ""
    ilvl: int = 82

    @property
    def prefix_targets(self) -> list[ModTarget]:
        return [t for t in self.targets if t.affix_type == "prefix"]

    @property
    def suffix_targets(self) -> list[ModTarget]:
        return [t for t in self.targets if t.affix_type == "suffix"]

    @property
    def family_ids(self) -> list[int]:
        return [t.family_id for t in self.targets]

    @property
    def prefix_family_ids(self) -> list[int]:
        return [t.family_id for t in self.prefix_targets]

    @property
    def suffix_family_ids(self) -> list[int]:
        return [t.family_id for t in self.suffix_targets]

    @property
    def max_tiers(self) -> list[int]:
        return [t.max_tier for t in self.targets]

    def __str__(self) -> str:
        parts = [f"T{t.max_tier} {t.family} ({t.affix_type[0]})" for t in self.targets]
        return f"{self.item_class} ilvl{self.ilvl}: {', '.join(parts)}"


# ── Fitness ───────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class Fitness:
    """Result of evaluating a RuleList over N Monte Carlo trials.

    Pareto objectives (all minimized):
      - expected_cost: mean cost of successful crafts
      - failure_rate: 1 - success_rate
      - cost_p90: 90th percentile cost (consistency)

    Per-rule credit (from PPL-ST):
      - fire_on_success[i]: times rule i fired in trials that ended SUCCESS
      - fire_on_failure[i]: times rule i fired in trials that ended FAIL
    """
    expected_cost: float = float("inf")
    success_rate: float = 0.0
    cost_p90: float = float("inf")
    cost_median: float = float("inf")
    cost_std: float = 0.0
    expected_steps: float = 0.0
    step_median: float = 0.0
    rule_count: int = 0

    # Per-rule credit assignment (PPL-ST inspired)
    fire_on_success: list[int] = field(default_factory=list)
    fire_on_failure: list[int] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        return 1.0 - self.success_rate

    @property
    def objectives(self) -> tuple[float, float, float]:
        """The 3 Pareto objectives (all minimized)."""
        return (self.expected_cost, self.failure_rate, self.cost_p90)

    def dominates(self, other: Fitness) -> bool:
        """True if self Pareto-dominates other."""
        a = self.objectives
        b = other.objectives
        at_least_one_better = False
        for ai, bi in zip(a, b):
            if ai > bi:
                return False
            if ai < bi:
                at_least_one_better = True
        return at_least_one_better

    @property
    def is_degenerate(self) -> bool:
        """Kill condition: success < 5% or infinite cost."""
        return self.success_rate < 0.05 or self.expected_cost == float("inf")

    def rule_is_dead(self, idx: int) -> bool:
        """True if rule never fired in any trial."""
        s = self.fire_on_success[idx] if idx < len(self.fire_on_success) else 0
        f = self.fire_on_failure[idx] if idx < len(self.fire_on_failure) else 0
        return s == 0 and f == 0

    def rule_is_harmful(self, idx: int, threshold: float = 3.0) -> bool:
        """True if rule fires much more on failures than successes."""
        s = self.fire_on_success[idx] if idx < len(self.fire_on_success) else 0
        f = self.fire_on_failure[idx] if idx < len(self.fire_on_failure) else 0
        if s == 0:
            return f > 10
        return (f / max(s, 1)) > threshold

    def rule_is_key(self, idx: int, threshold: float = 3.0) -> bool:
        """True if rule fires much more on successes than failures."""
        s = self.fire_on_success[idx] if idx < len(self.fire_on_success) else 0
        f = self.fire_on_failure[idx] if idx < len(self.fire_on_failure) else 0
        if f == 0:
            return s > 10
        return (s / max(f, 1)) > threshold

    def __str__(self) -> str:
        return (
            f"cost={self.expected_cost:.1f}c | "
            f"success={self.success_rate:.0%} | "
            f"p90={self.cost_p90:.1f}c | "
            f"median={self.cost_median:.1f}c | "
            f"steps={self.expected_steps:.0f}"
        )


# ── Individual ────────────────────────────────────────────────────────────────

@dataclass
class Individual:
    """One member of the GP population: a rule-list and its evaluated fitness."""
    rulelist: RuleList
    fitness: Fitness = field(default_factory=Fitness)
    pareto_rank: int = 0
    crowding_distance: float = 0.0

    @property
    def size(self) -> int:
        return self.rulelist.size

    @property
    def evaluated(self) -> bool:
        return self.fitness.expected_cost != float("inf") or self.fitness.success_rate > 0

    def copy(self) -> Individual:
        """Deep copy (fitness reset — needs re-evaluation)."""
        return Individual(rulelist=self.rulelist.copy())

    def __str__(self) -> str:
        return f"[Rank {self.pareto_rank}] {self.fitness}\n{self.rulelist}"


# ── PriceCache ────────────────────────────────────────────────────────────────

@dataclass
class PriceCache:
    """Pre-flight price data. Fetched once, used for all MC evaluations.

    Hot (poe.ninja, instant): currency, omen, essence prices.
    Cold (trade API, ~10 calls): base item prices at various states.
    """
    # Hot cache
    currency: dict[str, float] = field(default_factory=dict)
    omen: dict[str, float] = field(default_factory=dict)
    essence: dict[str, float] = field(default_factory=dict)

    # Cold cache
    base_white: float = 1.0
    base_magic_with: dict[str, float] = field(default_factory=dict)
    base_fractured_with: dict[str, float] = field(default_factory=dict)
    trade_finished: float = float("inf")

    def encode_for_rust(self) -> np.ndarray:
        """Encode prices as flat f32 array indexed by Currency/Omen IDs.

        Layout: [currency_prices..., omen_prices...]
        Size: max_currency_id + 1 + max_omen_id + 1
        """
        max_currency_id = max(int(c) for c in Currency) + 1
        max_omen_id = max(int(o) for o in Omen) + 1
        size = max_currency_id + max_omen_id
        prices = np.zeros(size, dtype=np.float32)

        # Currency name → ID mapping
        _name_to_cid: dict[str, int] = {}
        for c in Currency:
            # Normalize: "GREATER_TRANSMUTE" → "greater_transmute"
            _name_to_cid[c.name.lower()] = int(c)
            # Also map common poe.ninja names
            _name_to_cid[c.name.lower().replace("_", " ")] = int(c)

        for name, price in self.currency.items():
            key = name.lower().replace(" ", "_")
            cid = _name_to_cid.get(key)
            if cid is not None and cid < max_currency_id:
                prices[cid] = price

        # Omen prices offset by max_currency_id
        _name_to_oid: dict[str, int] = {}
        for o in Omen:
            _name_to_oid[o.name.lower()] = int(o)
            _name_to_oid[o.name.lower().replace("_", " ")] = int(o)

        for name, price in self.omen.items():
            key = name.lower().replace(" ", "_")
            oid = _name_to_oid.get(key)
            if oid is not None:
                prices[max_currency_id + oid] = price

        # Restart costs at their currency IDs
        prices[int(Currency.SCOUR)] = self.currency.get("scouring", 0.5)
        prices[int(Currency.BUY_BASE)] = self.base_white
        # BUY_MAGIC / BUY_FRACTURED: use average of known prices
        if self.base_magic_with:
            avg_magic = sum(self.base_magic_with.values()) / len(self.base_magic_with)
            prices[int(Currency.BUY_MAGIC)] = avg_magic
        else:
            prices[int(Currency.BUY_MAGIC)] = self.base_white * 10
        if self.base_fractured_with:
            avg_frac = sum(self.base_fractured_with.values()) / len(self.base_fractured_with)
            prices[int(Currency.BUY_FRACTURED)] = avg_frac
        else:
            prices[int(Currency.BUY_FRACTURED)] = self.base_white * 50
        # Reforge: costs 2 spare bases
        prices[int(Currency.REFORGE)] = self.base_white * 2

        return prices

    @property
    def craft_vs_buy_threshold(self) -> float:
        """Price of finished item on trade (for verdict)."""
        return self.trade_finished


# ── Population Serialization ──────────────────────────────────────────────────

def serialize_population(
    population: list[Individual],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Serialize entire population for Rust batch evaluation.

    Returns:
        rules_array: (pop_size, MAX_RULES, 5) uint16
            Per rule: [predicate, arg1, arg2, currency, omen]
        rule_counts: (pop_size,) uint8
        pop_size: number of individuals
    """
    pop_size = len(population)
    rules_array = np.zeros((pop_size, MAX_RULES, 5), dtype=np.uint16)
    rule_counts = np.zeros(pop_size, dtype=np.uint8)

    for i, ind in enumerate(population):
        conds, acts, n = ind.rulelist.serialize()
        rules_array[i, :, :3] = conds
        rules_array[i, :, 3:5] = acts
        rule_counts[i] = n

    return rules_array, rule_counts, pop_size
