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
    stat_text: str       # range text (e.g. "+(25-27) to Dexterity")
    fractured: bool = False
    desecrated: bool = False  # True if this mod came from abyss desecration
    value: float | None = None  # actual rolled value within the range (None = not yet rolled)

    def __post_init__(self):
        """Roll a value if not already set."""
        if self.value is None:
            self.value = _roll_stat_value(self.stat_text)

    @property
    def display_text(self) -> str:
        """Show the rolled value inline with the range.
        
        Examples:
            '+(25-27) to Dexterity' with value=26 → '+26(25-27) to Dexterity'
            '(68-79)% increased Energy Shield' with value=72 → '72%(68-79) increased Energy Shield'
            'Adds (4-6) to (7-11) Physical Damage' → 'Adds 5(4-6) to 9(7-11) Physical Damage'
        """
        if self.value is None:
            return self.stat_text
        return _format_with_value(self.stat_text, self.value)

    def divine(self) -> None:
        """Reroll the value within the stat range (Divine Orb)."""
        self.value = _roll_stat_value(self.stat_text)

    def __repr__(self) -> str:
        frac = " [F]" if self.fractured else ""
        desc = " [D]" if self.desecrated else ""
        return f"<{self.affix_type[0].upper()} T{self.tier} {self.family}{frac}{desc}>"


def _parse_stat_range(stat_text: str) -> tuple[float | None, float | None]:
    """Extract (min, max) of the FIRST numeric range from stat_text.
    
    Examples:
        '+(25-27) to Dexterity' → (25, 27)
        '(68-79)% increased Energy Shield' → (68, 79)
        'Adds (4-6) to (7-11) Physical Damage' → (4, 6)  # first range only
        '+45 to maximum Life' → (45, 45)  # single value
    """
    import re
    ranges = re.findall(r'\((\d+(?:\.\d+)?)[—–-](\d+(?:\.\d+)?)\)', stat_text)
    if ranges:
        return float(ranges[0][0]), float(ranges[0][1])
    
    # Single value patterns: +45, 5%, etc.
    single = re.search(r'[+]?(\d+(?:\.\d+)?)', stat_text)
    if single:
        v = float(single.group(1))
        return v, v
    
    return None, None


def _parse_all_ranges(stat_text: str) -> list[tuple[float, float]]:
    """Extract ALL (min, max) ranges from stat_text.
    
    'Adds (4-6) to (7-11) Physical Damage' → [(4, 6), (7, 11)]
    '+(25-27) to Dexterity' → [(25, 27)]
    """
    import re
    ranges = re.findall(r'\((\d+(?:\.\d+)?)[—–-](\d+(?:\.\d+)?)\)', stat_text)
    return [(float(lo), float(hi)) for lo, hi in ranges]


def _roll_stat_value(stat_text: str) -> float | None:
    """Roll a random value for the first range in stat_text."""
    import random as _rand
    lo, hi = _parse_stat_range(stat_text)
    if lo is None or hi is None:
        return None
    if lo == hi:
        return lo
    if lo == int(lo) and hi == int(hi):
        return float(_rand.randint(int(lo), int(hi)))
    return round(_rand.uniform(lo, hi), 2)


def _roll_all_values(stat_text: str) -> list[float]:
    """Roll values for ALL ranges in stat_text."""
    import random as _rand
    ranges = _parse_all_ranges(stat_text)
    values = []
    for lo, hi in ranges:
        if lo == hi:
            values.append(lo)
        elif lo == int(lo) and hi == int(hi):
            values.append(float(_rand.randint(int(lo), int(hi))))
        else:
            values.append(round(_rand.uniform(lo, hi), 2))
    return values


