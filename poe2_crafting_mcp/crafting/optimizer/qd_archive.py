"""MAP-Elites Quality-Diversity archive for the crafting optimizer.

Maintains a grid of elite strategies indexed by behavioral descriptors,
ensuring the optimizer discovers diverse strategy families (not just
200 variants of alt-regal).

Design informed by:
- Mouret & Clune (2015): MAP-Elites original paper
- Deep-Grid MAP-Elites (2020): noise handling for stochastic domains
- BASIL (2025): QD archive for rule-based policy evolution

Grid axes (48 cells total):
  - Primary early currency (4): transmute, alchemy, chaos, essence
  - Restart aggressiveness (4): <100c, 100-300c, 300-600c, >600c
  - Omen usage (3): none, light (1-2), heavy (3+)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .gene import Individual, RuleList


# ── Behavioral Descriptor Bucketing ───────────────────────────────────────────

# Axis 1: Primary early currency
EARLY_CURRENCY_BUCKETS = ["transmute", "alchemy", "chaos", "essence"]

# Axis 2: Restart threshold buckets (cost_spent_gte value on first restart rule)
RESTART_THRESHOLDS = [100.0, 300.0, 600.0]  # boundaries → 4 buckets

# Axis 3: Omen count buckets
OMEN_BUCKETS = [0, 1, 3]  # 0=none, 1-2=light, 3+=heavy → 3 buckets

# Grid dimensions
N_EARLY = len(EARLY_CURRENCY_BUCKETS)   # 4
N_RESTART = len(RESTART_THRESHOLDS) + 1  # 4
N_OMEN = len(OMEN_BUCKETS)              # 3
GRID_SIZE = N_EARLY * N_RESTART * N_OMEN  # 48


def _bucket_early_currency(rl: RuleList) -> int:
    """Map primary early currency to bucket index (0-3)."""
    name = rl.primary_early_currency
    if name in EARLY_CURRENCY_BUCKETS:
        return EARLY_CURRENCY_BUCKETS.index(name)
    # Default to "transmute" bucket for unknown
    return 0


def _bucket_restart(rl: RuleList) -> int:
    """Map restart threshold to bucket index (0-3)."""
    threshold = rl.restart_threshold
    for i, boundary in enumerate(RESTART_THRESHOLDS):
        if threshold < boundary:
            return i
    return len(RESTART_THRESHOLDS)  # last bucket (>600c)


def _bucket_omen(rl: RuleList) -> int:
    """Map omen count to bucket index (0-2)."""
    count = rl.omen_count
    if count == 0:
        return 0
    elif count <= 2:
        return 1
    else:
        return 2


def compute_descriptor(rl: RuleList) -> tuple[int, int, int]:
    """Compute the 3D behavioral descriptor for a rule-list."""
    return (
        _bucket_early_currency(rl),
        _bucket_restart(rl),
        _bucket_omen(rl),
    )


def descriptor_to_index(desc: tuple[int, int, int]) -> int:
    """Flatten 3D descriptor to a linear cell index."""
    return desc[0] * (N_RESTART * N_OMEN) + desc[1] * N_OMEN + desc[2]


def index_to_descriptor(idx: int) -> tuple[int, int, int]:
    """Convert linear index back to 3D descriptor."""
    early = idx // (N_RESTART * N_OMEN)
    remainder = idx % (N_RESTART * N_OMEN)
    restart = remainder // N_OMEN
    omen = remainder % N_OMEN
    return (early, restart, omen)


# ── QD Archive ────────────────────────────────────────────────────────────────

# Noise margin: only replace incumbent if new fitness is significantly better
# This prevents MC noise from churning good solutions out (Deep-Grid insight)
REPLACEMENT_MARGIN = 0.05  # 5% improvement required to replace


@dataclass
class QDArchive:
    """MAP-Elites grid archive for strategy diversity.

    Each cell stores the best individual whose behavioral descriptor maps
    to that cell. The archive persists across the entire optimization run,
    serving as long-term memory of diverse high-performing strategies.
    """
    cells: list[Individual | None] = field(default_factory=lambda: [None] * GRID_SIZE)
    update_count: int = 0
    replacement_count: int = 0

    @property
    def occupancy(self) -> int:
        """Number of filled cells."""
        return sum(1 for c in self.cells if c is not None)

    @property
    def coverage(self) -> float:
        """Fraction of grid cells filled (0.0 to 1.0)."""
        return self.occupancy / GRID_SIZE

    def offer(self, individual: Individual) -> bool:
        """Offer an individual to the archive.

        Returns True if the individual was inserted (new cell or better fitness).
        Uses replacement margin to handle MC noise.
        """
        if individual.fitness.is_degenerate:
            return False

        desc = compute_descriptor(individual.rulelist)
        idx = descriptor_to_index(desc)
        self.update_count += 1

        incumbent = self.cells[idx]

        if incumbent is None:
            # Empty cell — always fill
            self.cells[idx] = individual
            return True

        # Replace only if significantly better (noise-resilient)
        new_cost = individual.fitness.expected_cost
        old_cost = incumbent.fitness.expected_cost

        if old_cost == float("inf"):
            # Incumbent is degenerate — always replace
            self.cells[idx] = individual
            self.replacement_count += 1
            return True

        # Require margin improvement on primary objective (expected_cost)
        if new_cost < old_cost * (1.0 - REPLACEMENT_MARGIN):
            self.cells[idx] = individual
            self.replacement_count += 1
            return True

        return False

    def offer_population(self, population: list[Individual]) -> int:
        """Offer entire population to archive. Returns number of insertions."""
        inserted = 0
        for ind in population:
            if self.offer(ind):
                inserted += 1
        return inserted

    def get_elites(self) -> list[Individual]:
        """Return all non-None elites in the archive."""
        return [c for c in self.cells if c is not None]

    def get_injection_set(self, n: int) -> list[Individual]:
        """Get n individuals from archive for injection into NSGA-II population.

        Returns the best individuals (by expected_cost) from filled cells.
        These get injected every few generations to re-seed diversity.
        """
        elites = self.get_elites()
        if not elites:
            return []

        # Sort by expected_cost (best first), take top n
        elites.sort(key=lambda ind: ind.fitness.expected_cost)
        return elites[:n]

    def get_cell_info(self, idx: int) -> dict | None:
        """Get info about a specific cell (for debugging/display)."""
        ind = self.cells[idx]
        if ind is None:
            return None

        desc = index_to_descriptor(idx)
        return {
            "descriptor": desc,
            "early_currency": EARLY_CURRENCY_BUCKETS[desc[0]],
            "restart_bucket": desc[1],
            "omen_bucket": desc[2],
            "expected_cost": ind.fitness.expected_cost,
            "success_rate": ind.fitness.success_rate,
            "rules": ind.rulelist.size,
        }

    def summary(self) -> str:
        """Human-readable archive summary."""
        elites = self.get_elites()
        if not elites:
            return "QD Archive: empty"

        lines = [
            f"QD Archive: {self.occupancy}/{GRID_SIZE} cells filled "
            f"({self.coverage:.0%} coverage)",
            f"  Updates: {self.update_count}, Replacements: {self.replacement_count}",
            f"  Best cost: {min(e.fitness.expected_cost for e in elites):.1f}c",
            f"  Strategy families discovered:",
        ]

        # Count per early-currency bucket
        by_early: dict[str, int] = {}
        for elite in elites:
            name = elite.rulelist.primary_early_currency
            by_early[name] = by_early.get(name, 0) + 1

        for name, count in sorted(by_early.items(), key=lambda x: -x[1]):
            lines.append(f"    {name}: {count} variants")

        return "\n".join(lines)
