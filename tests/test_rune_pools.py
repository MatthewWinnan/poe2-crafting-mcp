"""Tests for rune pool merging in the crafting simulator and optimizer.

Verifies that socketed runes correctly expand the mod pool for crafting,
that family blocking works across merged pools, and that probability
calculations reflect the expanded pool.
"""

import numpy as np
import pytest

from poe2_crafting_mcp.crafting.simulator import (
    CraftingSimulator,
    RUNE_POOL_NAMES,
    RUNE_NAME_TO_POOL,
    resolve_rune_pool,
)


# ── Rune Name Resolution ────────────────────────────────────────────────────

class TestRuneNameResolution:
    def test_pool_names_resolve(self):
        """Pool names resolve to themselves."""
        for pool_name in RUNE_POOL_NAMES:
            assert resolve_rune_pool(pool_name) == pool_name

    def test_display_names_resolve(self):
        """Display names resolve to pool names."""
        assert resolve_rune_pool("Kolr's Hunt") == "marksman"
        assert resolve_rune_pool("Katla's Gloom") == "decay"
        assert resolve_rune_pool("Uhtred's Sidereus") == "chronomancy"
        assert resolve_rune_pool("Thrud's Might") == "destruction"
        assert resolve_rune_pool("Vorana's Carnage") == "berserking"
        assert resolve_rune_pool("Medved's Tending") == "soul"

    def test_case_insensitive(self):
        """Resolution is case-insensitive."""
        assert resolve_rune_pool("MARKSMAN") == "marksman"
        assert resolve_rune_pool("kolr's hunt") == "marksman"

    def test_fuzzy_apostrophe(self):
        """Apostrophe-less names resolve correctly."""
        assert resolve_rune_pool("Kolrs Hunt") == "marksman"
        assert resolve_rune_pool("katlas gloom") == "decay"

    def test_unknown_returns_none(self):
        """Unknown rune names return None."""
        assert resolve_rune_pool("invalid") is None
        assert resolve_rune_pool("") is None

    def test_all_six_pools_mapped(self):
        """All 6 rune pools have display names."""
        assert len(RUNE_POOL_NAMES) == 6
        assert len(RUNE_NAME_TO_POOL) == 6


# ── Simulator Pool Merging ───────────────────────────────────────────────────

def _make_normal_pool():
    """Minimal normal pool for testing."""
    return {
        "prefixes": [
            {
                "family": "IncreasedLife",
                "affix_type": "prefix",
                "family_weight": 3000,
                "tiers": [
                    {"stat_text": "+100 life", "weight": 1000, "req_level": 70, "tags": []},
                    {"stat_text": "+80 life", "weight": 1000, "req_level": 50, "tags": []},
                    {"stat_text": "+60 life", "weight": 1000, "req_level": 30, "tags": []},
                ],
            },
        ],
        "suffixes": [
            {
                "family": "FireResistance",
                "affix_type": "suffix",
                "family_weight": 2000,
                "tiers": [
                    {"stat_text": "+40% fire res", "weight": 1000, "req_level": 60, "tags": []},
                    {"stat_text": "+30% fire res", "weight": 1000, "req_level": 30, "tags": []},
                ],
            },
        ],
    }


def _make_rune_pool():
    """Minimal rune pool data for testing."""
    return {
        "prefixes": [
            {
                "family": "IgniteEffect",
                "affix_type": "prefix",
                "family_weight": 2,
                "tiers": [
                    {"stat_text": "+50% ignite", "weight": 1, "req_level": 75, "tags": []},
                    {"stat_text": "+30% ignite", "weight": 1, "req_level": 45, "tags": []},
                ],
            },
        ],
        "suffixes": [
            {
                "family": "WitheredEffect",
                "affix_type": "suffix",
                "family_weight": 2,
                "tiers": [
                    {"stat_text": "+35% wither", "weight": 1, "req_level": 75, "tags": []},
                    {"stat_text": "+20% wither", "weight": 1, "req_level": 45, "tags": []},
                ],
            },
        ],
    }


