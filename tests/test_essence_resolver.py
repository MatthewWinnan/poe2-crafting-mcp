"""Tests for essence resolver — maps essence name + item slot → mod details."""

import pytest
from poe2_crafting_mcp.crafting.essence_resolver import (
    EssenceResolver,
    slot_matches_essence,
    _parse_item_slots,
)


# ── Unit tests for slot matching ─────────────────────────────────────────────

class TestParseItemSlots:
    def test_single(self):
        assert _parse_item_slots("Gloves") == {"Gloves"}

    def test_comma_separated(self):
        assert _parse_item_slots("Belt, Boots, Gloves") == {"Belt", "Boots", "Gloves"}

    def test_or_separated(self):
        assert _parse_item_slots("Bow or Crossbow") == {"Bow", "Crossbow"}

    def test_mixed(self):
        assert _parse_item_slots("Belt, Body Armour, Helmet or Shield") == {
            "Belt", "Body Armour", "Helmet", "Shield"
        }


class TestSlotMatches:
    def test_direct_match(self):
        assert slot_matches_essence("Gloves", "Gloves")

    def test_category_armour(self):
        assert slot_matches_essence("Gloves", "Armour")
        assert slot_matches_essence("Boots", "Armour")
        assert slot_matches_essence("Body Armour", "Armour")
        assert slot_matches_essence("Helmet", "Armour")
        assert slot_matches_essence("Shield", "Armour")

    def test_category_jewellery(self):
        assert slot_matches_essence("Ring", "Jewellery")
        assert slot_matches_essence("Amulet", "Jewellery")
        assert not slot_matches_essence("Belt", "Jewellery")

    def test_category_martial_weapon(self):
        assert slot_matches_essence("Bow", "Martial Weapon")
        assert slot_matches_essence("One Hand Sword", "Martial Weapon")
        assert not slot_matches_essence("Wand", "Martial Weapon")
        assert not slot_matches_essence("Staff", "Martial Weapon")

    def test_category_caster_weapon(self):
        assert slot_matches_essence("Wand", "Caster Weapon")
        assert slot_matches_essence("Staff", "Caster Weapon")
        assert slot_matches_essence("Sceptre", "Caster Weapon")
        assert slot_matches_essence("Focus", "Caster Weapon")
        assert not slot_matches_essence("Bow", "Caster Weapon")

    def test_melee_weapon(self):
        assert slot_matches_essence("One Hand Sword", "Melee Weapon")
        assert slot_matches_essence("Two Hand Axe", "Melee Weapon")
        assert not slot_matches_essence("Bow", "Melee Weapon")
        assert not slot_matches_essence("Wand", "Melee Weapon")

    def test_equipment(self):
        assert slot_matches_essence("Gloves", "Equipment")
        assert slot_matches_essence("Ring", "Equipment")
        assert slot_matches_essence("Bow", "Equipment")

    def test_multi_term_essence_slot(self):
        assert slot_matches_essence("Bow", "Bow or Crossbow")
        assert slot_matches_essence("Crossbow", "Bow or Crossbow")
        assert not slot_matches_essence("Wand", "Bow or Crossbow")

    def test_one_handed_melee_or_bow(self):
        assert slot_matches_essence("Bow", "One Handed Melee Weapon or Bow")
        assert slot_matches_essence("Dagger", "One Handed Melee Weapon or Bow")
        assert not slot_matches_essence("Two Hand Axe", "One Handed Melee Weapon or Bow")

    def test_unknown_slot(self):
        assert not slot_matches_essence("Flask", "Armour")
        assert not slot_matches_essence("Jewel", "Equipment")

    def test_weapons_category(self):
        assert slot_matches_essence("Bow", "Weapons")
        assert slot_matches_essence("Wand", "Weapons")
        assert slot_matches_essence("One Hand Sword", "Weapons")
        assert not slot_matches_essence("Gloves", "Weapons")


# ── Integration tests against real DB ────────────────────────────────────────

@pytest.fixture
def resolver():
    return EssenceResolver()


class TestResolve:
    def test_greater_body_gloves(self, resolver):
        mod = resolver.resolve("Greater Essence of the Body", "Gloves")
        assert mod is not None
        assert "Life" in mod.stat_text
        assert mod.tier == "Greater"
        assert mod.effect_type == "upgrade"

    def test_greater_body_body_armour(self, resolver):
        mod = resolver.resolve("Greater Essence of the Body", "Body Armour")
        assert mod is not None
        assert "Life" in mod.stat_text
        # Body Armour gets higher values than Gloves
        gloves_mod = resolver.resolve("Greater Essence of the Body", "Gloves")
        assert mod.stat_min > gloves_mod.stat_min

    def test_greater_haste_bow_vs_melee(self, resolver):
        bow = resolver.resolve("Greater Essence of Haste", "Bow")
        sword = resolver.resolve("Greater Essence of Haste", "One Hand Sword")
        assert bow is not None
        assert sword is not None
        # Both give attack speed but different values
        assert "Attack Speed" in bow.stat_text
        assert "Attack Speed" in sword.stat_text

    def test_perfect_body(self, resolver):
        mod = resolver.resolve("Perfect Essence of the Body", "Body Armour")
        assert mod is not None
        assert mod.effect_type == "swap"
        assert "Life" in mod.stat_text

    def test_nonexistent_essence(self, resolver):
        mod = resolver.resolve("Fake Essence of Nothing", "Gloves")
        assert mod is None

    def test_invalid_slot(self, resolver):
        mod = resolver.resolve("Greater Essence of the Body", "Flask")
        assert mod is None


class TestResolveByBase:
    def test_by_base(self, resolver):
        mod = resolver.resolve_by_base("Body", "Greater", "Gloves")
        assert mod is not None
        assert "Life" in mod.stat_text

    def test_by_base_haste(self, resolver):
        mod = resolver.resolve_by_base("Haste", "Greater", "Bow")
        assert mod is not None
        assert "Attack Speed" in mod.stat_text


class TestListForSlot:
    def test_list_greater_gloves(self, resolver):
        mods = resolver.list_for_slot("Gloves", tier="Greater")
        assert len(mods) > 5
        names = {m.essence_name for m in mods}
        assert "Greater Essence of the Body" in names

    def test_list_all_tiers_bow(self, resolver):
        mods = resolver.list_for_slot("Bow")
        tiers = {m.tier for m in mods}
        assert "Greater" in tiers
        assert "Perfect" in tiers


class TestCurrencyKey:
    def test_tiers(self, resolver):
        assert resolver.get_currency_key("Lesser") == "lesser_essence"
        assert resolver.get_currency_key("Greater") == "greater_essence"
        assert resolver.get_currency_key("Perfect") == "perfect_essence"
        assert resolver.get_currency_key("Alloy") == ""