def _format_with_value(stat_text: str, value: float) -> str:
    """Format stat_text showing rolled values inline with ranges.
    
    Replaces each (min-max) pattern with value(min-max):
        '+(25-27) to Dexterity' → '+26(25-27) to Dexterity'
        '(68-79)% increased ES' → '72%(68-79) increased ES'
        'Adds (4-6) to (7-11) Phys' → 'Adds 5(4-6) to 9(7-11) Phys'
    """
    import re
    
    ranges = _parse_all_ranges(stat_text)
    if not ranges:
        return stat_text
    
    # Compute values for each range
    values: list[float] = [value]
    if len(ranges) > 1:
        lo0, hi0 = ranges[0]
        proportion = (value - lo0) / (hi0 - lo0) if hi0 > lo0 else 0.5
        for lo, hi in ranges[1:]:
            derived = lo + proportion * (hi - lo)
            if lo == int(lo) and hi == int(hi):
                derived = float(round(derived))
            else:
                derived = round(derived, 2)
            values.append(derived)
    
    # Replace ranges right-to-left to preserve positions
    # Find all range matches with their positions
    range_pattern = re.compile(r'\((\d+(?:\.\d+)?)[—–-](\d+(?:\.\d+)?)\)')
    matches = list(range_pattern.finditer(stat_text))
    
    if len(matches) != len(values):
        return stat_text  # safety fallback
    
    # Process right-to-left so positions don't shift
    result = stat_text
    for match, val in reversed(list(zip(matches, values))):
        start = match.start()
        end = match.end()
        range_str = match.group(0)  # e.g. "(25-27)"
        
        # Format value
        if val == int(val):
            val_str = str(int(val))
        else:
            # Use enough precision to distinguish
            val_str = f"{val:.2f}".rstrip('0').rstrip('.')
        
        # Check context: what's before and after?
        prefix_char = result[start - 1] if start > 0 else ""
        suffix_char = result[end] if end < len(result) else ""
        
        if prefix_char == "+" and suffix_char == "%":
            # +val%(range) — e.g. +(24-27)% → +27%(24-27)
            replacement = f"+{val_str}%{range_str}"
            result = result[:start - 1] + replacement + result[end + 1:]
        elif prefix_char == "+":
            # +val(range) — e.g. +(25-27) to Dex → +26(25-27) to Dex
            replacement = f"+{val_str}{range_str}"
            result = result[:start - 1] + replacement + result[end:]
        elif suffix_char == "%":
            # val%(range) — e.g. (68-79)% → 72%(68-79)
            replacement = f"{val_str}%{range_str}"
            result = result[:start] + replacement + result[end + 1:]
        else:
            # val(range) — plain number
            replacement = f"{val_str}{range_str}"
            result = result[:start] + replacement + result[end:]
    
    return result


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
    corruption_enchantment: str = ""       # DEPRECATED — use implicits list instead
    has_abyss_mark: bool = False           # True if "Mark of the Abyssal Lord" is on item
    abyss_mark_min_level: int = 0          # req_level of the mod removed by Abyss essence (tier floor for reveal)
    implicits: list[ModInstance] = field(default_factory=list)  # corruption implicits, base implicits
    desecrated_unrevealed: bool = False    # True if item has an unrevealed desecrated mod pending
    desecrated_affix_type: str = ""        # "prefix" or "suffix" — what slot is reserved for reveal

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
            has_abyss_mark=self.has_abyss_mark,
            abyss_mark_min_level=self.abyss_mark_min_level,
            implicits=[ModInstance(**m.__dict__) for m in self.implicits],
            desecrated_unrevealed=self.desecrated_unrevealed,
            desecrated_affix_type=self.desecrated_affix_type,
        )


# ── Currency Definitions ──────────────────────────────────────────────────────