class TestSimulatorRunePoolMerging:
    def test_no_runes_baseline(self):
        """Without runes, pool has only normal mods."""
        sim = CraftingSimulator("Gloves_int", 82, _make_normal_pool())
        pool = sim.get_available_pool()
        families = {m["family"] for m in pool}
        assert "IncreasedLife" in families
        assert "IgniteEffect" not in families

    def test_rune_pool_expands_pool(self):
        """Rune pool mods are added to the available pool."""
        sim = CraftingSimulator(
            "Gloves_int", 82, _make_normal_pool(),
            rune_pool_data=[_make_rune_pool()],
        )
        pool = sim.get_available_pool()
        families = {m["family"] for m in pool}
        assert "IncreasedLife" in families
        assert "IgniteEffect" in families
        assert "WitheredEffect" in families

    def test_rune_pool_increases_pool_size(self):
        """Rune pool adds mods to the total pool size."""
        sim_normal = CraftingSimulator("Gloves_int", 82, _make_normal_pool())
        sim_rune = CraftingSimulator(
            "Gloves_int", 82, _make_normal_pool(),
            rune_pool_data=[_make_rune_pool()],
        )
        normal_size = len(sim_normal.get_available_pool())
        rune_size = len(sim_rune.get_available_pool())
        assert rune_size > normal_size

    def test_rune_pool_total_weight_increases(self):
        """Total weight increases when rune pool is merged."""
        sim_normal = CraftingSimulator("Gloves_int", 82, _make_normal_pool())
        sim_rune = CraftingSimulator(
            "Gloves_int", 82, _make_normal_pool(),
            rune_pool_data=[_make_rune_pool()],
        )
        normal_weight = sum(m["weight"] for m in sim_normal.get_available_pool())
        rune_weight = sum(m["weight"] for m in sim_rune.get_available_pool())
        assert rune_weight > normal_weight

    def test_family_blocking_works_across_pools(self):
        """Family blocking excludes rune mods when family is on item."""
        sim = CraftingSimulator(
            "Gloves_int", 82, _make_normal_pool(),
            rune_pool_data=[_make_rune_pool()],
        )
        # Place IgniteEffect on the item
        sim.set_item_mods(["IgniteEffect"])
        sim.set_item_rarity("Rare")
        pool = sim.get_available_pool()
        families = {m["family"] for m in pool}
        assert "IgniteEffect" not in families
        assert "IncreasedLife" in families  # other mods still available

    def test_probability_of_rune_mod(self):
        """Can calculate probability for a rune-only mod."""
        sim = CraftingSimulator(
            "Gloves_int", 82, _make_normal_pool(),
            rune_pool_data=[_make_rune_pool()],
        )
        sim.set_item_rarity("Rare")
        prob = sim.probability_of("IgniteEffect", "exalted")
        assert prob["probability"] > 0
        assert prob["target_weight"] > 0

    def test_probability_zero_without_rune(self):
        """Rune-only mods have 0% probability without the rune equipped."""
        sim = CraftingSimulator("Gloves_int", 82, _make_normal_pool())
        sim.set_item_rarity("Rare")
        prob = sim.probability_of("IgniteEffect", "exalted")
        assert prob["probability"] == 0

    def test_multiple_rune_pools(self):
        """Multiple rune pools stack additively."""
        rune_pool_2 = {
            "prefixes": [
                {
                    "family": "ProjectileDamage",
                    "affix_type": "prefix",
                    "family_weight": 2,
                    "tiers": [
                        {"stat_text": "+30% proj", "weight": 1, "req_level": 65, "tags": []},
                    ],
                },
            ],
            "suffixes": [],
        }
        sim = CraftingSimulator(
            "Gloves_int", 82, _make_normal_pool(),
            rune_pool_data=[_make_rune_pool(), rune_pool_2],
        )
        pool = sim.get_available_pool()
        families = {m["family"] for m in pool}
        assert "IgniteEffect" in families
        assert "ProjectileDamage" in families
        assert "IncreasedLife" in families


# ── Database Integration (requires real DB) ──────────────────────────────────

def _db_available():
    import os
    return os.path.exists("data/poe2_craft.db")


@pytest.mark.skipif(not _db_available(), reason="poe2_craft.db not available")
class TestRunePoolDB:
    def test_from_db_with_runes(self):
        """CraftingSimulator.from_db loads rune pools from DB."""
        sim = CraftingSimulator.from_db("Gloves_int", 82, rune_pools=["decay"])
        assert len(sim._rune_mods) > 0
        rune_families = {m["family"] for m in sim._rune_mods}
        assert "IgniteEffect" in rune_families or "BleedingDamage" in rune_families

    def test_from_db_without_runes(self):
        """Without runes, no rune mods loaded."""
        sim = CraftingSimulator.from_db("Gloves_int", 82)
        assert len(sim._rune_mods) == 0

    def test_pool_size_increases_with_decay(self):
        """Decay rune measurably increases pool size."""
        sim_normal = CraftingSimulator.from_db("Gloves_int", 82)
        sim_decay = CraftingSimulator.from_db("Gloves_int", 82, rune_pools=["decay"])
        normal_pool = sim_normal.get_available_pool()
        decay_pool = sim_decay.get_available_pool()
        assert len(decay_pool) > len(normal_pool)

    def test_preflight_with_runes(self):
        """Optimizer preflight merges rune pools into flat arrays."""
        from poe2_crafting_mcp.crafting.optimizer.preflight import preflight
        pool_normal, _, _ = preflight("Gloves_int", 82,
                                       [("IncreasedEnergyShield", "prefix", 1)])
        pool_decay, _, _ = preflight("Gloves_int", 82,
                                      [("IncreasedEnergyShield", "prefix", 1)],
                                      rune_pools=["decay"])
        assert len(pool_decay["prefix_weights"]) > len(pool_normal["prefix_weights"])
        assert len(pool_decay["suffix_weights"]) > len(pool_normal["suffix_weights"])
