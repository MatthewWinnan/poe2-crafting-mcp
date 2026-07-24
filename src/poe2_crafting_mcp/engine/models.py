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

    # Defence
    life: float = 0.0
    energy_shield: float = 0.0
    mana: float = 0.0
    evasion: float = 0.0
    armour: float = 0.0

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
    explicit_mods: list[str] = field(default_factory=list)
    implicit_mods: list[str] = field(default_factory=list)
    raw_text: str = ""