CURRENCIES: dict[str, dict[str, Any]] = {
    # Basic
    "transmute":         {"op": "add", "qty": 1, "min_lv": 0,  "to_rarity": "Magic", "from_rarity": ["Normal"]},
    "augment":           {"op": "add", "qty": 1, "min_lv": 0,  "from_rarity": ["Magic"]},
    "regal":             {"op": "add", "qty": 1, "min_lv": 0,  "to_rarity": "Rare", "from_rarity": ["Magic"]},
    "alchemy":           {"op": "reroll", "qty": 4, "min_lv": 0, "to_rarity": "Rare", "from_rarity": ["Normal", "Magic"]},
    "chaos":             {"op": "del_add", "qty": 1, "min_lv": 0, "from_rarity": ["Rare"]},
    "exalted":           {"op": "add", "qty": 1, "min_lv": 0,  "from_rarity": ["Rare"]},
    "annulment":         {"op": "del", "qty": 1, "min_lv": 0,  "from_rarity": ["Magic", "Rare"]},
    "divine":            {"op": "divine", "min_lv": 0, "from_rarity": ["Magic", "Rare"]},
    "fracturing":        {"op": "fracture", "min_lv": 0, "from_rarity": ["Rare"], "min_mods": 4},
    "scour":             {"op": "scour", "min_lv": 0},
    # NOTE: Orb of Alteration does NOT exist in PoE2 (not obtainable in game)
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
    "reforge":           {"op": "reforge", "qty": 4, "min_lv": 0, "from_rarity": ["Magic", "Rare"]},
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
    # ── Abyss omens (desecration system) ──────────────────────────────────────
    # Consumed at bone application (desecrate step):
    "sinistral_necromancy":    {"applies_to": ["desecrate"], "gentype_only": 1},
    "dextral_necromancy":      {"applies_to": ["desecrate"], "gentype_only": 2},
    "putrefaction":            {"applies_to": ["desecrate"], "replace_all": True},
    "blackblooded":            {"applies_to": ["desecrate"], "lich_pool": "kurgal", "slots": ["weapon", "jewellery"]},
    "liege":                   {"applies_to": ["desecrate"], "lich_pool": "amanamu", "slots": ["weapon", "jewellery"]},
    "sovereign":               {"applies_to": ["desecrate"], "lich_pool": "ulaman", "slots": ["weapon", "jewellery"]},
    # Consumed at reveal step (Well of Souls):
    "abyssal_echoes":          {"applies_to": ["reveal"], "reroll_reveal": True},
    # Consumed on annulment (targets only the abyss mod):
    "light":                   {"applies_to": ["annulment"], "desecrated_only": True},
}


# ── Rune Pool Mapping ────────────────────────────────────────────────────────
# Game Warp Runes that expand the crafting mod pool when socketed.
# Key: pool name in mod_weights table. Value: in-game rune name.
RUNE_POOL_NAMES: dict[str, str] = {
    "marksman":    "Kolr's Hunt",
    "decay":       "Katla's Gloom",
    "chronomancy": "Uhtred's Sidereus",
    "destruction": "Thrud's Might",
    "berserking":  "Vorana's Carnage",
    "soul":        "Medved's Tending",
}

# Reverse mapping: rune display name → pool name
RUNE_NAME_TO_POOL: dict[str, str] = {v.lower(): k for k, v in RUNE_POOL_NAMES.items()}


def resolve_rune_pool(name: str) -> str | None:
    """Resolve a rune name or pool name to a valid pool name.

    Accepts: "marksman", "Kolr's Hunt", "kolrs hunt", "decay", etc.
    Returns the pool name (e.g. "marksman") or None if unrecognized.
    """
    name_lower = name.lower().strip()
    if name_lower in RUNE_POOL_NAMES:
        return name_lower
    # Try display name match
    if name_lower in RUNE_NAME_TO_POOL:
        return RUNE_NAME_TO_POOL[name_lower]
    # Fuzzy: strip apostrophes and extra spaces
    normalized = name_lower.replace("'", "").replace("'", "").replace("  ", " ")
    for display, pool in RUNE_NAME_TO_POOL.items():
        if normalized == display.replace("'", "").replace("'", ""):
            return pool
    return None


