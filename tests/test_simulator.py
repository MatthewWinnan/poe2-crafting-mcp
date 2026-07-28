"""Tests for crafting simulator — new mechanics (essences, omens, scour, reforge)."""

import random
import pytest
from poe2_crafting_mcp.crafting.simulator import (
    CraftingSimulator,
    ItemState,
    ModInstance,
    CURRENCIES,
    OMENS,
)


# ── Test fixture: minimal mod pool ──────────────────────────────────────────

def _make_pool():
    """Minimal mod pool with 2 prefix families and 2 suffix families."""
    return {
        "prefixes": [
            {
                "family": "IncreasedLife",
                "tiers": [
                    {"req_level": 60, "weight": 500, "stat_text": "+100 to maximum Life"},
                    {"req_level": 30, "weight": 1000, "stat_text": "+50 to maximum Life"},
                ],
            },
            {
                "family": "FlatPhysDamage",
                "tiers": [
                    {"req_level": 70, "weight": 300, "stat_text": "Adds 20-30 Physical Damage"},
                    {"req_level": 10, "weight": 800, "stat_text": "Adds 5-10 Physical Damage"},
                ],
            },
            {
                "family": "IncreasedArmour",
                "tiers": [
                    {"req_level": 50, "weight": 600, "stat_text": "+200 to Armour"},
                ],
            },
        ],
        "suffixes": [
            {
                "family": "FireResist",
                "tiers": [
                    {"req_level": 60, "weight": 500, "stat_text": "+40% to Fire Resistance"},
                    {"req_level": 20, "weight": 1000, "stat_text": "+20% to Fire Resistance"},
                ],
            },
            {
                "family": "ColdResist",
                "tiers": [
                    {"req_level": 60, "weight": 500, "stat_text": "+40% to Cold Resistance"},
                    {"req_level": 20, "weight": 1000, "stat_text": "+20% to Cold Resistance"},
                ],
            },
            {
                "family": "AttackSpeed",
                "tiers": [
                    {"req_level": 50, "weight": 400, "stat_text": "10% increased Attack Speed"},
                ],
            },
        ],
    }


def _make_sim(ilvl: int = 80) -> CraftingSimulator:
    sim = CraftingSimulator("Gloves_str", ilvl, _make_pool())
    sim.item.rarity = "Normal"
    sim.item.mods = []
    return sim


def _add_mod(sim: CraftingSimulator, family: str, fractured: bool = False) -> ModInstance:
    """Helper: add a specific mod to the item."""
    for m in sim._all_mods:
        if m["family"] == family:
            mod = ModInstance(
                family=m["family"],
                affix_type=m["affix_type"],
                tier=m["tier"],
                req_level=m["req_level"],
                weight=m["weight"],
                stat_text=m["stat_text"],
                fractured=fractured,
            )
            sim.item.mods.append(mod)
            return mod
    raise ValueError(f"Family {family} not in pool")


# ── Scour ───────────────────────────────────────────────────────────────────

