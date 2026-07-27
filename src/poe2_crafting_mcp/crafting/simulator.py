"""
Crafting simulator — state machine for PoE2 crafting operations.

Models item state, mod pool dynamics, and all currency operations.
Calculates exact probabilities and expected costs for crafting targets.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModInstance:
    """A single modifier on an item."""
    family: str          # mod group (e.g. "IncreasedLife") — only one per family
    affix_type: str      # "prefix" or "suffix"
    tier: int            # tier number within family (1=best)
    req_level: int       # ilvl required to roll this tier
    weight: int          # spawn weight (DropChance)
    stat_text: str       # human-readable stat
    fractured: bool = False

    def __repr__(self) -> str:
        frac = " [F]" if self.fractured else ""
        return f"<{self.affix_type[0].upper()} T{self.tier} {self.family}{frac}>"


@dataclass
class ItemState:
    """Current state of an item being crafted."""
    item_class: str      # poe2db slug (e.g. "Gloves_int")
    ilvl: int
    rarity: str = "Normal"  # Normal/Magic/Rare
    mods: list[ModInstance] = field(default_factory=list)
    corrupted: bool = False

    @property
    def prefixes(self) -> list[ModInstance]:
        return [m for m in self.mods if m.affix_type == "prefix"]

    @property
    def suffixes(self) -> list[ModInstance]:
        return [m for m in self.mods if m.affix_type == "suffix"]

    @property
    def max_prefixes(self) -> int:
        if self.rarity == "Rare":
            return 3
        elif self.rarity == "Magic":
            return 1
        return 0

    @property
    def max_suffixes(self) -> int:
        if self.rarity == "Rare":
            return 3
        elif self.rarity == "Magic":
            return 1
        return 0

    @property
    def open_prefixes(self) -> int:
        return max(0, self.max_prefixes - len(self.prefixes))

    @property
    def open_suffixes(self) -> int:
        return max(0, self.max_suffixes - len(self.suffixes))

    @property
    def open_affixes(self) -> int:
        return self.open_prefixes + self.open_suffixes

    @property
    def families_on_item(self) -> set[str]:
        return {m.family for m in self.mods}

    @property
    def removable_mods(self) -> list[ModInstance]:
        """Mods that can be removed (non-fractured)."""
        return [m for m in self.mods if not m.fractured]

    def copy(self) -> "ItemState":
        """Deep copy for simulation."""
        return ItemState(
            item_class=self.item_class,
            ilvl=self.ilvl,
            rarity=self.rarity,
            mods=[ModInstance(**m.__dict__) for m in self.mods],
            corrupted=self.corrupted,
        )


# ── Currency Definitions ──────────────────────────────────────────────────────

CURRENCIES: dict[str, dict[str, Any]] = {
    # Basic
    "transmute":         {"op": "add", "qty": 1, "min_lv": 0,  "to_rarity": "Magic", "from_rarity": ["Normal"]},
    "augment":           {"op": "add", "qty": 1, "min_lv": 0,  "from_rarity": ["Magic"]},
    "regal":             {"op": "add", "qty": 1, "min_lv": 0,  "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "alchemy":           {"op": "reroll", "qty": 4, "min_lv": 0, "to_rarity": "Rare", "from_rarity": ["Normal"]},
    "chaos":             {"op": "del_add", "qty": 1, "min_lv": 0, "from_rarity": ["Rare"]},
    "exalted":           {"op": "add", "qty": 1, "min_lv": 0,  "from_rarity": ["Rare"]},
    "annulment":         {"op": "del", "qty": 1, "min_lv": 0,  "from_rarity": ["Magic", "Rare"]},
    "divine":            {"op": "divine", "min_lv": 0, "from_rarity": ["Magic", "Rare"]},
    "fracturing":        {"op": "fracture", "min_lv": 0, "from_rarity": ["Rare"], "min_mods": 4},
    # Greater
    "greater_transmute": {"op": "add", "qty": 1, "min_lv": 44, "to_rarity": "Magic", "from_rarity": ["Normal"]},
    "greater_augment":   {"op": "add", "qty": 1, "min_lv": 44, "from_rarity": ["Magic"]},
    "greater_regal":     {"op": "add", "qty": 1, "min_lv": 35, "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "greater_chaos":     {"op": "del_add", "qty": 1, "min_lv": 35, "from_rarity": ["Rare"]},
    "greater_exalted":   {"op": "add", "qty": 1, "min_lv": 35, "from_rarity": ["Rare"]},
    # Perfect
    "perfect_transmute": {"op": "add", "qty": 1, "min_lv": 70, "to_rarity": "Magic", "from_rarity": ["Normal"]},
    "perfect_augment":   {"op": "add", "qty": 1, "min_lv": 70, "from_rarity": ["Magic"]},
    "perfect_regal":     {"op": "add", "qty": 1, "min_lv": 50, "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "perfect_chaos":     {"op": "del_add", "qty": 1, "min_lv": 50, "from_rarity": ["Rare"]},
    "perfect_exalted":   {"op": "add", "qty": 1, "min_lv": 50, "from_rarity": ["Rare"]},
}

# Omen gentype_only: 1=prefix, 2=suffix
OMENS: dict[str, dict[str, Any]] = {
    "sinistral_exaltation": {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "gentype_only": 1},
    "dextral_exaltation":   {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "gentype_only": 2},
    "sinistral_coronation": {"applies_to": ["regal", "greater_regal", "perfect_regal"], "gentype_only": 1},
    "dextral_coronation":   {"applies_to": ["regal", "greater_regal", "perfect_regal"], "gentype_only": 2},
    "sinistral_erasure":    {"applies_to": ["chaos", "greater_chaos", "perfect_chaos"], "del_gentype_only": 1},
    "dextral_erasure":      {"applies_to": ["chaos", "greater_chaos", "perfect_chaos"], "del_gentype_only": 2},
    "sinistral_annulment":  {"applies_to": ["annulment"], "del_gentype_only": 1},
    "dextral_annulment":    {"applies_to": ["annulment"], "del_gentype_only": 2},
    "sinistral_alchemy":    {"applies_to": ["alchemy"], "gentype_only": 1},  # maximize prefixes
    "dextral_alchemy":      {"applies_to": ["alchemy"], "gentype_only": 2},  # maximize suffixes
}


class CraftingSimulator:
    """
    Crafting state machine with probability calculation.

    Tracks item state, applies currency operations, and calculates
    exact probabilities for hitting target mods.
    """

    def __init__(self, item_class: str, ilvl: int, mod_pool: dict):
        """
        Args:
            item_class: poe2db item class (e.g. "Gloves_int")
            ilvl: item level
            mod_pool: result from PriceDatabase.get_craftable_mods()
                      Must include 'prefixes' and 'suffixes' with tier data.
        """
        self.item_class = item_class
        self.ilvl = ilvl
        self.item = ItemState(item_class=item_class, ilvl=ilvl, rarity="Rare")

        # Flatten mod pool into a list of all tiers
        self._all_mods: list[dict] = []
        for group in mod_pool.get('prefixes', []):
            for tier_idx, tier in enumerate(group['tiers']):
                self._all_mods.append({
                    'family': group['family'],
                    'affix_type': 'prefix',
                    'tier': tier_idx + 1,
                    'req_level': tier['req_level'],
                    'weight': tier['weight'],
                    'stat_text': tier['stat_text'],
                })
        for group in mod_pool.get('suffixes', []):
            for tier_idx, tier in enumerate(group['tiers']):
                self._all_mods.append({
                    'family': group['family'],
                    'affix_type': 'suffix',
                    'tier': tier_idx + 1,
                    'req_level': tier['req_level'],
                    'weight': tier['weight'],
                    'stat_text': tier['stat_text'],
                })

    def get_available_pool(
        self,
        min_mod_level: int = 0,
        gentype_only: int = 0,
        item: ItemState | None = None,
    ) -> list[dict]:
        """Get mods available for rolling given current item state.

        Applies all filtering:
        - ilvl cap
        - min_mod_level (Greater/Perfect currencies)
        - Family blocking (mods already on item excluded)
        - Slot limits (full prefix/suffix excluded)
        - Omen gentype targeting
        """
        item = item or self.item
        blocked_families = item.families_on_item
        prefixes_full = item.open_prefixes == 0
        suffixes_full = item.open_suffixes == 0

        available = []
        for mod in self._all_mods:
            if mod['req_level'] > self.ilvl:
                continue
            if mod['req_level'] < min_mod_level:
                continue
            if mod['family'] in blocked_families:
                continue
            if mod['affix_type'] == 'prefix' and prefixes_full:
                continue
            if mod['affix_type'] == 'suffix' and suffixes_full:
                continue
            if gentype_only == 1 and mod['affix_type'] != 'prefix':
                continue
            if gentype_only == 2 and mod['affix_type'] != 'suffix':
                continue
            available.append(mod)
        return available

    def probability_of(
        self,
        target_family: str,
        currency: str = "exalted",
        omen: str = "",
        target_tier: int = 0,
    ) -> dict:
        """Calculate probability of hitting a target mod with given currency.

        Args:
            target_family: mod family to target (e.g. "IncreasedLife")
            currency: currency key (e.g. "exalted", "greater_transmute")
            omen: optional omen key (e.g. "sinistral_exaltation")
            target_tier: specific tier (0 = any tier in family)

        Returns:
            dict with: probability, target_weight, total_weight,
                       expected_attempts, available_pool_size
        """
        cur = CURRENCIES.get(currency)
        if not cur:
            return {"error": f"Unknown currency: {currency}"}

        min_lv = cur.get("min_lv", 0)
        gentype_only = 0
        if omen:
            omen_def = OMENS.get(omen, {})
            gentype_only = omen_def.get("gentype_only", 0)

        pool = self.get_available_pool(min_mod_level=min_lv, gentype_only=gentype_only)

        if not pool:
            return {"probability": 0, "target_weight": 0, "total_weight": 0,
                    "expected_attempts": float('inf'), "available_pool_size": 0}

        total_weight = sum(m['weight'] for m in pool)

        # Find target mods in pool
        if target_tier > 0:
            target_mods = [m for m in pool
                           if m['family'] == target_family and m['tier'] == target_tier]
        else:
            target_mods = [m for m in pool if m['family'] == target_family]

        target_weight = sum(m['weight'] for m in target_mods)

        if target_weight == 0:
            return {"probability": 0, "target_weight": 0, "total_weight": total_weight,
                    "expected_attempts": float('inf'), "available_pool_size": len(pool),
                    "note": f"'{target_family}' not in available pool (blocked or wrong ilvl?)"}

        prob = target_weight / total_weight
        expected = 1.0 / prob if prob > 0 else float('inf')

        return {
            "probability": prob,
            "probability_pct": round(prob * 100, 2),
            "target_weight": target_weight,
            "total_weight": total_weight,
            "expected_attempts": round(expected, 1),
            "available_pool_size": len(pool),
            "target_tiers_in_pool": len(target_mods),
        }

    def estimate_cost(
        self,
        target_family: str,
        currency: str = "exalted",
        omen: str = "",
        target_tier: int = 0,
        currency_price: float = 1.0,
        omen_price: float = 0.0,
    ) -> dict:
        """Estimate expected cost to hit a target mod.

        Args:
            target_family: mod family to target
            currency: currency key
            omen: optional omen
            target_tier: 0 = any tier, N = specific tier
            currency_price: price per use in chaos equivalent
            omen_price: price of omen (one-time cost per attempt if used)

        Returns:
            dict with probability info + expected_cost, cost_per_attempt
        """
        prob = self.probability_of(target_family, currency, omen, target_tier)
        if prob.get("error"):
            return prob

        cost_per_attempt = currency_price + omen_price
        expected_cost = prob["expected_attempts"] * cost_per_attempt

        return {
            **prob,
            "currency": currency,
            "omen": omen or None,
            "currency_price": currency_price,
            "omen_price": omen_price,
            "cost_per_attempt": cost_per_attempt,
            "expected_cost": round(expected_cost, 1),
        }

    def compare_methods(
        self,
        target_family: str,
        target_tier: int = 0,
        methods: list[dict] | None = None,
        prices: dict[str, float] | None = None,
    ) -> list[dict]:
        """Compare multiple crafting methods for hitting a target.

        Args:
            target_family: mod family to target
            target_tier: 0 = any tier, N = specific tier
            methods: list of {"currency": str, "omen": str, "price": float, "omen_price": float}
                     If None, uses default methods with live or fallback prices.
            prices: dict of currency_key → chaos_value. If provided, overrides defaults.

        Returns:
            List of cost estimates sorted by expected_cost (cheapest first).
        """
        # Default prices (fallback if no live data)
        default_prices: dict[str, float] = {
            "transmute": 0.01,
            "augment": 0.02,
            "regal": 0.5,
            "alchemy": 0.3,
            "chaos": 1.0,
            "exalted": 5.0,
            "annulment": 8.0,
            "divine": 50.0,
            "greater_transmute": 0.1,
            "greater_augment": 0.2,
            "greater_regal": 2.0,
            "greater_chaos": 3.0,
            "greater_exalted": 15.0,
            "perfect_transmute": 2.0,
            "perfect_augment": 4.0,
            "perfect_regal": 10.0,
            "perfect_chaos": 15.0,
            "perfect_exalted": 50.0,
        }
        if prices:
            default_prices.update(prices)

        if methods is None:
            # Build default comparison set from all currencies that do "add" or "del_add"
            methods = []
            for key, cur in CURRENCIES.items():
                if cur["op"] in ("add", "del_add"):
                    methods.append({
                        "currency": key,
                        "price": default_prices.get(key, 1.0),
                    })

        results = []
        for m in methods:
            est = self.estimate_cost(
                target_family=target_family,
                currency=m.get("currency", "exalted"),
                omen=m.get("omen", ""),
                target_tier=target_tier,
                currency_price=m.get("price", default_prices.get(m.get("currency", ""), 1.0)),
                omen_price=m.get("omen_price", 0.0),
            )
            if not est.get("error") and est.get("probability", 0) > 0:
                results.append(est)

        results.sort(key=lambda r: r.get("expected_cost", float('inf')))
        return results

    def set_item_mods(self, mod_families: list[str]) -> None:
        """Set existing mods on the item (for blocked-pool calculations).

        Args:
            mod_families: list of family names already on the item.
                          These will be excluded from the rolling pool.
        """
        self.item.mods = []
        for family in mod_families:
            # Find this family in our pool to determine its affix type
            affix_type = "prefix"  # default
            for mod in self._all_mods:
                if mod['family'] == family:
                    affix_type = mod['affix_type']
                    break
            self.item.mods.append(ModInstance(
                family=family,
                affix_type=affix_type,
                tier=1,
                req_level=1,
                weight=0,
                stat_text=f"(existing: {family})",
            ))

    def set_item_rarity(self, rarity: str) -> None:
        """Set item rarity (affects max prefix/suffix slots)."""
        self.item.rarity = rarity

    def roll_mod(self, min_mod_level: int = 0, gentype_only: int = 0) -> ModInstance | None:
        """Roll a random mod from the available pool (for simulation)."""
        pool = self.get_available_pool(min_mod_level=min_mod_level, gentype_only=gentype_only)
        if not pool:
            return None

        total = sum(m['weight'] for m in pool)
        roll = random.randint(1, total)
        cumulative = 0
        for mod in pool:
            cumulative += mod['weight']
            if roll <= cumulative:
                return ModInstance(
                    family=mod['family'],
                    affix_type=mod['affix_type'],
                    tier=mod['tier'],
                    req_level=mod['req_level'],
                    weight=mod['weight'],
                    stat_text=mod['stat_text'],
                )
        return None  # shouldn't reach here

    def apply_currency(self, currency: str, omen: str = "") -> ItemState:
        """Apply a currency to the item, mutating state. Returns new state."""
        cur = CURRENCIES.get(currency)
        if not cur:
            raise ValueError(f"Unknown currency: {currency}")

        op = cur["op"]
        min_lv = cur.get("min_lv", 0)
        gentype_only = 0
        del_gentype_only = 0

        if omen:
            omen_def = OMENS.get(omen, {})
            gentype_only = omen_def.get("gentype_only", 0)
            del_gentype_only = omen_def.get("del_gentype_only", 0)

        # Rarity change
        if "to_rarity" in cur:
            self.item.rarity = cur["to_rarity"]

        if op == "add":
            for _ in range(cur.get("qty", 1)):
                mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
                if mod:
                    self.item.mods.append(mod)

        elif op == "del_add":
            # Remove step
            removable = self.item.removable_mods
            if del_gentype_only == 1:
                removable = [m for m in removable if m.affix_type == "prefix"]
            elif del_gentype_only == 2:
                removable = [m for m in removable if m.affix_type == "suffix"]
            if removable:
                to_remove = random.choice(removable)
                self.item.mods.remove(to_remove)
            # Add step
            mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
            if mod:
                self.item.mods.append(mod)

        elif op == "del":
            removable = self.item.removable_mods
            if del_gentype_only == 1:
                removable = [m for m in removable if m.affix_type == "prefix"]
            elif del_gentype_only == 2:
                removable = [m for m in removable if m.affix_type == "suffix"]
            for _ in range(cur.get("qty", 1)):
                if removable:
                    to_remove = random.choice(removable)
                    self.item.mods.remove(to_remove)
                    removable = self.item.removable_mods

        elif op == "reroll":
            # Remove all non-fractured mods
            self.item.mods = [m for m in self.item.mods if m.fractured]
            # Add N mods
            for _ in range(cur.get("qty", 4)):
                if self.item.open_affixes > 0:
                    mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
                    if mod:
                        self.item.mods.append(mod)

        elif op == "fracture":
            non_fractured = [m for m in self.item.mods if not m.fractured]
            if non_fractured:
                chosen = random.choice(non_fractured)
                chosen.fractured = True

        elif op == "divine":
            pass  # Values reroll within tier — doesn't change mod structure

        return self.item

    def simulate_craft(
        self,
        target_family: str,
        currency: str,
        omen: str = "",
        target_tier: int = 0,
        max_attempts: int = 10000,
        n_simulations: int = 1000,
    ) -> dict:
        """Monte Carlo simulation for hitting a target mod.

        Runs n_simulations independent attempts, returns statistics.
        """
        attempts_list = []

        for _ in range(n_simulations):
            # Reset item to starting state
            sim_item = self.item.copy()
            original_mods = sim_item.mods.copy()

            attempts = 0
            hit = False
            for attempt in range(max_attempts):
                attempts += 1
                # Apply currency to sim item
                # For simplicity, reset to original state each attempt for
                # "spam" type crafting (transmute/chaos on fresh item)
                cur = CURRENCIES[currency]
                op = cur["op"]

                if op == "add":
                    # Check if target is in what we'd roll
                    pool = self.get_available_pool(
                        min_mod_level=cur.get("min_lv", 0),
                        gentype_only=OMENS.get(omen, {}).get("gentype_only", 0),
                        item=sim_item,
                    )
                    total_w = sum(m['weight'] for m in pool)
                    if total_w == 0:
                        break
                    # Roll
                    roll = random.randint(1, total_w)
                    cumul = 0
                    for mod in pool:
                        cumul += mod['weight']
                        if roll <= cumul:
                            if mod['family'] == target_family:
                                if target_tier == 0 or mod['tier'] == target_tier:
                                    hit = True
                            break
                    if hit:
                        break
                    # For spam crafting, we don't actually add the mod
                    # (we're just counting rolls until hit)

                elif op == "del_add":
                    # Chaos: remove 1, add 1 — check if the add hits
                    pool = self.get_available_pool(
                        min_mod_level=cur.get("min_lv", 0),
                        gentype_only=OMENS.get(omen, {}).get("gentype_only", 0),
                        item=sim_item,
                    )
                    total_w = sum(m['weight'] for m in pool)
                    if total_w == 0:
                        break
                    roll = random.randint(1, total_w)
                    cumul = 0
                    for mod in pool:
                        cumul += mod['weight']
                        if roll <= cumul:
                            if mod['family'] == target_family:
                                if target_tier == 0 or mod['tier'] == target_tier:
                                    hit = True
                            break
                    if hit:
                        break

                else:
                    # For other ops, just count based on probability
                    break

            attempts_list.append(attempts if hit else max_attempts)

        # Statistics
        hits = sum(1 for a in attempts_list if a < max_attempts)
        avg_attempts = sum(attempts_list) / len(attempts_list) if attempts_list else 0

        return {
            "simulations": n_simulations,
            "hits": hits,
            "hit_rate": hits / n_simulations if n_simulations else 0,
            "avg_attempts": round(avg_attempts, 1),
            "median_attempts": sorted(attempts_list)[len(attempts_list) // 2],
            "max_attempts_cap": max_attempts,
        }
