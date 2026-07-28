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
    desecrated: bool = False  # True if this mod came from abyss desecration

    def __repr__(self) -> str:
        frac = " [F]" if self.fractured else ""
        desc = " [D]" if self.desecrated else ""
        return f"<{self.affix_type[0].upper()} T{self.tier} {self.family}{frac}{desc}>"


@dataclass
class ItemState:
    """Current state of an item being crafted."""
    item_class: str      # poe2db slug (e.g. "Gloves_int")
    ilvl: int
    rarity: str = "Normal"  # Normal/Magic/Rare
    mods: list[ModInstance] = field(default_factory=list)
    corrupted: bool = False
    essence_mod_family: str | None = None  # tracks which family is the essence mod (one per item)
    quality: int = 0                       # 0-20 (23 max via corruption)
    sockets: list[str] = field(default_factory=list)  # names of socketed items (runes/cores/idols)
    max_sockets: int = 0                   # determined by slot type (can increase via Vaal)
    corruption_enchantment: str = ""       # Vaal enchantment stat_text (separate from mods)

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
    def open_sockets(self) -> int:
        return max(0, self.max_sockets - len(self.sockets))

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
            essence_mod_family=self.essence_mod_family,
            quality=self.quality,
            sockets=list(self.sockets),
            max_sockets=self.max_sockets,
            corruption_enchantment=self.corruption_enchantment,
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
    "scour":             {"op": "scour", "min_lv": 0, "from_rarity": ["Magic", "Rare"]},
    "alteration":        {"op": "reroll", "qty": 2, "min_lv": 0, "to_rarity": "Magic", "from_rarity": ["Magic"]},
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
    # Essences — special ops, not standard currency
    "lesser_essence":    {"op": "essence_upgrade", "min_lv": 0, "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "normal_essence":    {"op": "essence_upgrade", "min_lv": 0, "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "greater_essence":   {"op": "essence_upgrade", "min_lv": 0, "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "perfect_essence":   {"op": "essence_swap", "min_lv": 0, "from_rarity": ["Rare"]},
    # Reforging bench — 3-to-1 recycling
    # Requires 2 spare bases (reforge_stock >= 2). Consumes current item + 2 spares.
    # Output: fresh Rare with 4 random mods (same base type, lowest ilvl).
    "reforge":           {"op": "reforge", "qty": 4, "min_lv": 0, "to_rarity": "Rare", "from_rarity": ["Normal", "Magic", "Rare"]},
    # Quality currencies
    "armourers_scrap":   {"op": "quality", "qty": 5, "slot_type": "armour"},
    "blacksmiths_whetstone": {"op": "quality", "qty": 5, "slot_type": "weapon"},
    # Socket currency
    "artificer":         {"op": "add_socket"},
    # Corruption
    "vaal":              {"op": "corrupt"},
    # Architect's Orb (Atziri's Temple) — second corruption attempt
    # 50% add second enchantment, 50% destroy item
    "architect":         {"op": "architect_corrupt"},
}

# ── Max Sockets by Item Slot ──────────────────────────────────────────────────
# Normal max sockets. Vaal Orb can add +1 beyond this.

MAX_SOCKETS_BY_SLOT: dict[str, int] = {
    # Two-handed weapons: 2 sockets
    "Bow": 2, "Crossbow": 2, "Two Hand Sword": 2, "Two Hand Axe": 2,
    "Two Hand Mace": 2, "Quarterstaff": 2, "Staff": 2, "Talisman": 2,
    # Body Armour: 2 sockets
    "Body Armour": 2,
    # One-handed weapons: 1 socket
    "One Hand Sword": 1, "One Hand Axe": 1, "One Hand Mace": 1,
    "Dagger": 1, "Claw": 1, "Flail": 1, "Spear": 1,
    "Wand": 1, "Sceptre": 1,
    # Armour pieces: 1 socket
    "Helmet": 1, "Gloves": 1, "Boots": 1,
    # Off-hand: 1 socket
    "Shield": 1, "Focus": 1, "Buckler": 1,
    # Jewellery/Quiver: 0 sockets
    "Ring": 0, "Amulet": 0, "Belt": 0, "Quiver": 0,
}


def get_max_sockets_for_item_class(item_class: str) -> int:
    """Determine default max sockets from item_class."""
    from poe2_crafting_mcp.crafting.desecration import get_bone_slot_for_item_class
    # Try direct slot name first (for item_classes that ARE slot names)
    if item_class in MAX_SOCKETS_BY_SLOT:
        return MAX_SOCKETS_BY_SLOT[item_class]
    # Map item_class to slot
    # Import here to avoid circular
    slot_map = {
        "Bows": "Bow", "Crossbows": "Crossbow", "Daggers": "Dagger",
        "Claws": "Claw", "Flails": "Flail", "Spears": "Spear",
        "Quarterstaves": "Quarterstaff", "Sceptres": "Sceptre",
        "Wands": "Wand", "Staves": "Staff", "Rings": "Ring",
        "Amulets": "Amulet", "Belts": "Belt", "Quivers": "Quiver",
        "Talismans": "Talisman", "Traps": "Talisman",
        "Foci": "Focus", "Bucklers": "Buckler",
        "One_Hand_Swords": "One Hand Sword", "Two_Hand_Swords": "Two Hand Sword",
        "One_Hand_Axes": "One Hand Axe", "Two_Hand_Axes": "Two Hand Axe",
        "One_Hand_Maces": "One Hand Mace", "Two_Hand_Maces": "Two Hand Mace",
    }
    if item_class in slot_map:
        return MAX_SOCKETS_BY_SLOT.get(slot_map[item_class], 0)
    # Armour with attribute suffixes (e.g. Body_Armours_str, Gloves_int)
    for prefix, slot in [
        ("Body_Armours", "Body Armour"), ("Boots", "Boots"),
        ("Gloves", "Gloves"), ("Helmets", "Helmet"),
        ("Shields", "Shield"),
    ]:
        if item_class.startswith(prefix):
            return MAX_SOCKETS_BY_SLOT.get(slot, 0)
    return 0

# Omen gentype_only: 1=prefix, 2=suffix
# Multiple omens can be active simultaneously — their effects stack.
OMENS: dict[str, dict[str, Any]] = {
    # ── Exaltation omens ──────────────────────────────────────────────────────
    "sinistral_exaltation":    {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "gentype_only": 1},
    "dextral_exaltation":      {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "gentype_only": 2},
    "greater_exaltation":      {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "qty_override": 2},
    "homogenising_exaltation": {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "homogenise": True},
    "catalysing_exaltation":   {"applies_to": ["exalted", "greater_exalted", "perfect_exalted"], "catalyse": True},
    # ── Annulment omens ───────────────────────────────────────────────────────
    "sinistral_annulment":     {"applies_to": ["annulment"], "del_gentype_only": 1},
    "dextral_annulment":       {"applies_to": ["annulment"], "del_gentype_only": 2},
    # ── Erasure omens (Chaos) ─────────────────────────────────────────────────
    "sinistral_erasure":       {"applies_to": ["chaos", "greater_chaos", "perfect_chaos"], "del_gentype_only": 1},
    "dextral_erasure":         {"applies_to": ["chaos", "greater_chaos", "perfect_chaos"], "del_gentype_only": 2},
    "whittling":               {"applies_to": ["chaos", "greater_chaos", "perfect_chaos"], "del_target": "lowest_req_level"},
    # ── Coronation omens (Regal) ──────────────────────────────────────────────
    "sinistral_coronation":    {"applies_to": ["regal", "greater_regal", "perfect_regal"], "gentype_only": 1},
    "dextral_coronation":      {"applies_to": ["regal", "greater_regal", "perfect_regal"], "gentype_only": 2},
    "homogenising_coronation": {"applies_to": ["regal", "greater_regal", "perfect_regal"], "homogenise": True},
    # ── Crystallisation omens (Essence) ───────────────────────────────────────
    "sinistral_crystallisation": {"applies_to": ["perfect_essence"], "del_gentype_only": 1},
    "dextral_crystallisation":   {"applies_to": ["perfect_essence"], "del_gentype_only": 2},
    # ── Alchemy omens ─────────────────────────────────────────────────────────
    "sinistral_alchemy":       {"applies_to": ["alchemy"], "gentype_only": 1},
    "dextral_alchemy":         {"applies_to": ["alchemy"], "gentype_only": 2},
    # ── Corruption / Terminal omens ───────────────────────────────────────────
    "corruption":              {"applies_to": ["vaal"], "force_outcome": True},
    "blessed":                 {"applies_to": ["divine"], "implicit_only": True},
    "sanctification":          {"applies_to": ["divine"], "sanctify": True},
    "recombination":           {"applies_to": ["recombinator"], "lucky": True},
    # ── Abyss omens (desecration system) ──────────────────────────────────────
    "sinistral_necromancy":    {"applies_to": ["desecrate"], "gentype_only": 1},
    "dextral_necromancy":      {"applies_to": ["desecrate"], "gentype_only": 2},
    "light":                   {"applies_to": ["annulment"], "desecrated_only": True},
    "abyssal_echoes":          {"applies_to": ["desecrate"], "reroll_reveal": True},
    "putrefaction":            {"applies_to": ["desecrate"], "replace_all": True},
    "blackblooded":            {"applies_to": ["desecrate"], "lich_pool": "kurgal"},
    "liege":                   {"applies_to": ["desecrate"], "lich_pool": "amanamu"},
    "sovereign":               {"applies_to": ["desecrate"], "lich_pool": "ulaman"},
}


class CraftingSimulator:
    """
    Crafting state machine with probability calculation.

    Tracks item state, applies currency operations, and calculates
    exact probabilities for hitting target mods.
    """

    def __init__(self, item_class: str, ilvl: int, mod_pool: dict, essence_pool: dict | None = None):
        """
        Args:
            item_class: poe2db item class (e.g. "Gloves_int")
            ilvl: item level
            mod_pool: result from PriceDatabase.get_craftable_mods()
                      Must include 'prefixes' and 'suffixes' with tier data.
            essence_pool: optional result from get_craftable_mods(pool='essence')
                          If None, _find_essence_mod falls back to normal pool.
                          Should include both 'essence' and 'perfect_essence' mods.
        """
        self.item_class = item_class
        self.ilvl = ilvl
        self.item = ItemState(
            item_class=item_class, ilvl=ilvl, rarity="Rare",
            max_sockets=get_max_sockets_for_item_class(item_class),
        )

        # Reforging: tracks spare bases available for 3-to-1 recycling.
        # Each failed craft that gets scoured/discarded adds 1 to this count.
        # Reforging consumes 2 spares (current item + 2 spares → 1 new item).
        self.reforge_stock: int = 0

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
                    'tags': tier.get('tags', []),
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
                    'tags': tier.get('tags', []),
                })

        # Flatten essence-specific pool (mods that only essences can guarantee)
        # This includes essence-exclusive mods not in the normal pool
        self._essence_mods: list[dict] = []
        if essence_pool:
            for group in essence_pool.get('prefixes', []):
                for tier_idx, tier in enumerate(group['tiers']):
                    self._essence_mods.append({
                        'family': group['family'],
                        'affix_type': 'prefix',
                        'tier': tier_idx + 1,
                        'req_level': tier['req_level'],
                        'weight': tier.get('weight', 0),
                        'stat_text': tier['stat_text'],
                    })
            for group in essence_pool.get('suffixes', []):
                for tier_idx, tier in enumerate(group['tiers']):
                    self._essence_mods.append({
                        'family': group['family'],
                        'affix_type': 'suffix',
                        'tier': tier_idx + 1,
                        'req_level': tier['req_level'],
                        'weight': tier.get('weight', 0),
                        'stat_text': tier['stat_text'],
                    })

    @classmethod
    def from_db(cls, item_class: str, ilvl: int, db_path: str = "data/poe2_craft.db") -> "CraftingSimulator":
        """Create a simulator with all pools loaded from the database.

        Loads the normal pool for rolling + combined essence/perfect_essence
        pool for essence-guaranteed mods.
        """
        from poe2_crafting_mcp.data.price_db import PriceDatabase
        pdb = PriceDatabase(db_path)

        normal_pool = pdb.get_craftable_mods(item_class, ilvl=ilvl, pool='normal')
        essence_pool = pdb.get_craftable_mods(item_class, ilvl=ilvl, pool='essence')
        perfect_pool = pdb.get_craftable_mods(item_class, ilvl=ilvl, pool='perfect_essence')

        # Merge essence + perfect_essence into one pool for the simulator
        merged_essence = {
            'prefixes': essence_pool['prefixes'] + perfect_pool['prefixes'],
            'suffixes': essence_pool['suffixes'] + perfect_pool['suffixes'],
        }

        return cls(item_class, ilvl, normal_pool, essence_pool=merged_essence)

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

    def identify_mod_family(self, mod_text: str) -> str | None:
        """Match a mod stat text to its family name.

        Useful for converting trade listing mods into family names for blocking.
        Uses fuzzy matching: strips numbers from both sides and compares templates.

        Args:
            mod_text: stat text from a trade listing (e.g. "+120 to maximum Life")

        Returns:
            Family name (e.g. "IncreasedLife") or None if no match.
        """
        import re

        # Normalize: replace all numbers (including ranges like "120-149") with #
        def _normalize(text: str) -> str:
            # Handle ranges like (120-149) or (1-4)
            text = re.sub(r'\(?\d+\.?\d*\s*[-–—]\s*\d+\.?\d*\)?', '#', text)
            # Handle single numbers with optional +/-
            text = re.sub(r'[+-]?\d+\.?\d*', '#', text)
            # Collapse multiple # into one
            text = re.sub(r'#+', '#', text)
            # Normalize +# to just # for matching
            text = text.replace('+#', '#')
            return text.lower().strip()

        target = _normalize(mod_text)
        best_match = None
        best_score = 0

        # Build a set of unique (normalized_text → family) from all mods
        seen: dict[str, str] = {}
        for mod in self._all_mods:
            norm = _normalize(mod['stat_text'])
            if norm not in seen:
                seen[norm] = mod['family']

        # Try exact match first
        if target in seen:
            return seen[target]

        # Fuzzy: find SHORTEST containing match (most specific)
        for norm, family in seen.items():
            if target in norm or norm in target:
                # Prefer shorter matches (more specific)
                # "# to maximum life" matching "# to maximum life" (len=18) is better
                # than matching "#% increased energy shield # to maximum life" (len=48)
                if target == norm:
                    return family
                # For substring: prefer the one closest in length to target
                score = 1.0 / (1 + abs(len(norm) - len(target)))
                if score > best_score:
                    best_score = score
                    best_match = family

        return best_match

    def identify_mods_from_text(self, mod_texts: list[str]) -> list[dict]:
        """Identify multiple mod texts → family names.

        Returns list of {text, family, affix_type} for each matched mod.
        """
        results = []
        for text in mod_texts:
            family = self.identify_mod_family(text)
            affix_type = ""
            if family:
                for mod in self._all_mods:
                    if mod['family'] == family:
                        affix_type = mod['affix_type']
                        break
            results.append({
                "text": text,
                "family": family or "(unknown)",
                "affix_type": affix_type or "?",
            })
        return results

    def roll_mod(
        self, min_mod_level: int = 0, gentype_only: int = 0, homogenise: bool = False
    ) -> ModInstance | None:
        """Roll a random mod from the available pool (for simulation).

        Args:
            min_mod_level: minimum req_level filter (Greater/Perfect currencies)
            gentype_only: 1=prefix only, 2=suffix only, 0=both
            homogenise: if True, only mods sharing tags with existing item mods
        """
        pool = self.get_available_pool(min_mod_level=min_mod_level, gentype_only=gentype_only)

        # Homogenise filter: only mods sharing at least one tag with existing mods
        if homogenise and pool:
            existing_tags: set[str] = set()
            for mod in self.item.mods:
                # Find the mod's tags from _all_mods or _essence_mods
                for pool_mod in self._all_mods:
                    if pool_mod['family'] == mod.family and pool_mod['tier'] == mod.tier:
                        existing_tags.update(pool_mod.get('tags', []))
                        break
            if existing_tags:
                pool = [m for m in pool if set(m.get('tags', [])) & existing_tags]

        if not pool:
            return None

        total = sum(m['weight'] for m in pool)
        if total <= 0:
            return None
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

    def apply_currency(
        self,
        currency: str,
        omen: str = "",
        omens: list[str] | None = None,
        essence_family: str = "",
        essence_stat_text: str = "",
    ) -> ItemState:
        """Apply a currency to the item, mutating state. Returns new state.

        Args:
            currency: currency key from CURRENCIES dict
            omen: single omen key (backward compat, deprecated — use omens=[])
            omens: list of active omen keys. Multiple omens stack their effects.
                   E.g. omens=["dextral_exaltation", "greater_exaltation"] adds 2 suffixes.
            essence_family: for essence operations, the guaranteed mod family
            essence_stat_text: for essence operations, the exact stat_text to place
                               (pins the correct tier). If empty, picks best tier.
        """
        cur = CURRENCIES.get(currency)
        if not cur:
            raise ValueError(f"Unknown currency: {currency}")

        # Validate: corrupted items can't be modified
        if self.item.corrupted:
            raise ValueError("Cannot apply currency to corrupted item")

        # Validate: rarity constraint
        from_rarity = cur.get("from_rarity")
        if from_rarity and self.item.rarity not in from_rarity:
            raise ValueError(
                f"{currency} requires rarity {from_rarity}, item is {self.item.rarity}"
            )

        # Validate: min_mods constraint (e.g. fracturing orb needs 4+ mods)
        min_mods = cur.get("min_mods", 0)
        if min_mods and len(self.item.mods) < min_mods:
            raise ValueError(
                f"{currency} requires at least {min_mods} mods, item has {len(self.item.mods)}"
            )

        # ── Merge omen effects ────────────────────────────────────────────────
        # Support both old single-omen API and new multi-omen list
        active_omens: list[str] = []
        if omens:
            active_omens = omens
        elif omen:
            active_omens = [omen]

        # Merge all active omen effects into composite values
        gentype_only = 0
        del_gentype_only = 0
        del_target = ""
        homogenise = False
        qty = cur.get("qty", 1)

        for omen_key in active_omens:
            omen_def = OMENS.get(omen_key, {})
            # Validate omen applies to this currency
            applies_to = omen_def.get("applies_to", [])
            if applies_to and currency not in applies_to:
                continue  # omen doesn't affect this currency, skip
            if omen_def.get("gentype_only"):
                gentype_only = omen_def["gentype_only"]
            if omen_def.get("del_gentype_only"):
                del_gentype_only = omen_def["del_gentype_only"]
            if omen_def.get("del_target"):
                del_target = omen_def["del_target"]
            if omen_def.get("homogenise"):
                homogenise = True
            if "qty_override" in omen_def:
                qty = omen_def["qty_override"]

        op = cur["op"]
        min_lv = cur.get("min_lv", 0)

        # Rarity change
        if "to_rarity" in cur:
            self.item.rarity = cur["to_rarity"]

        if op == "add":
            for _ in range(qty):
                mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only, homogenise=homogenise)
                if mod:
                    self.item.mods.append(mod)

        elif op == "del_add":
            # Remove step
            removable = self._get_removable(del_gentype_only, del_target)
            if removable:
                to_remove = self._pick_removal_target(removable, del_target)
                self.item.mods.remove(to_remove)
                if to_remove.family == self.item.essence_mod_family:
                    self.item.essence_mod_family = None
            # Add step
            mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only, homogenise=homogenise)
            if mod:
                self.item.mods.append(mod)

        elif op == "del":
            removable = self._get_removable(del_gentype_only)
            for _ in range(qty):
                if removable:
                    to_remove = random.choice(removable)
                    self.item.mods.remove(to_remove)
                    if to_remove.family == self.item.essence_mod_family:
                        self.item.essence_mod_family = None
                    removable = self._get_removable(del_gentype_only)

        elif op == "reroll":
            # Remove all non-fractured mods, clear essence tracking
            self.item.mods = [m for m in self.item.mods if m.fractured]
            self.item.essence_mod_family = None
            # Add N mods
            for _ in range(cur.get("qty", 4)):
                if self.item.open_affixes > 0:
                    mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
                    if mod:
                        self.item.mods.append(mod)

        elif op == "scour":
            self.item.mods = [m for m in self.item.mods if m.fractured]
            self.item.rarity = "Normal"
            self.item.essence_mod_family = None

        elif op == "reforge":
            # Reforging bench: 3-to-1. Current item + 2 from stock → fresh Rare.
            if self.reforge_stock < 2:
                raise ValueError(
                    f"Reforge requires 2 spare bases in stock (have {self.reforge_stock}). "
                    f"Use 'stash' to add failed items to stock, or buy bases."
                )
            self.reforge_stock -= 2
            # Reset item completely (all mods gone, fresh start)
            self.item.mods = [m for m in self.item.mods if m.fractured]
            self.item.rarity = "Rare"
            self.item.essence_mod_family = None
            # Roll 4 fresh mods (same as alchemy)
            for _ in range(4):
                if self.item.open_affixes > 0:
                    mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
                    if mod:
                        self.item.mods.append(mod)

        elif op == "essence_upgrade":
            # Greater Essence: Magic → Rare with guaranteed mod + random fill
            self._apply_essence_upgrade(essence_family, min_lv, gentype_only, essence_stat_text)

        elif op == "essence_swap":
            # Perfect Essence: remove 1, add 1 guaranteed (NOT a reroll)
            self._apply_essence_swap(essence_family, del_gentype_only, essence_stat_text)

        elif op == "fracture":
            non_fractured = [m for m in self.item.mods if not m.fractured]
            if non_fractured:
                chosen = random.choice(non_fractured)
                chosen.fractured = True

        elif op == "divine":
            pass  # Values reroll within tier — doesn't change mod structure

        elif op == "quality":
            # Add quality to item (5% per use, max 20)
            if self.item.quality >= 20:
                raise ValueError("Item already at maximum quality (20%)")
            self.item.quality = min(20, self.item.quality + cur.get("qty", 5))

        elif op == "add_socket":
            # Artificer's Orb: always adds 1 socket (guaranteed)
            if self.item.corrupted:
                raise ValueError("Cannot add socket to corrupted item")
            if len(self.item.sockets) >= self.item.max_sockets:
                raise ValueError(
                    f"Item at max sockets ({self.item.max_sockets}). "
                    f"Use Vaal Orb for a chance at +1 beyond max."
                )
            # Socket is added as empty (no augment placed yet)
            self.item.sockets.append("")

        elif op == "corrupt":
            # Vaal Orb: corrupts item with random outcome
            if self.item.corrupted:
                raise ValueError("Item is already corrupted")
            self.item.corrupted = True

            # Check for Omen of Corruption (removes "no change" outcome)
            has_corruption_omen = "corruption" in [o for o in active_omens]

            # Determine if item can gain sockets (weapons + armour only, not jewellery)
            from poe2_crafting_mcp.crafting.desecration import get_bone_slot_for_item_class
            slot_cat = get_bone_slot_for_item_class(self.item_class)
            can_gain_socket = slot_cat in ("weapon", "armour")

            # Build outcome pool (equally weighted per wiki)
            outcomes = []
            if not has_corruption_omen:
                outcomes.append("nothing")
            outcomes.append("reroll_mods")      # reroll up to 3 mods
            outcomes.append("enchantment")       # add Vaal enchantment
            if can_gain_socket:
                outcomes.append("socket")        # add socket beyond max
            else:
                outcomes.append("nothing_socket")  # jewellery: pseudo no-change

            outcome = random.choice(outcomes)

            if outcome == "reroll_mods":
                # Reroll up to 3 existing mods into new ones
                non_fractured = [m for m in self.item.mods if not m.fractured]
                n_to_reroll = min(3, len(non_fractured))
                if n_to_reroll > 0:
                    to_reroll = random.sample(non_fractured, n_to_reroll)
                    for mod in to_reroll:
                        self.item.mods.remove(mod)
                    # Add same number of new mods
                    for _ in range(n_to_reroll):
                        new_mod = self.roll_mod()
                        if new_mod:
                            self.item.mods.append(new_mod)

            elif outcome == "enchantment":
                # Add a Vaal enchantment from the corrupted pool
                # Store as a special field (doesn't take a prefix/suffix slot)
                self.item.corruption_enchantment = self._roll_corruption_enchantment()

            elif outcome == "socket":
                # Add +1 socket beyond normal max
                self.item.max_sockets += 1
                self.item.sockets.append("")
            # "nothing" and "nothing_socket" — only corrupted tag added

        elif op == "architect_corrupt":
            # Architect's Orb: requires already-corrupted item
            # 50% chance to add second corruption enchantment, 50% destroy
            if not self.item.corrupted:
                raise ValueError("Architect's Orb requires a corrupted item")
            if random.random() < 0.5:
                # Success: add second enchantment
                enchant = self._roll_corruption_enchantment()
                if self.item.corruption_enchantment:
                    # Append to existing (both are kept)
                    self.item.corruption_enchantment += "\n" + enchant
                else:
                    self.item.corruption_enchantment = enchant
            else:
                # Failure: item destroyed
                raise ValueError("DESTROYED — Architect's Orb failed (50% chance)")

        return self.item


    def stash_for_reforge(self) -> None:
        """Stash current item as a spare base for reforging.

        Increments reforge_stock and resets the item to a fresh Normal state.
        Used when a craft attempt fails and the item should be recycled.
        """
        self.reforge_stock += 1
        self.item = ItemState(
            item_class=self.item_class,
            ilvl=self.ilvl,
            rarity="Normal",
            max_sockets=get_max_sockets_for_item_class(self.item_class),
        )

    def buy_base(self, count: int = 1) -> None:
        """Buy fresh bases and add to reforge stock.

        Represents purchasing white bases from trade to fuel reforging.
        Cost tracking is handled by the caller (optimizer/CLI).
        """
        self.reforge_stock += count


    def _roll_corruption_enchantment(self) -> str:
        """Roll a random Vaal enchantment from the corrupted pool for this item class."""
        # Query the corrupted pool for this item class at ilvl
        from poe2_crafting_mcp.data.price_db import PriceDatabase
        try:
            pdb = PriceDatabase()
            rows = pdb._conn.execute(
                "SELECT stat_text FROM mod_weights "
                "WHERE pool = 'corrupted' AND item_class = ? AND req_level <= ?",
                (self.item_class, self.ilvl),
            ).fetchall()
            if rows:
                return random.choice(rows)[0]
        except Exception:
            pass
        return ""

    def _get_removable(
        self, del_gentype_only: int = 0, del_target: str = ""
    ) -> list[ModInstance]:
        """Get removable mods filtered by omen targeting."""
        removable = self.item.removable_mods
        if del_gentype_only == 1:
            removable = [m for m in removable if m.affix_type == "prefix"]
        elif del_gentype_only == 2:
            removable = [m for m in removable if m.affix_type == "suffix"]
        return removable

    def _pick_removal_target(
        self, removable: list[ModInstance], del_target: str = ""
    ) -> ModInstance:
        """Pick which mod to remove. Deterministic for whittling, random otherwise."""
        if del_target == "lowest_req_level" and removable:
            return min(removable, key=lambda m: m.req_level)
        return random.choice(removable)

    def _apply_essence_upgrade(
        self, essence_family: str, min_lv: int = 0, gentype_only: int = 0,
        essence_stat_text: str = "",
    ) -> None:
        """Essence upgrade: Magic → Rare with guaranteed mod + random fill to 4.

        All essence tiers (Lesser/Normal/Greater) work the same:
        - Requires Magic item
        - Upgrades to Rare
        - Keeps existing Magic mods
        - Adds 1 guaranteed essence mod
        - Fills remaining slots randomly to 4 total mods

        Family blocking: cannot use if essence_family is already on item
        (game prevents using an essence whose guaranteed mod shares a family
        with an existing mod on the item).
        """
        if not essence_family:
            raise ValueError("essence_family required for essence operations")

        # Family blocking: game won't let you use essence if the guaranteed
        # family already exists on the item (regardless of fractured status)
        if essence_family in self.item.families_on_item:
            if essence_family != self.item.essence_mod_family:
                raise ValueError(
                    f"Cannot use essence: family '{essence_family}' already on item"
                )

        # If item already has an essence mod, remove it (one per item rule)
        if self.item.essence_mod_family:
            self.item.mods = [
                m for m in self.item.mods
                if m.family != self.item.essence_mod_family or m.fractured
            ]

        # Add the guaranteed essence mod
        essence_mod = self._find_essence_mod(essence_family, essence_stat_text)
        if essence_mod:
            self.item.mods.append(essence_mod)
            self.item.essence_mod_family = essence_family

        # No random fill — essence only adds the 1 guaranteed mod.
        # The item keeps its existing Magic mods + the essence mod.
        # Result: 2-3 mods total (1-2 from Magic + 1 essence).

    def _apply_essence_swap(
        self, essence_family: str, del_gentype_only: int = 0,
        essence_stat_text: str = "",
    ) -> None:
        """Perfect Essence: remove 1 mod, add 1 guaranteed. NOT a reroll.

        Slot-forcing: if the essence mod's affix type is full,
        removal is forced to target that type (making room).
        Crystallisation omen overrides: del_gentype_only controls removal type.

        Family blocking: the game prevents using a perfect essence if the
        target family is already on the item AND it would remain after the
        removal step (i.e., if it's fractured). If the existing mod with
        that family can be removed, the essence is allowed (remove then add).
        """
        if not essence_family:
            raise ValueError("essence_family required for perfect_essence")

        # Family blocking check: can't use if family is on item AND the mod is
        # fractured (permanent). Non-fractured mods could be the removal target.
        existing_family_mod = next(
            (m for m in self.item.mods if m.family == essence_family), None
        )
        if existing_family_mod and existing_family_mod.fractured:
            if essence_family != self.item.essence_mod_family:
                raise ValueError(
                    f"Cannot use essence: family '{essence_family}' is fractured on item"
                )

        # If item already has an essence mod, that mod is removed first (one per item)
        if self.item.essence_mod_family:
            old_essence = [
                m for m in self.item.mods
                if m.family == self.item.essence_mod_family and not m.fractured
            ]
            if old_essence:
                self.item.mods.remove(old_essence[0])
                self.item.essence_mod_family = None
            # The essence mod counts as the "remove 1" step
        else:
            # Determine affix type of the essence mod for slot-forcing
            essence_affix_type = self._get_family_affix_type(essence_family)

            # Slot-forcing: if essence is suffix and all suffixes full, force suffix removal
            # Crystallisation omen overrides this with explicit targeting
            effective_del_gentype = del_gentype_only
            if effective_del_gentype == 0 and essence_affix_type:
                if essence_affix_type == "prefix" and self.item.open_prefixes == 0:
                    effective_del_gentype = 1  # force prefix removal
                elif essence_affix_type == "suffix" and self.item.open_suffixes == 0:
                    effective_del_gentype = 2  # force suffix removal

            removable = self._get_removable(effective_del_gentype)
            if removable:
                to_remove = random.choice(removable)
                self.item.mods.remove(to_remove)

        # Add guaranteed essence mod
        essence_mod = self._find_essence_mod(essence_family, essence_stat_text)
        if essence_mod:
            self.item.mods.append(essence_mod)
            self.item.essence_mod_family = essence_family

    def _find_essence_mod(self, family: str, stat_text: str = "") -> ModInstance | None:
        """Find the correct essence mod to place on the item.

        If stat_text is provided (from EssenceResolver), matches the exact mod
        tier. This ensures Lesser/Normal/Greater/Perfect essences place the
        correct tier, not just the best available.

        If stat_text is empty, falls back to best tier at ilvl (legacy behavior).
        """
        # If exact stat_text provided, find the matching mod
        if stat_text:
            # Search essence pool first
            match = next(
                (m for m in self._essence_mods
                 if m['family'] == family and m['stat_text'] == stat_text),
                None,
            )
            # Fall back to normal pool
            if not match:
                match = next(
                    (m for m in self._all_mods
                     if m['family'] == family and m['stat_text'] == stat_text),
                    None,
                )
            if match:
                return ModInstance(
                    family=match['family'],
                    affix_type=match['affix_type'],
                    tier=match['tier'],
                    req_level=match['req_level'],
                    weight=match.get('weight', 0),
                    stat_text=match['stat_text'],
                )

        # Fallback: find best tier at ilvl (when stat_text not specified)
        # Search essence pool first (has essence-exclusive mods)
        candidates = [
            m for m in self._essence_mods
            if m['family'] == family and m['req_level'] <= self.ilvl
        ]
        # Fall back to normal pool if not found in essence pool
        if not candidates:
            candidates = [
                m for m in self._all_mods
                if m['family'] == family and m['req_level'] <= self.ilvl
            ]
        if not candidates:
            return None
        # Essence guarantees best available tier (tier 1 = best)
        best = min(candidates, key=lambda m: m['tier'])
        return ModInstance(
            family=best['family'],
            affix_type=best['affix_type'],
            tier=best['tier'],
            req_level=best['req_level'],
            weight=best['weight'],
            stat_text=best['stat_text'],
        )

    def _get_family_affix_type(self, family: str) -> str:
        """Look up whether a family is prefix or suffix."""
        # Check essence pool first (for essence-exclusive families)
        for mod in self._essence_mods:
            if mod['family'] == family:
                return mod['affix_type']
        for mod in self._all_mods:
            if mod['family'] == family:
                return mod['affix_type']
        return ""

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