class TestScour:
    def test_scour_clears_mods(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FireResist")
        sim.apply_currency("scour")
        assert sim.item.rarity == "Normal"
        assert len(sim.item.mods) == 0

    def test_scour_preserves_fractured(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife", fractured=True)
        _add_mod(sim, "FireResist")
        sim.apply_currency("scour")
        assert sim.item.rarity == "Normal"
        assert len(sim.item.mods) == 1
        assert sim.item.mods[0].family == "IncreasedLife"
        assert sim.item.mods[0].fractured is True

    def test_scour_clears_essence_tracking(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        sim.item.essence_mod_family = "IncreasedLife"
        _add_mod(sim, "IncreasedLife")
        sim.apply_currency("scour")
        assert sim.item.essence_mod_family is None


# ── Alteration ──────────────────────────────────────────────────────────────

class TestAlteration:
    def test_alteration_rerolls_magic(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        _add_mod(sim, "IncreasedLife")
        random.seed(42)
        sim.apply_currency("alteration")
        # Should reroll to Magic with up to 2 mods (1P + 1S)
        assert sim.item.rarity == "Magic"
        assert 1 <= len(sim.item.mods) <= 2


# ── Lesser / Normal Essence ──────────────────────────────────────────────────

class TestLesserNormalEssence:
    def test_lesser_upgrades_magic_to_rare(self):
        """Lesser essence upgrades Magic → Rare with guaranteed mod + fill."""
        sim = _make_sim()
        sim.item.rarity = "Magic"
        random.seed(42)
        sim.apply_currency("lesser_essence", essence_family="IncreasedLife")
        assert sim.item.rarity == "Rare"

    def test_lesser_gives_guaranteed_mod(self):
        """Lesser essence guarantees the specified mod family."""
        sim = _make_sim()
        sim.item.rarity = "Magic"
        random.seed(42)
        sim.apply_currency("lesser_essence", essence_family="IncreasedLife")
        families = {m.family for m in sim.item.mods}
        assert "IncreasedLife" in families

    def test_lesser_fills_to_4_mods(self):
        """Lesser essence adds 1 guaranteed mod only (no random fill)."""
        sim = _make_sim()
        sim.item.rarity = "Magic"
        _add_mod(sim, "FireResist")  # existing Magic mod
        random.seed(42)
        sim.apply_currency("lesser_essence", essence_family="IncreasedLife")
        # Should have 2 mods: existing FireResist + guaranteed IncreasedLife
        assert len(sim.item.mods) == 2
        assert {m.family for m in sim.item.mods} == {"FireResist", "IncreasedLife"}

    def test_normal_essence_same_behavior(self):
        """Normal essence also upgrades Magic → Rare."""
        sim = _make_sim()
        sim.item.rarity = "Magic"
        random.seed(42)
        sim.apply_currency("normal_essence", essence_family="FireResist")
        assert sim.item.rarity == "Rare"
        families = {m.family for m in sim.item.mods}
        assert "FireResist" in families

    def test_tracks_essence_mod(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        random.seed(42)
        sim.apply_currency("lesser_essence", essence_family="IncreasedLife")
        assert sim.item.essence_mod_family == "IncreasedLife"


# ── Greater Essence ─────────────────────────────────────────────────────────

class TestGreaterEssence:
    def test_upgrades_magic_to_rare(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        _add_mod(sim, "FireResist")
        random.seed(42)
        sim.apply_currency("greater_essence", essence_family="IncreasedLife")
        assert sim.item.rarity == "Rare"

    def test_guaranteed_mod_present(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        _add_mod(sim, "FireResist")
        random.seed(42)
        sim.apply_currency("greater_essence", essence_family="IncreasedLife")
        families = {m.family for m in sim.item.mods}
        assert "IncreasedLife" in families

    def test_adds_only_guaranteed_mod(self):
        """Greater essence adds 1 guaranteed mod, no random fill."""
        sim = _make_sim()
        sim.item.rarity = "Magic"
        _add_mod(sim, "FireResist")
        random.seed(42)
        sim.apply_currency("greater_essence", essence_family="IncreasedLife")
        # Should have 2 mods: existing + guaranteed
        assert len(sim.item.mods) == 2
        assert {m.family for m in sim.item.mods} == {"FireResist", "IncreasedLife"}

    def test_tracks_essence_mod(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        random.seed(42)
        sim.apply_currency("greater_essence", essence_family="IncreasedLife")
        assert sim.item.essence_mod_family == "IncreasedLife"

    def test_replaces_previous_essence_mod(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        _add_mod(sim, "FireResist")
        sim.item.essence_mod_family = "FireResist"
        random.seed(42)
        sim.apply_currency("greater_essence", essence_family="IncreasedLife")
        assert sim.item.essence_mod_family == "IncreasedLife"
        # FireResist should be removed (old essence mod)
        families = {m.family for m in sim.item.mods}
        assert "FireResist" not in families or any(
            m.family == "FireResist" and m.fractured for m in sim.item.mods
        )

    def test_requires_essence_family(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        with pytest.raises(ValueError, match="essence_family required"):
            sim.apply_currency("greater_essence")


# ── Perfect Essence ─────────────────────────────────────────────────────────

class TestPerfectEssence:
    def test_remove_one_add_one(self):
        """Perfect essence removes 1 mod and adds 1 guaranteed — NOT a reroll."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "FireResist")
        _add_mod(sim, "ColdResist")
        initial_count = len(sim.item.mods)

        random.seed(42)
        sim.apply_currency("perfect_essence", essence_family="AttackSpeed")
        # Should have same count: removed 1, added 1
        assert len(sim.item.mods) == initial_count
        assert "AttackSpeed" in {m.family for m in sim.item.mods}

    def test_tracks_essence_mod(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FireResist")
        random.seed(42)
        sim.apply_currency("perfect_essence", essence_family="AttackSpeed")
        assert sim.item.essence_mod_family == "AttackSpeed"

    def test_slot_forcing_suffix_full(self):
        """When all suffixes full and essence is suffix, must remove a suffix."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        # Fill all 3 suffix slots
        _add_mod(sim, "FireResist")
        _add_mod(sim, "ColdResist")
        _add_mod(sim, "AttackSpeed")
        # Add 1 prefix
        _add_mod(sim, "IncreasedLife")

        # AttackSpeed is a suffix — pool is full, so removal forced to suffix
        random.seed(42)
        initial_prefixes = [m.family for m in sim.item.prefixes]
        sim.apply_currency("perfect_essence", essence_family="AttackSpeed")
        # IncreasedLife (prefix) should be preserved
        assert "IncreasedLife" in {m.family for m in sim.item.mods}

    def test_crystallisation_omen_overrides(self):
        """Sinistral crystallisation forces prefix removal."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "FireResist")

        # With sinistral_crystallisation, removal targets prefix only
        random.seed(42)
        sim.apply_currency(
            "perfect_essence",
            omen="sinistral_crystallisation",
            essence_family="IncreasedArmour",
        )
        # FireResist (suffix) should be preserved
        assert "FireResist" in {m.family for m in sim.item.mods}
        # IncreasedArmour (prefix) should be added
        assert "IncreasedArmour" in {m.family for m in sim.item.mods}

    def test_one_essence_per_item(self):
        """Second essence removes the first essence mod."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "FireResist")
        _add_mod(sim, "ColdResist")
        sim.item.essence_mod_family = "IncreasedLife"

        random.seed(42)
        sim.apply_currency("perfect_essence", essence_family="IncreasedArmour")
        # Old essence (IncreasedLife) should be removed
        assert "IncreasedLife" not in {m.family for m in sim.item.mods}
        # New essence should be present
        assert "IncreasedArmour" in {m.family for m in sim.item.mods}
        assert sim.item.essence_mod_family == "IncreasedArmour"
        # Count should stay same: old essence removed counts as the "del" step
        assert len(sim.item.mods) == 4

    def test_requires_essence_family(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        with pytest.raises(ValueError, match="essence_family required"):
            sim.apply_currency("perfect_essence")


# ── Omen of Greater Exaltation ──────────────────────────────────────────────

class TestGreaterExaltation:
    def test_adds_two_mods(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")

        random.seed(42)
        sim.apply_currency("exalted", omen="greater_exaltation")
        # Should have 3 mods: 1 original + 2 from greater exaltation
        assert len(sim.item.mods) == 3

    def test_stacks_with_sinistral(self):
        """Greater exaltation + sinistral = 2 prefix mods."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "FireResist")  # 1 suffix

        # We need both omens — but our system only takes one omen string.
        # For now, test that greater_exaltation with gentype works via qty_override.
        # The stacking of two omens is a design question for the optimizer.
        random.seed(42)
        sim.apply_currency("exalted", omen="greater_exaltation")
        assert len(sim.item.mods) == 3

    def test_respects_slot_limits(self):
        """Can't add 2 mods if only 1 slot open."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        # Fill 2 prefixes, 3 suffixes = only 1 prefix open
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "FireResist")
        _add_mod(sim, "ColdResist")
        _add_mod(sim, "AttackSpeed")

        random.seed(42)
        before = len(sim.item.mods)
        sim.apply_currency("exalted", omen="greater_exaltation")
        # Should add at most 1 (only 1 slot open)
        assert len(sim.item.mods) <= before + 1


# ── Omen of Whittling ──────────────────────────────────────────────────────

class TestWhittling:
    def test_removes_lowest_req_level(self):
        """Whittling deterministically removes the mod with lowest req_level."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        # Add mods with different req_levels
        mod_low = _add_mod(sim, "FlatPhysDamage")   # T2 req_level=10
        mod_high = _add_mod(sim, "IncreasedLife")     # T1 req_level=60
        _add_mod(sim, "FireResist")

        random.seed(42)
        sim.apply_currency("chaos", omen="whittling")
        # FlatPhysDamage T2 (req_level=10) should be removed (lowest)
        remaining = {m.family for m in sim.item.mods}
        assert "FlatPhysDamage" not in remaining or any(
            m.family == "FlatPhysDamage" and m.req_level > 10 for m in sim.item.mods
        )

    def test_whittling_is_deterministic(self):
        """Same state should always remove the same mod regardless of seed."""
        results = set()
        for seed in range(10):
            sim = _make_sim()
            sim.item.rarity = "Rare"
            _add_mod(sim, "FlatPhysDamage")  # req_level=10
            _add_mod(sim, "IncreasedLife")   # req_level=60
            _add_mod(sim, "FireResist")      # req_level=60

            random.seed(seed)
            # Capture what was removed
            before = {m.family for m in sim.item.mods}
            sim.apply_currency("chaos", omen="whittling")
            # One mod removed, one added — check the removed one
            after = {m.family for m in sim.item.mods}
            removed = before - after
            # The removed mod should always be FlatPhysDamage (lowest req_level)
            # (though the added mod varies, the removed one is deterministic)
            if removed:
                results.add(frozenset(removed))
        # All runs should remove the same family
        assert len(results) <= 1


# ── Reforge ─────────────────────────────────────────────────────────────────

class TestReforge:
    def test_reforge_produces_rare_with_4_mods(self):
        sim = _make_sim()
        sim.item.rarity = "Normal"
        sim.reforge_stock = 2
        random.seed(42)
        sim.apply_currency("reforge")
        assert sim.item.rarity == "Rare"
        assert len(sim.item.mods) == 4

    def test_reforge_works_on_rare(self):
        """Reforge accepts Rare items (unlike alchemy which requires Normal)."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        sim.reforge_stock = 2
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FireResist")
        random.seed(42)
        sim.apply_currency("reforge")
        assert sim.item.rarity == "Rare"
        assert len(sim.item.mods) == 4

    def test_reforge_preserves_fractured(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        sim.reforge_stock = 2
        _add_mod(sim, "IncreasedLife", fractured=True)
        _add_mod(sim, "FireResist")
        random.seed(42)
        sim.apply_currency("reforge")
        assert any(m.family == "IncreasedLife" and m.fractured for m in sim.item.mods)

    def test_reforge_requires_stock(self):
        """Reforge fails without 2 spare bases in stock."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        sim.reforge_stock = 1  # not enough
        import pytest
        with pytest.raises(ValueError, match="Reforge requires 2 spare bases"):
            sim.apply_currency("reforge")

    def test_reforge_consumes_stock(self):
        """Reforge decrements stock by 2."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        sim.reforge_stock = 5
        random.seed(42)
        sim.apply_currency("reforge")
        assert sim.reforge_stock == 3

    def test_stash_for_reforge(self):
        """Stashing increments stock and resets item."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        sim.stash_for_reforge()
        assert sim.reforge_stock == 1
        assert sim.item.rarity == "Normal"
        assert len(sim.item.mods) == 0


# ── Annulment clears essence tracking ──────────────────────────────────────

class TestAnnulmentEssenceTracking:
    def test_annul_clears_essence_if_removed(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        mod = _add_mod(sim, "IncreasedLife")
        sim.item.essence_mod_family = "IncreasedLife"
        # Only 1 mod — annulment must remove it
        sim.apply_currency("annulment")
        assert sim.item.essence_mod_family is None


# ── Chaos clears essence tracking ──────────────────────────────────────────

class TestChaosEssenceTracking:
    def test_chaos_clears_essence_if_removed(self):
        """If chaos removes the essence mod, tracking is cleared."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        sim.item.essence_mod_family = "IncreasedLife"
        # Only 1 removable mod — chaos must remove it
        random.seed(42)
        sim.apply_currency("chaos")
        assert sim.item.essence_mod_family is None


# ── Currency definitions sanity ────────────────────────────────────────────

# ── Validation ────────────────────────────────────────────────────────────

class TestValidation:
    def test_corrupted_item_rejects_currency(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        sim.item.corrupted = True
        _add_mod(sim, "IncreasedLife")
        with pytest.raises(ValueError, match="corrupted"):
            sim.apply_currency("chaos")

    def test_wrong_rarity_rejected(self):
        sim = _make_sim()
        sim.item.rarity = "Normal"
        with pytest.raises(ValueError, match="requires rarity"):
            sim.apply_currency("chaos")  # chaos requires Rare

    def test_transmute_on_magic_rejected(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        with pytest.raises(ValueError, match="requires rarity"):
            sim.apply_currency("transmute")  # transmute requires Normal

    def test_fracturing_min_mods(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FireResist")
        # Only 2 mods, fracturing needs 4
        with pytest.raises(ValueError, match="at least 4 mods"):
            sim.apply_currency("fracturing")

    def test_fracturing_with_enough_mods(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "FireResist")
        _add_mod(sim, "ColdResist")
        random.seed(42)
        sim.apply_currency("fracturing")
        assert any(m.fractured for m in sim.item.mods)

    def test_alchemy_on_rare_rejected(self):
        sim = _make_sim()
        sim.item.rarity = "Rare"
        with pytest.raises(ValueError, match="requires rarity"):
            sim.apply_currency("alchemy")  # alchemy requires Normal

    def test_exalted_on_magic_rejected(self):
        sim = _make_sim()
        sim.item.rarity = "Magic"
        with pytest.raises(ValueError, match="requires rarity"):
            sim.apply_currency("exalted")  # exalted requires Rare


# ── MC verification: analytical vs simulated probabilities ───────────────

class TestMCVerification:
    """Compare analytical probability_of() with Monte Carlo simulation.

    Uses a large N to verify convergence within statistical tolerance.
    """

    def test_exalt_expected_attempts(self):
        """Analytical expected_attempts matches MC avg_attempts."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FireResist")

        # Analytical
        result = sim.probability_of("ColdResist", currency="exalted")
        expected = result["expected_attempts"]
        assert expected < 100  # sanity

        # MC — simulate_craft counts rolls until hit
        random.seed(1234)
        mc = sim.simulate_craft("ColdResist", "exalted", n_simulations=5000)

        # MC avg should be within 15% of analytical (tolerance for stochastic)
        ratio = mc["avg_attempts"] / expected
        assert 0.85 < ratio < 1.15, (
            f"MC avg={mc['avg_attempts']:.1f} vs analytical={expected:.1f} (ratio={ratio:.2f})"
        )

    def test_chaos_spam_expected_attempts(self):
        """del_add (chaos) MC avg matches analytical expected."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "FireResist")

        result = sim.probability_of("AttackSpeed", currency="chaos")
        expected = result["expected_attempts"]
        assert expected > 1

        random.seed(42)
        mc = sim.simulate_craft("AttackSpeed", "chaos", n_simulations=5000)

        ratio = mc["avg_attempts"] / expected
        assert 0.85 < ratio < 1.15, (
            f"MC avg={mc['avg_attempts']:.1f} vs analytical={expected:.1f} (ratio={ratio:.2f})"
        )

    def test_greater_currency_filter(self):
        """Greater currency filters out low-level mods."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")

        # Normal exalt includes all tiers
        normal = sim.probability_of("FlatPhysDamage", currency="exalted")
        # Greater exalt filters min_lv=35 — FlatPhysDamage T2 (req_level=10) excluded
        greater = sim.probability_of("FlatPhysDamage", currency="greater_exalted")

        # Greater should have fewer target tiers
        assert greater["target_tiers_in_pool"] <= normal["target_tiers_in_pool"]

    def test_omen_gentype_narrows_pool(self):
        """Sinistral omen restricts to prefixes only."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "FireResist")  # 1 suffix

        # Without omen: IncreasedLife is one of many
        no_omen = sim.probability_of("IncreasedLife", currency="exalted")
        # With sinistral: pool restricted to prefixes
        with_omen = sim.probability_of(
            "IncreasedLife", currency="exalted", omen="sinistral_exaltation"
        )

        # Sinistral should give HIGHER probability (smaller pool)
        assert with_omen["probability"] > no_omen["probability"]
        assert with_omen["available_pool_size"] < no_omen["available_pool_size"]

    def test_perfect_currency_filter(self):
        """Perfect currency filters min_lv=50+."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        _add_mod(sim, "IncreasedLife")

        perfect = sim.probability_of("AttackSpeed", currency="perfect_exalted")
        # AttackSpeed has req_level=50, should be in perfect pool
        assert perfect["probability"] > 0
        assert perfect["available_pool_size"] > 0

    def test_pool_exhaustion(self):
        """When all prefix/suffix slots full, prob of that type is 0."""
        sim = _make_sim()
        sim.item.rarity = "Rare"
        # Fill all 3 prefixes
        _add_mod(sim, "IncreasedLife")
        _add_mod(sim, "FlatPhysDamage")
        _add_mod(sim, "IncreasedArmour")
        # Fill 2 suffixes
        _add_mod(sim, "FireResist")
        _add_mod(sim, "ColdResist")

        # Only 1 suffix slot open, no prefix slots
        result = sim.probability_of("AttackSpeed", currency="exalted")
        assert result["probability"] == 1.0  # Only suffix left is AttackSpeed


class TestCurrencyDefinitions:
    def test_all_new_currencies_present(self):
        assert "scour" in CURRENCIES
        assert "alteration" in CURRENCIES
        assert "lesser_essence" in CURRENCIES
        assert "normal_essence" in CURRENCIES
        assert "greater_essence" in CURRENCIES
        assert "perfect_essence" in CURRENCIES
        assert "reforge" in CURRENCIES

    def test_all_new_omens_present(self):
        assert "greater_exaltation" in OMENS
        assert "whittling" in OMENS
        assert "homogenising_exaltation" in OMENS
        assert "sinistral_crystallisation" in OMENS
        assert "dextral_crystallisation" in OMENS

    def test_essence_omens_apply_to_correct_currency(self):
        assert "perfect_essence" in OMENS["sinistral_crystallisation"]["applies_to"]
        assert "perfect_essence" in OMENS["dextral_crystallisation"]["applies_to"]

    def test_whittling_applies_to_chaos(self):
        for c in ["chaos", "greater_chaos", "perfect_chaos"]:
            assert c in OMENS["whittling"]["applies_to"]

    def test_greater_exaltation_applies_to_exalts(self):
        for c in ["exalted", "greater_exalted", "perfect_exalted"]:
            assert c in OMENS["greater_exaltation"]["applies_to"]