def recommend_runes(
    item_class: str,
    ilvl: int,
    target_families: list[str],
) -> list[dict]:
    """Recommend which runes to socket for a crafting goal.

    Analyzes all 6 rune pools against the target mod families and reports:
    - Which pools contain target families (direct hits)
    - How many extra mods each pool adds (dilution)
    - Net probability impact

    Args:
        item_class: poe2db item class slug (e.g. "Gloves_int")
        ilvl: item level
        target_families: list of target mod family names

    Returns:
        List of dicts sorted by recommendation strength (best first), each with:
        - pool_name, rune_name, verdict (RECOMMENDED/NEUTRAL/AVOID)
        - target_hits: families in this pool that match targets
        - extra_prefixes, extra_suffixes: mod count added to pool
        - total_extra_weight: total weight added
        - probability_impact: estimated % change in hitting any target
    """
    from poe2_crafting_mcp.data.price_db import PriceDatabase
    pdb = PriceDatabase()

    # Get the base normal pool
    normal_pool = pdb.get_craftable_mods(item_class, ilvl, pool="normal")
    normal_prefix_weight = normal_pool.get("total_prefix_weight", 0)
    normal_suffix_weight = normal_pool.get("total_suffix_weight", 0)

    # Find target weights in the normal pool
    target_set = set(target_families)
    normal_target_prefix_weight = 0
    normal_target_suffix_weight = 0
    for group in normal_pool.get("prefixes", []):
        if group["family"] in target_set:
            normal_target_prefix_weight += sum(t["weight"] for t in group["tiers"])
    for group in normal_pool.get("suffixes", []):
        if group["family"] in target_set:
            normal_target_suffix_weight += sum(t["weight"] for t in group["tiers"])

    results = []
    for pool_name, rune_name in RUNE_POOL_NAMES.items():
        rune_pool = pdb.get_craftable_mods(item_class, ilvl, pool=pool_name)

        prefixes = rune_pool.get("prefixes", [])
        suffixes = rune_pool.get("suffixes", [])

        if not prefixes and not suffixes:
            continue

        # Count mods and weights added
        extra_prefix_count = sum(len(g["tiers"]) for g in prefixes)
        extra_suffix_count = sum(len(g["tiers"]) for g in suffixes)
        extra_prefix_weight = sum(t["weight"] for g in prefixes for t in g["tiers"])
        extra_suffix_weight = sum(t["weight"] for g in suffixes for t in g["tiers"])

        # Find target hits
        target_hits = []
        rune_target_prefix_weight = 0
        rune_target_suffix_weight = 0
        for group in prefixes:
            if group["family"] in target_set:
                family_weight = sum(t["weight"] for t in group["tiers"])
                target_hits.append({
                    "family": group["family"],
                    "affix_type": "prefix",
                    "tiers": len(group["tiers"]),
                    "weight": family_weight,
                })
                rune_target_prefix_weight += family_weight
        for group in suffixes:
            if group["family"] in target_set:
                family_weight = sum(t["weight"] for t in group["tiers"])
                target_hits.append({
                    "family": group["family"],
                    "affix_type": "suffix",
                    "tiers": len(group["tiers"]),
                    "weight": family_weight,
                })
                rune_target_suffix_weight += family_weight

        # All rune families (for display)
        rune_families = []
        for group in prefixes:
            rune_families.append({"family": group["family"], "affix_type": "prefix",
                                  "tiers": len(group["tiers"])})
        for group in suffixes:
            rune_families.append({"family": group["family"], "affix_type": "suffix",
                                  "tiers": len(group["tiers"])})

        # Calculate probability impact
        # P(target) = target_weight / total_weight
        # With rune: P(target) = (target_weight + rune_target_weight) / (total_weight + rune_weight)
        prob_change_prefix = 0.0
        prob_change_suffix = 0.0
        if normal_prefix_weight > 0:
            p_before = normal_target_prefix_weight / normal_prefix_weight
            p_after = (normal_target_prefix_weight + rune_target_prefix_weight) / (
                normal_prefix_weight + extra_prefix_weight)
            prob_change_prefix = p_after - p_before
        if normal_suffix_weight > 0:
            p_before = normal_target_suffix_weight / normal_suffix_weight
            p_after = (normal_target_suffix_weight + rune_target_suffix_weight) / (
                normal_suffix_weight + extra_suffix_weight)
            prob_change_suffix = p_after - p_before

        net_prob_change = prob_change_prefix + prob_change_suffix

        # Verdict
        if target_hits:
            verdict = "RECOMMENDED"
        elif net_prob_change >= -0.001:
            verdict = "NEUTRAL"
        else:
            verdict = "AVOID"

        results.append({
            "pool_name": pool_name,
            "rune_name": rune_name,
            "verdict": verdict,
            "target_hits": target_hits,
            "rune_families": rune_families,
            "extra_prefixes": extra_prefix_count,
            "extra_suffixes": extra_suffix_count,
            "total_extra_weight": extra_prefix_weight + extra_suffix_weight,
            "probability_impact_pct": round(net_prob_change * 100, 3),
        })

    # Sort: RECOMMENDED first, then by probability impact descending
    verdict_order = {"RECOMMENDED": 0, "NEUTRAL": 1, "AVOID": 2}
    results.sort(key=lambda r: (verdict_order[r["verdict"]], -r["probability_impact_pct"]))

    return results


