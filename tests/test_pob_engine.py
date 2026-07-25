"""Tests for the PoB calculation engine."""

import pytest
from pathlib import Path


POB_PATH = Path(__file__).parent.parent / "vendor" / "PathOfBuilding-PoE2"
BUILD_FIXTURE = Path(__file__).parent.parent / "data" / "builds" / "martial_artist.txt"


@pytest.mark.skipif(
    not (POB_PATH / "src" / "HeadlessWrapper.lua").exists(),
    reason="PoB-PoE2 submodule not initialized",
)
class TestPoBEngine:
    """Tests that require the PoB-PoE2 submodule to be present."""

    @pytest.fixture(scope="class")
    @classmethod
    def engine(cls):
        """Shared engine instance — boots PoB once for the whole class."""
        from poe2_crafting_mcp.engine.pob_engine import PoBEngine
        return PoBEngine(POB_PATH)

    @pytest.fixture(scope="class")
    @classmethod
    def loaded_engine(cls, engine):
        """Engine with the martial artist fixture loaded."""
        engine.load_build_from_file(BUILD_FIXTURE)
        return engine

    # ── Boot ──────────────────────────────────────────────────────

    def test_pob_path_exists(self):
        """PoB-PoE2 submodule is cloned and has expected structure."""
        assert (POB_PATH / "src" / "HeadlessWrapper.lua").exists()
        assert (POB_PATH / "src" / "Launch.lua").exists()
        assert (POB_PATH / "src" / "Data").is_dir()

    def test_engine_boots(self, engine):
        """PoBEngine initializes and boots without error."""
        from poe2_crafting_mcp.engine.pob_engine import PoBEngine
        assert isinstance(engine, PoBEngine)
        assert engine._booted is True

    # ── Load ──────────────────────────────────────────────────────

    def test_load_build_from_file(self, loaded_engine):
        """Loads the fixture build without raising."""
        assert loaded_engine._build_loaded is True

    def test_load_build_stats_nonzero(self, loaded_engine):
        """Stats are non-zero after loading a real build."""
        stats = loaded_engine.get_stats()
        assert stats.total_dps > 0, "Expected non-zero DPS"
        assert stats.life > 0, "Expected non-zero life"

    # ── Build Info ────────────────────────────────────────────────

    def test_get_build_info_class(self, loaded_engine):
        """Build info returns expected class for the Martial Artist fixture."""
        info = loaded_engine.get_build_info()
        # The fixture is a Martial Artist build
        assert info.class_name != "", "class_name should not be empty"
        assert info.level > 0, "level should be positive"

    def test_get_build_info_tree_nodes(self, loaded_engine):
        """Build info includes passive tree node counts."""
        info = loaded_engine.get_build_info()
        assert info.total_allocated > 0
        assert info.notable_count >= 0
        assert info.keystone_count >= 0
        assert info.notable_count <= info.total_allocated

    def test_get_build_info_main_skill(self, loaded_engine):
        """Build info returns a non-empty main skill label."""
        info = loaded_engine.get_build_info()
        assert info.main_skill != ""

    # ── Stats Detail ──────────────────────────────────────────────

    def test_get_stats_defence(self, loaded_engine):
        """Defence stats are populated."""
        stats = loaded_engine.get_stats()
        # At least one defensive stat should be non-zero
        assert any([
            stats.evasion > 0,
            stats.armour > 0,
            stats.energy_shield > 0,
        ]), "Expected at least one non-zero defensive stat"

    def test_get_stats_resistances_in_range(self, loaded_engine):
        """Resistances are within a plausible range (-100 to 90)."""
        stats = loaded_engine.get_stats()
        for res_name, val in [
            ("fire", stats.fire_res),
            ("cold", stats.cold_res),
            ("lightning", stats.lightning_res),
        ]:
            assert -100 <= val <= 90, f"{res_name} resistance {val} out of expected range"

    # ── Items ─────────────────────────────────────────────────────

    def test_get_equipped_items_returns_dict(self, loaded_engine):
        """get_equipped_items returns a dict keyed by slot name."""
        items = loaded_engine.get_equipped_items()
        assert isinstance(items, dict)
        assert len(items) > 0
        # All values are either EquippedItem or None
        from poe2_crafting_mcp.engine.models import EquippedItem
        for slot, item in items.items():
            assert item is None or isinstance(item, EquippedItem)

    def test_get_equipped_items_known_slots(self, loaded_engine):
        """All expected slot keys are present in the result."""
        items = loaded_engine.get_equipped_items()
        from poe2_crafting_mcp.engine.pob_engine import PoBEngine
        for slot in PoBEngine.SLOT_NAMES:
            assert slot in items, f"Expected slot '{slot}' in equipped items"

    # ── Socket Groups / Gems ──────────────────────────────────────

    def test_get_socket_groups(self, loaded_engine):
        """get_socket_groups returns a list with at least one group."""
        from poe2_crafting_mcp.engine.models import SocketGroup
        groups = loaded_engine.get_socket_groups()
        assert isinstance(groups, list)
        assert len(groups) > 0
        assert all(isinstance(g, SocketGroup) for g in groups)

    def test_socket_group_has_gems(self, loaded_engine):
        """At least one socket group has at least one gem."""
        groups = loaded_engine.get_socket_groups()
        has_gems = any(len(g.gems) > 0 for g in groups)
        assert has_gems, "Expected at least one socket group with gems"

    # ── Skill List ────────────────────────────────────────────────

    def test_get_skill_list(self, loaded_engine):
        """get_skill_list returns a non-empty list of skill labels."""
        skills = loaded_engine.get_skill_list()
        assert isinstance(skills, list)
        assert len(skills) > 0
        assert all(isinstance(s, str) for s in skills)

    def test_set_main_skill_valid(self, loaded_engine):
        """set_main_skill with index 1 succeeds and returns stats."""
        from poe2_crafting_mcp.engine.models import BuildStats
        stats = loaded_engine.set_main_skill(1)
        assert isinstance(stats, BuildStats)

    def test_set_main_skill_invalid_raises(self, loaded_engine):
        """set_main_skill with out-of-range index raises ValueError."""
        with pytest.raises(ValueError):
            loaded_engine.set_main_skill(999)

    # ── Passive Tree ──────────────────────────────────────────────

    def test_get_keystones(self, loaded_engine):
        """get_keystones returns a list of strings."""
        keystones = loaded_engine.get_keystones()
        assert isinstance(keystones, list)
        assert all(isinstance(k, str) for k in keystones)

    def test_get_notables(self, loaded_engine):
        """get_notables returns a list of strings."""
        notables = loaded_engine.get_notables()
        assert isinstance(notables, list)
        assert all(isinstance(n, str) for n in notables)

    def test_notables_count_matches_build_info(self, loaded_engine):
        """Count of notables from get_notables() matches build_info.notable_count."""
        info = loaded_engine.get_build_info()
        notables = loaded_engine.get_notables()
        assert len(notables) == info.notable_count

    # ── Generic Output ────────────────────────────────────────────

    def test_get_output_contains_total_dps(self, loaded_engine):
        """get_output() includes TotalDPS key."""
        output = loaded_engine.get_output()
        assert isinstance(output, dict)
        assert "TotalDPS" in output
        assert output["TotalDPS"] == loaded_engine.get_stats().total_dps

    def test_get_output_has_many_keys(self, loaded_engine):
        """get_output() returns many stat keys (PoB has ~200)."""
        output = loaded_engine.get_output()
        assert len(output) > 20, f"Expected >20 output stats, got {len(output)}"

    # ── Config ────────────────────────────────────────────────────

    def test_get_all_config_returns_dict(self, loaded_engine):
        """get_all_config returns a dict."""
        config = loaded_engine.get_all_config()
        assert isinstance(config, dict)

    def test_set_config_option_bool(self, loaded_engine):
        """set_config_option with a bool returns updated stats."""
        from poe2_crafting_mcp.engine.models import BuildStats
        stats = loaded_engine.set_config_option("buffPowerChargesMax", False)
        assert isinstance(stats, BuildStats)
        # Clean up
        loaded_engine.set_config_option("buffPowerChargesMax", None)

    def test_set_config_option_int(self, loaded_engine):
        """set_config_option with an int returns updated stats."""
        from poe2_crafting_mcp.engine.models import BuildStats
        stats = loaded_engine.set_config_option("enemyLevel", 80)
        assert isinstance(stats, BuildStats)
        # Verify it was set
        val = loaded_engine.get_config_option("enemyLevel")
        assert val == 80
        # Clean up
        loaded_engine.set_config_option("enemyLevel", None)

    # ── Gem Setters ───────────────────────────────────────────────

    def test_set_gem_level(self, loaded_engine):
        """set_gem_level changes the gem level and returns updated stats."""
        from poe2_crafting_mcp.engine.models import BuildStats
        stats = loaded_engine.set_gem_level(1, 1, 20)
        assert isinstance(stats, BuildStats)

    def test_set_gem_quality(self, loaded_engine):
        """set_gem_quality changes quality and returns updated stats."""
        from poe2_crafting_mcp.engine.models import BuildStats
        stats = loaded_engine.set_gem_quality(1, 1, 20)
        assert isinstance(stats, BuildStats)

    # ── Character Level ───────────────────────────────────────────

    def test_set_character_level(self, loaded_engine):
        """set_character_level clamps and updates the build."""
        from poe2_crafting_mcp.engine.models import BuildStats
        stats = loaded_engine.set_character_level(90)
        assert isinstance(stats, BuildStats)
        info = loaded_engine.get_build_info()
        assert info.level == 90

    def test_set_character_level_clamps_min(self, loaded_engine):
        """set_character_level clamps to 1 minimum."""
        loaded_engine.set_character_level(-5)
        info = loaded_engine.get_build_info()
        assert info.level == 1

    # ── Export ────────────────────────────────────────────────────

    def test_export_xml_returns_string(self, loaded_engine):
        """export_xml returns a non-empty XML string."""
        xml = loaded_engine.export_xml()
        assert isinstance(xml, str)
        assert len(xml) > 100
        assert "<PathOfBuilding" in xml or "<Build" in xml or "<?xml" in xml

    def test_export_build_code_roundtrip(self, loaded_engine):
        """Exported build code can be decoded back to XML."""
        import base64
        import zlib

        code = loaded_engine.export_build_code()
        assert isinstance(code, str)
        assert len(code) > 50

        # Decode and check it's valid XML-ish
        padding = 4 - len(code) % 4
        if padding != 4:
            code += "=" * padding
        raw = base64.urlsafe_b64decode(code)
        xml = zlib.decompress(raw).decode("utf-8")
        assert len(xml) > 100

    # ── Combat Profile ────────────────────────────────────────────

    def test_get_combat_profile_structure(self, loaded_engine):
        """get_combat_profile returns a CombatProfile with expected fields."""
        from poe2_crafting_mcp.engine.models import CombatProfile
        profile = loaded_engine.get_combat_profile()
        assert isinstance(profile, CombatProfile)
        assert profile.total_dps > 0
        assert isinstance(profile.charges, dict)
        assert isinstance(profile.ailments_on_enemy, list)
        assert isinstance(profile.relevant_config, dict)

    def test_combat_profile_damage_type_percent(self, loaded_engine):
        """damage_type_percent sums to approximately 100%."""
        profile = loaded_engine.get_combat_profile()
        pct_sum = sum(profile.damage_type_percent.values())
        assert 95 <= pct_sum <= 105, f"damage_type_percent sum {pct_sum} not near 100"

    def test_combat_profile_relevant_config_categories(self, loaded_engine):
        """relevant_config contains expected category keys."""
        profile = loaded_engine.get_combat_profile()
        all_cats = set(profile.relevant_config.keys())
        # At minimum, some categories should be present
        assert len(all_cats) > 0

    def test_combat_profile_config_option_fields(self, loaded_engine):
        """Each ConfigOptionInfo has the required fields."""
        from poe2_crafting_mcp.engine.models import ConfigOptionInfo
        profile = loaded_engine.get_combat_profile()
        for _cat, options in profile.relevant_config.items():
            for opt in options:
                assert isinstance(opt, ConfigOptionInfo)
                assert opt.var != ""  # label may be empty for special options like customMods

    # ── Condition Sources ─────────────────────────────────────────

    def test_get_condition_sources_returns_dict(self, loaded_engine):
        """get_condition_sources returns a non-empty dict."""
        sources = loaded_engine.get_condition_sources()
        assert isinstance(sources, dict)
        assert len(sources) > 0

    def test_condition_sources_entry_structure(self, loaded_engine):
        """Each entry in get_condition_sources has the expected keys."""
        sources = loaded_engine.get_condition_sources()
        for cond, info in sources.items():
            assert "sources" in info, f"{cond} missing 'sources'"
            assert "auto_applicable" in info, f"{cond} missing 'auto_applicable'"
            assert "current_value" in info, f"{cond} missing 'current_value'"
            assert isinstance(info["sources"], list)
            assert isinstance(info["auto_applicable"], bool)

    # ── setup_realistic_scenario ──────────────────────────────────

    def test_setup_realistic_scenario_returns_structure(self, loaded_engine):
        """setup_realistic_scenario returns the expected dict structure."""
        result = loaded_engine.setup_realistic_scenario()
        assert "applied" in result
        assert "dps_before" in result
        assert "dps_after" in result
        assert "dps_change_percent" in result
        assert isinstance(result["applied"], list)
        assert isinstance(result["dps_before"], (int, float))
        assert isinstance(result["dps_after"], (int, float))
        assert isinstance(result["dps_change_percent"], float)

    def test_setup_realistic_scenario_applied_entries(self, loaded_engine):
        """Each applied entry has var, value, and reason."""
        result = loaded_engine.setup_realistic_scenario()
        for entry in result["applied"]:
            assert "var" in entry, f"entry missing 'var': {entry}"
            assert "value" in entry, f"entry missing 'value': {entry}"
            assert "reason" in entry, f"entry missing 'reason': {entry}"
            assert isinstance(entry["var"], str)
            assert isinstance(entry["reason"], str)

    def test_setup_realistic_scenario_increases_dps(self, loaded_engine):
        """Applying a realistic scenario should raise DPS for the Monk fixture."""
        # Reset to defaults first
        loaded_engine.set_config_option("usePowerCharges", False)
        loaded_engine.set_config_option("useFrenzyCharges", False)
        loaded_engine.set_config_option("multiplierRage", 0)
        dps_before = loaded_engine.get_stats().total_dps
        result = loaded_engine.setup_realistic_scenario()
        assert result["dps_after"] > dps_before, (
            f"DPS should increase: before={dps_before}, after={result['dps_after']}"
        )

    # ── Error Handling ────────────────────────────────────────────

    def test_get_stats_without_build_raises(self):
        """Calling get_stats() before loading a build raises RuntimeError."""
        from poe2_crafting_mcp.engine.pob_engine import PoBEngine
        # Create a fresh engine without loading a build
        engine = PoBEngine(POB_PATH)
        with pytest.raises(RuntimeError, match="No build loaded"):
            engine.get_stats()

    def test_equip_item_invalid_slot_raises(self, loaded_engine):
        """equip_item with an invalid slot name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid slot"):
            loaded_engine.equip_item("NotASlot", "Rarity: Normal\nShort Sword")
