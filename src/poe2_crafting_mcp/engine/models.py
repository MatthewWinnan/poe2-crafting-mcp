"""Data models for the PoB engine module."""

from dataclasses import dataclass, field


@dataclass
class BuildStats:
    """Core output stats from a PoB calculation."""

    # Offence
    total_dps: float = 0.0
    crit_chance: float = 0.0
    crit_multiplier: float = 0.0
    hit_chance: float = 0.0
    speed: float = 0.0

    # Damage breakdown by type
    phys_dps: float = 0.0
    fire_dps: float = 0.0
    cold_dps: float = 0.0
    lightning_dps: float = 0.0
    chaos_dps: float = 0.0

    # Defence
    life: float = 0.0
    energy_shield: float = 0.0
    ward: float = 0.0
    mana: float = 0.0
    evasion: float = 0.0
    armour: float = 0.0
    block_chance: float = 0.0
    spell_block_chance: float = 0.0

    # Resistances
    fire_res: float = 0.0
    cold_res: float = 0.0
    lightning_res: float = 0.0
    chaos_res: float = 0.0


@dataclass
class BuildInfo:
    """Metadata about the loaded build."""

    name: str = ""
    class_name: str = ""
    ascendancy: str = ""
    level: int = 0
    main_skill: str = ""
    # Passive tree overview
    total_allocated: int = 0
    keystone_count: int = 0
    notable_count: int = 0


@dataclass
class GemInstance:
    """A single gem socketed in a skill group."""

    name: str
    level: int
    quality: int
    is_support: bool
    corrupted: bool = False
    corrupt_level: int = 0  # signed — e.g. +1 or -1 on corruption
    enabled: bool = True


@dataclass
class SocketGroup:
    """A socket group (skill link) in the skills tab."""

    label: str
    slot: str          # equipment slot it's in, e.g. "Weapon 1"
    enabled: bool
    include_in_full_dps: bool
    gems: list[GemInstance] = field(default_factory=list)


@dataclass
class DPSDelta:
    """Result of comparing stats before and after a change."""

    before: BuildStats
    after: BuildStats

    @property
    def dps_change(self) -> float:
        return self.after.total_dps - self.before.total_dps

    @property
    def dps_change_percent(self) -> float:
        if self.before.total_dps == 0:
            return 0.0
        return (self.dps_change / self.before.total_dps) * 100

    @property
    def es_change(self) -> float:
        return self.after.energy_shield - self.before.energy_shield

    @property
    def life_change(self) -> float:
        return self.after.life - self.before.life


@dataclass
class EquippedItem:
    """Summary of an item in a slot."""

    slot: str
    name: str
    base_type: str
    rarity: str
    item_level: int
    quality: int = 0
    corrupted: bool = False
    explicit_mods: list[str] = field(default_factory=list)
    implicit_mods: list[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class TreeJewel:
    """A jewel socketed in the passive tree."""

    node_id: int
    node_name: str           # passive tree node display name (e.g. "Jewel Socket")
    node_x: float            # approximate x position on tree (for spatial context)
    node_y: float            # approximate y position on tree
    name: str                # item name (unique name or magic prefix/suffix)
    base_type: str           # base type (e.g. "Viridian Jewel")
    corrupted: bool = False
    explicit_mods: list[str] = field(default_factory=list)


# ── Combat Profile ─────────────────────────────────────────────────────────────


@dataclass
class ChargeInfo:
    """A charge type available to the build."""

    current: int        # amount configured in the scenario (0 if not enabled)
    maximum: int        # max charges the build can have
    configured: bool    # whether "usePowerCharges" / "useFrenzyCharges" etc. is set


@dataclass
class AilmentInfo:
    """An ailment the build can apply to enemies."""

    ailment: str              # "Shock", "Ignite", "Chill", "Freeze", "Poison", "Bleed"
    chance_percent: float     # per-hit application chance (may exceed 100 for guaranteed)
    magnitude: float          # shock = % increased damage taken; ignite/poison/bleed = DPS
    duration_seconds: float
    stack_max: int = 1        # max simultaneous stacks


@dataclass
class ConfigOptionInfo:
    """A single PoB config option that is relevant to the loaded build."""

    var: str
    var_type: str                                  # "check", "count", "list", "countAllowZero", "integer"
    label: str                                     # human-readable label (ANSI codes stripped)
    tooltip: str                                   # explanation of what it does
    current_value: bool | int | float | str | None # None = not set (PoB uses default)
    list_options: list[tuple[str, str]] | None = None  # (value, label) pairs for list types


@dataclass
class CombatProfile:
    """
    Full combat scenario profile for a loaded build.

    Designed for agent consumption — contains everything needed to evaluate
    what scenario assumptions are active, what buffs/ailments are available,
    and what config knobs exist to tune the scenario.
    """

    # ── Current DPS (reflects active config) ──────────────────────────────────
    total_dps: float

    # ── Charges ─────���─────────────────────────────────────────────────────────
    # Keys: "Power", "Frenzy", "Endurance", "Blood", "Inspiration", etc.
    charges: dict[str, ChargeInfo]

    # ── Rage ───────────────────────────────────���──────────────────────────────
    rage_available: bool        # build can gain rage
    rage_max: int
    rage_current: int           # configured amount (0 if not set)
    rage_effect_per_stack: float  # % more attack damage per stack (usually 1%)

    # ── Ailments applied to enemies ──────��────────────────────────────────────
    ailments_on_enemy: list[AilmentInfo]

    # ── Defence ───────────────────────────────────────────────────────────────
    life: float
    energy_shield: float
    evasion: float
    armour: float
    fire_res: float
    cold_res: float
    lightning_res: float
    chaos_res: float
    # Multiplier vs each incoming damage type after all mitigation (1.0 = no mitigation)
    # Keys: "Physical", "Fire", "Cold", "Lightning", "Chaos"
    damage_taken_mults: dict[str, float]

    # ── Damage Type Breakdown ─────────────────────────────────────────────────
    # % of total hit damage per element (Physical/Fire/Cold/Lightning/Chaos).
    # Tells the agent: which Trinity resonance builds fastest, which penetration
    # investments matter, which exposures/debuffs are worth applying.
    damage_type_percent: dict[str, float]

    # ── Scenario Config ───────────────────────────────────────────────────────
    # All config options relevant to this build, with their current values.
    # Grouped by category key: "charges", "buffs", "enemy", "conditions", "modes", "other"
    relevant_config: dict[str, list[ConfigOptionInfo]]