class CraftingSimulator:
    """
    Crafting state machine with probability calculation.

    Tracks item state, applies currency operations, and calculates
    exact probabilities for hitting target mods.
    """

    def __init__(
        self,
        item_class: str,
        ilvl: int,
        mod_pool: dict,
        essence_pool: dict | None = None,
        rune_pools: list[str] | None = None,
        rune_pool_data: list[dict] | None = None,
    ):
        """
        Args:
            item_class: poe2db item class (e.g. "Gloves_int")
            ilvl: item level
            mod_pool: result from PriceDatabase.get_craftable_mods()
                      Must include 'prefixes' and 'suffixes' with tier data.
            essence_pool: optional result from get_craftable_mods(pool='essence')
                          If None, _find_essence_mod falls back to normal pool.
                          Should include both 'essence' and 'perfect_essence' mods.
            rune_pools: list of rune pool names to load from DB (e.g. ["marksman", "decay"]).
                        These expand the rolling pool — rune mods are added to the normal pool.
            rune_pool_data: pre-loaded rune pool data (list of get_craftable_mods() results).
                            Use instead of rune_pools when data is already loaded.
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
        # All 3 items must be same rarity. Output matches input rarity.
        self.reforge_stock: dict[str, int] = {"Magic": 0, "Rare": 0}  # per-rarity counts

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

        # Flatten rune pool mods (added to normal pool when rolling)
        # Rune mods expand the available pool — they don't replace normal mods.
        # A family can appear in both normal and rune pools (different tiers/weights).
        self._rune_mods: list[dict] = []
        self._active_rune_pools: list[str] = rune_pools or []

        rune_data_list = rune_pool_data or []
        if rune_pools and not rune_pool_data:
            # Load from DB on demand
            rune_data_list = self._load_rune_pools(rune_pools)

        for pool_data in rune_data_list:
            for group in pool_data.get('prefixes', []):
                for tier_idx, tier in enumerate(group['tiers']):
                    self._rune_mods.append({
                        'family': group['family'],
                        'affix_type': 'prefix',
                        'tier': tier_idx + 1,
                        'req_level': tier['req_level'],
                        'weight': tier['weight'],
                        'stat_text': tier['stat_text'],
                        'tags': tier.get('tags', []),
                    })
            for group in pool_data.get('suffixes', []):
                for tier_idx, tier in enumerate(group['tiers']):
                    self._rune_mods.append({
                        'family': group['family'],
                        'affix_type': 'suffix',
                        'tier': tier_idx + 1,
                        'req_level': tier['req_level'],
                        'weight': tier['weight'],
                        'stat_text': tier['stat_text'],
                        'tags': tier.get('tags', []),
                    })

    def _load_rune_pools(self, rune_pools: list[str]) -> list[dict]:
        """Load rune pool data from the database."""
        from poe2_crafting_mcp.data.price_db import PriceDatabase
        pdb = PriceDatabase()
        result = []
        for pool_name in rune_pools:
            pool_data = pdb.get_craftable_mods(self.item_class, ilvl=self.ilvl, pool=pool_name)
            if pool_data['prefixes'] or pool_data['suffixes']:
                result.append(pool_data)
        return result

    @classmethod
    def from_db(
        cls,
        item_class: str,
        ilvl: int,
        db_path: str = "data/poe2_craft.db",
        rune_pools: list[str] | None = None,
    ) -> "CraftingSimulator":
        """Create a simulator with all pools loaded from the database.

        Loads the normal pool for rolling + combined essence/perfect_essence
        pool for essence-guaranteed mods. Optionally loads rune pools that
        expand the rolling pool (e.g. "marksman", "decay").

        Args:
            item_class: poe2db item class (e.g. "Gloves_int")
            ilvl: item level
            db_path: path to SQLite database
            rune_pools: list of rune pool names to merge into the rolling pool.
                        Valid pools: marksman, decay, chronomancy, destruction,
                        berserking, soul.
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

        # Load rune pools if specified
        rune_pool_data = None
        if rune_pools:
            rune_pool_data = []
            for pool_name in rune_pools:
                pool_data = pdb.get_craftable_mods(item_class, ilvl=ilvl, pool=pool_name)
                if pool_data['prefixes'] or pool_data['suffixes']:
                    rune_pool_data.append(pool_data)

        return cls(item_class, ilvl, normal_pool, essence_pool=merged_essence,
                   rune_pool_data=rune_pool_data, rune_pools=rune_pools)

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

        If rune pools are active, their mods are merged into the normal pool.
        A family can appear in both normal and rune pools with different
        tiers/weights — all entries are included (the game rolls one flat pool).
        """
        item = item or self.item
        blocked_families = item.families_on_item
        prefixes_full = item.open_prefixes == 0
        suffixes_full = item.open_suffixes == 0

        # Combine normal + rune mods into one source
        all_sources = self._all_mods
        if self._rune_mods:
            all_sources = self._all_mods + self._rune_mods

        available = []
        for mod in all_sources:
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
        self, min_mod_level: int = 0, gentype_only: int = 0,
    ) -> ModInstance | None:
        """Roll a random mod from the available pool (for simulation).

        Args:
            min_mod_level: minimum req_level filter (Greater/Perfect currencies)
            gentype_only: 1=prefix only, 2=suffix only, 0=both
        """
        pool = self.get_available_pool(min_mod_level=min_mod_level, gentype_only=gentype_only)

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

        # Validate: corrupted items can't be modified (except scour/stash which are conceptual resets)
        op = cur["op"]
        if self.item.corrupted and op not in ("scour", "architect_corrupt"):
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
            if "qty_override" in omen_def:
                qty = omen_def["qty_override"]

        min_lv = cur.get("min_lv", 0)

        # Rarity change
        if "to_rarity" in cur:
            self.item.rarity = cur["to_rarity"]

        if op == "add":
            # Rarity change happens before add (e.g. transmute: Normal→Magic then add)
            if self.item.open_affixes == 0 and "to_rarity" not in cur:
                raise ValueError(f"No open affix slots ({len(self.item.mods)} mods, item is full)")
            for _ in range(qty):
                if self.item.open_affixes == 0:
                    break
                mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
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
            mod = self.roll_mod(min_mod_level=min_lv, gentype_only=gentype_only)
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
            # "Scour" = discard current mods, start over with this base.
            # This is a conceptual reset, not a PoE2 currency (Orb of Scouring doesn't exist).
            # Works even on corrupted items (you're discarding it as reforge fodder).
            self.item.mods = [m for m in self.item.mods if m.fractured]
            self.item.rarity = "Normal"
            self.item.essence_mod_family = None
            self.item.corrupted = False
            self.item.corruption_enchantment = ""
            self.item.implicits = []

        elif op == "reforge":
            # Reforging bench: 3-to-1. Current item + 2 from stock → new item.
            # All 3 must be same rarity. Output = same rarity with new random mods.
            item_rarity = self.item.rarity
            if item_rarity not in ("Magic", "Rare"):
                raise ValueError(
                    f"Reforge requires a Magic or Rare item (current is {item_rarity})"
                )
            stock_count = self.reforge_stock.get(item_rarity, 0)
            if stock_count < 2:
                raise ValueError(
                    f"Reforge requires 2 spare {item_rarity} bases in stock "
                    f"(have {stock_count}). Use 'stash' to add failed items."
                )
            self.reforge_stock[item_rarity] -= 2
            # Reset item completely (all mods gone, reroll)
            self.item.mods = [m for m in self.item.mods if m.fractured]
            self.item.essence_mod_family = None
            # Output: same rarity, 4 mods for Rare, 2 mods for Magic
            target_mods = 4 if item_rarity == "Rare" else 2
            for _ in range(target_mods):
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
            # Divine Orb: reroll numeric values of ALL mods within their tier ranges
            for mod in self.item.mods:
                if not mod.fractured:  # fractured mods can't be divined
                    mod.divine()

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
                # Reroll: removes all non-fractured mods, fills with new random mods
                # Makes the item Rare with full prefixes and suffixes (6 mods)
                self.item.mods = [m for m in self.item.mods if m.fractured]
                self.item.rarity = "Rare"
                # Fill to 6 mods (3 prefix + 3 suffix)
                while self.item.open_affixes > 0:
                    new_mod = self.roll_mod()
                    if new_mod:
                        self.item.mods.append(new_mod)
                    else:
                        break

            elif outcome == "enchantment":
                # Add a Vaal corruption implicit (doesn't take a prefix/suffix slot)
                implicit = self._roll_corruption_implicit()
                if implicit:
                    self.item.implicits.append(implicit)

            elif outcome == "socket":
                # Add +1 socket beyond normal max
                self.item.max_sockets += 1
                self.item.sockets.append("")
            # "nothing" and "nothing_socket" — only corrupted tag added

        elif op == "architect_corrupt":
            # Architect's Orb: requires already-corrupted item
            # 50% chance to add second corruption implicit, 50% destroy
            if not self.item.corrupted:
                raise ValueError("Architect's Orb requires a corrupted item")
            if random.random() < 0.5:
                # Success: add second implicit
                implicit = self._roll_corruption_implicit()
                if implicit:
                    self.item.implicits.append(implicit)
            else:
                # Failure: item destroyed
                raise ValueError("DESTROYED — Architect's Orb failed (50% chance)")

        return self.item


    def stash_for_reforge(self) -> None:
        """Stash current item as a spare base for reforging.

        Increments reforge_stock for the item's current rarity and resets to Normal.
        Used when a craft attempt fails and the item should be recycled.
        Only Magic and Rare items can be stashed (Normal has nothing to reforge).
        """
        rarity = self.item.rarity
        if rarity not in ("Magic", "Rare"):
            raise ValueError(f"Can only stash Magic or Rare items for reforging (item is {rarity})")
        self.reforge_stock[rarity] = self.reforge_stock.get(rarity, 0) + 1
        self.item = ItemState(
            item_class=self.item_class,
            ilvl=self.ilvl,
            rarity="Normal",
            max_sockets=get_max_sockets_for_item_class(self.item_class),
        )

    def buy_base(self, count: int = 1, rarity: str = "Rare") -> None:
        """Buy bases and add to reforge stock for a specific rarity.

        Represents purchasing items from trade to fuel reforging.
        Cost tracking is handled by the caller (optimizer/CLI).
        """
        if rarity not in ("Magic", "Rare"):
            raise ValueError(f"Can only buy Magic or Rare bases for reforging")
        self.reforge_stock[rarity] = self.reforge_stock.get(rarity, 0) + count


    def _roll_corruption_implicit(self) -> ModInstance | None:
        """Roll a random Vaal implicit from the corrupted pool for this item class."""
        from poe2_crafting_mcp.data.price_db import PriceDatabase
        try:
            pdb = PriceDatabase()
            rows = pdb._conn.execute(
                "SELECT mod_family, stat_text, req_level FROM mod_weights "
                "WHERE pool = 'corrupted' AND item_class = ? AND req_level <= ?",
                (self.item_class, self.ilvl),
            ).fetchall()
            if rows:
                row = random.choice(rows)
                return ModInstance(
                    family=row[0],
                    affix_type="implicit",
                    tier=1,
                    req_level=row[2],
                    weight=1,
                    stat_text=row[1],
                )
        except Exception:
            pass
        return None

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
        """Essence upgrade: Magic → Rare with guaranteed mod (no random fill).

        All essence tiers (Lesser/Normal/Greater) work the same:
        - Requires Magic item
        - Upgrades to Rare
        - Keeps existing Magic mods (1-2)
        - Adds 1 guaranteed essence mod
        - Result: 2-3 mods total (no random fill)

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
                # Track removed mod's level for Abyss mark tier upgrade
                if essence_family == "EssenceAbyss":
                    self.item.abyss_mark_min_level = to_remove.req_level
                self.item.mods.remove(to_remove)

        # Add guaranteed essence mod
        essence_mod = self._find_essence_mod(essence_family, essence_stat_text)
        if essence_mod:
            self.item.mods.append(essence_mod)
            self.item.essence_mod_family = essence_family

        # Special: Essence of the Abyss sets the mark flag
        if essence_family == "EssenceAbyss":
            self.item.has_abyss_mark = True

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
