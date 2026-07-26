"""
PoE2 keyword/concept dictionary.

Each entry is a dict with:
  name           — display name (matches poe2db Keywords page)
  category       — one of: damage_type, ailment, attribute, defence, offence,
                   charge, resource, buff, debuff, mechanic, keyword, keystone,
                   projectile, ground
  summary        — one-sentence plain-English description
  mechanics      — detailed explanation (2-5 sentences)
  formula        — calculation formula or numeric details (empty string if N/A)
  see_also       — related concept names AND PoB config/stat var names
  source         — where the definition was verified:
                   "manual"            hand-written, unverified from official source
                   "PoB:ConfigOptions" verified against ConfigOptions.lua
                   "PoB:SkillTypes"    verified against SkillType enum in PoB
                   "PoB:Gems"          verified against Gems.lua
                   "poe2wiki"          sourced from the PoE2 community wiki

Entries without a "source" key default to "manual" when seeded into the DB.
"""

from __future__ import annotations

CONCEPTS: list[dict] = [

    # ── Damage Types ──────────────────────────────────────────────────────────

    {
        "name": "Physical Damage",
        "category": "damage_type",
        "summary": "The most common damage type, reduced by Armour.",
        "mechanics": (
            "Physical damage is dealt by most attacks and some skills. "
            "It is the only damage type reduced by the Armour formula. "
            "It can inflict Bleeding and cause Stun buildup. "
            "Chaos damage removes twice as much Energy Shield as equivalent physical damage."
        ),
        "formula": "Armour reduction = Armour / (Armour + 10 × hit).",
        "see_also": ["Armour", "Bleeding", "Strength", "Crushed", "Overwhelm"],
    },
    {
        "name": "Fire Damage",
        "category": "damage_type",
        "summary": "Elemental damage type that can inflict Ignite.",
        "mechanics": (
            "Fire damage is reduced by Fire Resistance (cap 75% by default). "
            "Hits with fire damage can apply Ignite. "
            "Fire exposure reduces enemy fire resistance by 20%."
        ),
        "formula": "Damage taken × (1 − fire_res / 100).",
        "see_also": ["Ignite", "Exposure", "Resistance", "Avatar of Fire", "conditionEnemyIgnited"],
    },
    {
        "name": "Cold Damage",
        "category": "damage_type",
        "summary": "Elemental damage type that chills and builds Freeze.",
        "mechanics": (
            "Cold damage is reduced by Cold Resistance. "
            "Hits with cold damage inflict Chill and contribute Freeze buildup proportional to hit size. "
            "Cold exposure reduces enemy cold resistance by 20%."
        ),
        "formula": "Freeze buildup = cold hit / enemy ailment threshold × 100%.",
        "see_also": ["Chill", "Freeze", "Exposure", "Resistance", "conditionEnemyChilled", "conditionEnemyFrozen"],
    },
    {
        "name": "Lightning Damage",
        "category": "damage_type",
        "summary": "Elemental damage type with chance to Shock and Electrocute.",
        "mechanics": (
            "Lightning damage is reduced by Lightning Resistance. "
            "Hits with lightning damage can Shock enemies and build Electrocute buildup. "
            "Lightning damage has the widest damage range (low minimum, high maximum). "
            "Lightning exposure reduces enemy lightning resistance by 20%."
        ),
        "formula": "Shock chance = ShockChanceMultiplier (25%) × other modifiers.",
        "see_also": ["Shock", "Electrocute", "Exposure", "Resistance", "conditionEnemyShocked"],
    },
    {
        "name": "Chaos Damage",
        "category": "damage_type",
        "summary": "Damage type that bypasses Armour and removes double Energy Shield.",
        "mechanics": (
            "Chaos damage is not reduced by Armour and bypasses Energy Shield unless "
            "you have Chaos Inoculation. It removes twice as much Energy Shield as its "
            "damage value. Chaos resistance is harder to cap and starts at -60% by default "
            "for new characters."
        ),
        "formula": "ES removed = chaos_hit × 2 (before chaos resistance).",
        "see_also": ["Resistance", "Energy Shield", "Chaos Inoculation", "Poison", "Withered"],
    },

    # ── Ailments ─────────────────────────────────────────────────────────────

    {
        "name": "Ailments",
        "category": "ailment",
        "summary": "Debuffs associated with specific damage types applied on hit.",
        "mechanics": (
            "Ailments are debuffs applied by hits. Damaging ailments (Bleeding, Ignite, Poison) "
            "deal damage over time. Non-damaging ailments (Chill, Freeze, Shock, Electrocute) "
            "apply effects like slowing or increasing damage taken. Each ailment has a chance "
            "to be applied per hit, modified by build stats."
        ),
        "formula": "",
        "see_also": ["Bleeding", "Ignite", "Poison", "Chill", "Freeze", "Shock", "Electrocute", "Brittle", "Sap", "Scorch"],
    },
    {
        "name": "Shock",
        "category": "ailment",
        "summary": "Causes enemies to take 20% increased damage for 4–8 seconds.",
        "mechanics": (
            "Shock is a non-damaging lightning ailment. The base magnitude is 20% increased "
            "damage taken. Higher lightning hits increase shock magnitude (scaling with hit vs "
            "enemy max life), up to 50% (or higher with mods). "
            "Shock chance is modified by ShockChanceMultiplier (25% base multiplier in PoE2). "
            "Duration is 8 seconds vs monsters, 4 vs players."
        ),
        "formula": "Base magnitude: 20%. Max magnitude: 50% (moddable). Duration: 8s vs monsters.",
        "see_also": ["Lightning Damage", "Ailments", "Electrocute", "conditionEnemyShocked", "ShockChance", "MaximumShock"],
    },
    {
        "name": "Chill",
        "category": "ailment",
        "summary": "Slows enemy action speed, lasts 2–8 seconds.",
        "mechanics": (
            "Chill is a non-damaging cold ailment that reduces enemy action speed (slow). "
            "Chill magnitude scales with the cold hit size relative to enemy max life. "
            "The maximum chill effect is 50% reduced action speed. "
            "Chill is automatically applied by any cold hit; chance is 100% by default."
        ),
        "formula": "Max chill: 50% slow. Duration: 2s (players) to 8s (monsters).",
        "see_also": ["Cold Damage", "Freeze", "Ailments", "Slow", "conditionEnemyChilled", "ChillChance"],
    },
    {
        "name": "Freeze",
        "category": "ailment",
        "summary": "Prevents enemy movement and actions entirely.",
        "mechanics": (
            "Freeze is a non-damaging cold ailment that completely stops an enemy. "
            "It requires building up freeze buildup equal to the enemy's Freeze Threshold "
            "(based on enemy max life). Each cold hit contributes buildup proportional to "
            "cold damage dealt vs ailment threshold. Frozen enemies Shatter when killed."
        ),
        "formula": "Buildup = cold hit × FreezeDamageScale (2.1) / enemy ailment threshold. Threshold: 500% for players.",
        "see_also": ["Cold Damage", "Chill", "Ailments", "Shatter", "Immobilised", "conditionEnemyFrozen", "FreezeBuildupAvg"],
    },
    {
        "name": "Ignite",
        "category": "ailment",
        "summary": "Burns enemy for fire damage over time based on the hit that inflicted it.",
        "mechanics": (
            "Ignite is a damaging fire ailment. It deals fire DoT based on 200% of the fire "
            "hit per minute (1200%/min ÷ 60 ≈ 20% per second of the hit). Duration is 4 seconds "
            "by default. Only the strongest ignite on an enemy is active unless stacking is enabled. "
            "Ignite chance is modified by IgniteChanceMultiplier (20% base)."
        ),
        "formula": "DPS = fire_hit × 1200% / 60s. Duration: 4s. Stack limit: 1 (default).",
        "see_also": ["Fire Damage", "Ailments", "Aggravated Ignite", "conditionEnemyIgnited", "IgniteChance", "IgniteDPS"],
    },
    {
        "name": "Bleeding",
        "category": "ailment",
        "summary": "Deals physical damage over time, increased while enemy is moving.",
        "mechanics": (
            "Bleeding is a damaging physical ailment. It deals physical DoT at 150% of the "
            "physical hit per minute (900%/min). Duration is 5 seconds by default. "
            "Bleeding deals 100% more damage against moving targets. "
            "Multiple bleeds can stack on a target."
        ),
        "formula": "DPS = physical_hit × 900% / 60s (×2 if target moving). Duration: 5s.",
        "see_also": ["Physical Damage", "Ailments", "Aggravated Bleeding", "conditionEnemyBleeding", "BleedChance", "BleedDPS"],
    },
    {
        "name": "Poison",
        "category": "ailment",
        "summary": "Deals chaos damage over time; stacks multiply with each hit.",
        "mechanics": (
            "Poison is a damaging chaos ailment. Each application deals chaos DoT at 200% "
            "of the combined physical and chaos hit per minute. Duration is 2 seconds by default. "
            "Multiple poison stacks accumulate independently, making rapid hits very effective. "
            "Applied by physical or chaos hits with sufficient poison chance."
        ),
        "formula": "DPS per stack = (phys + chaos) hit × 1200% / 60s. Duration: 2s per stack.",
        "see_also": ["Chaos Damage", "Physical Damage", "Ailments", "Withered", "conditionEnemyPoisoned", "PoisonChance", "PoisonDPS"],
    },
    {
        "name": "Electrocute",
        "category": "ailment",
        "summary": "Interrupts enemy actions, requires buildup like Freeze.",
        "mechanics": (
            "Electrocute is a non-damaging lightning ailment requiring buildup to proc. "
            "It interrupts and stuns the target briefly. Duration is 5 seconds vs monsters, "
            "2 vs players. Buildup scales with lightning hit size vs the Electrocute Threshold. "
            "Normal enemies can be Primed for Electrocution at 40% buildup."
        ),
        "formula": "Duration: 5s (monsters), 2s (players). Threshold modifier: 500% of ailment threshold.",
        "see_also": ["Lightning Damage", "Ailments", "Shock", "Immobilised", "Freeze"],
    },
    {
        "name": "Brittle",
        "category": "ailment",
        "summary": "Causes hits against the enemy to have up to +6% Critical Hit Chance.",
        "mechanics": (
            "Brittle is a lesser non-damaging cold ailment. Enemies affected by Brittle grant "
            "attackers up to +6% to Critical Hit Chance. It scales with the hit that applied it "
            "relative to enemy life. Multiple applications increase the bonus up to the cap."
        ),
        "formula": "Up to +6% Critical Hit Chance against Brittle enemies.",
        "see_also": ["Cold Damage", "Ailments", "Critical Hits", "conditionEnemyBrittle"],
    },
    {
        "name": "Scorch",
        "category": "ailment",
        "summary": "Lesser fire ailment that reduces enemy fire resistance.",
        "mechanics": (
            "Scorch is a lesser non-damaging fire ailment. It reduces the target's fire resistance. "
            "The magnitude scales with fire hit size. Applied by fire hits with a Scorch modifier. "
            "Stacks multiplicatively with Exposure."
        ),
        "formula": "Reduces fire resistance by magnitude (scales with hit vs life).",
        "see_also": ["Fire Damage", "Ailments", "Exposure", "conditionEnemyScorched"],
    },
    {
        "name": "Sap",
        "category": "ailment",
        "summary": "Lesser lightning ailment that reduces enemy damage dealt.",
        "mechanics": (
            "Sap is a lesser non-damaging lightning ailment. It reduces the damage dealt by "
            "the affected enemy. Magnitude scales with the lightning hit that applied it. "
            "Applied by lightning hits with a Sap modifier."
        ),
        "formula": "Reduces enemy damage dealt by magnitude.",
        "see_also": ["Lightning Damage", "Ailments", "conditionEnemySapped"],
    },
    {
        "name": "Withered",
        "category": "ailment",
        "summary": "Applies 5% increased Chaos Damage taken per stack, up to 10 stacks.",
        "mechanics": (
            "Withered is a chaos debuff (not technically an ailment) that stacks up to 10 times. "
            "Each stack causes the target to take 5% increased chaos damage, for a maximum of "
            "50% increased chaos damage taken at 10 stacks. Applied by chaos skills with Wither."
        ),
        "formula": "5% increased Chaos Damage taken per stack × up to 10 stacks = max 50%.",
        "see_also": ["Chaos Damage", "Poison", "Debuffs"],
    },
    {
        "name": "Aggravated Bleeding",
        "category": "ailment",
        "summary": "Bleeding that deals 100% extra damage.",
        "mechanics": (
            "Aggravated Bleeding is Bleeding that has been upgraded to deal double damage. "
            "Certain skills or modifiers can Aggravate Bleeding on a target. "
            "The damage increase applies on top of the moving target bonus."
        ),
        "formula": "DPS = normal bleed DPS × 2.",
        "see_also": ["Bleeding", "Physical Damage"],
    },
    {
        "name": "Aggravated Ignite",
        "category": "ailment",
        "summary": "Ignite that deals 100% extra damage.",
        "mechanics": (
            "Aggravated Ignite is Ignite that has been upgraded to deal double damage. "
            "Certain skills or modifiers Aggravate Ignite, doubling its fire DoT output."
        ),
        "formula": "DPS = normal ignite DPS × 2.",
        "see_also": ["Ignite", "Fire Damage"],
    },
    {
        "name": "Corrupted Blood",
        "category": "ailment",
        "summary": "Stacking physical DoT debuff, up to 10 stacks per target.",
        "mechanics": (
            "Corrupted Blood is a debuff that deals physical damage over time and stacks "
            "up to 10 times per target. Each stack adds a separate DoT. "
            "It is inflicted by specific skills and cannot be normally spread."
        ),
        "formula": "Up to 10 independent stacks of physical DoT.",
        "see_also": ["Physical Damage", "Bleeding", "Ailments"],
    },

    # ── Attributes ────────────────────────────────────────────────────────────

    {
        "name": "Attributes",
        "category": "attribute",
        "summary": "The three primary character stats: Strength, Dexterity, Intelligence.",
        "mechanics": (
            "Every 10 points of an attribute grants a bonus: Strength gives Life and melee damage, "
            "Dexterity gives Accuracy and Evasion, Intelligence gives Mana and Energy Shield. "
            "Attributes also act as requirements for equipping items and gems."
        ),
        "formula": "Each 10 of attribute grants its inherent bonus.",
        "see_also": ["Strength", "Dexterity", "Intelligence"],
    },
    {
        "name": "Strength",
        "category": "attribute",
        "summary": "Grants +2 maximum Life and melee physical damage per point.",
        "mechanics": (
            "Strength is the primary attribute for melee builds and warriors. "
            "Every 1 Strength grants +2 maximum Life. "
            "It also provides a percentage increase to melee physical damage. "
            "Required by armour items, axes, maces, and swords."
        ),
        "formula": "+2 max Life per 1 Strength. Melee physical damage bonus per 10 Strength.",
        "see_also": ["Life", "Physical Damage", "Attributes", "Black Scythe Training"],
    },
    {
        "name": "Dexterity",
        "category": "attribute",
        "summary": "Grants +8 Accuracy Rating and Evasion Rating per point.",
        "mechanics": (
            "Dexterity is the primary attribute for ranged and evasion builds. "
            "Every 1 Dexterity grants +8 Accuracy Rating. "
            "It also contributes to Evasion Rating. "
            "Required by evasion armour, bows, claws, and daggers."
        ),
        "formula": "+8 Accuracy per 1 Dexterity. Evasion bonus per 10 Dexterity.",
        "see_also": ["Accuracy", "Evasion", "Attributes", "Circular Teachings"],
    },
    {
        "name": "Intelligence",
        "category": "attribute",
        "summary": "Grants +2 maximum Mana and Energy Shield per point.",
        "mechanics": (
            "Intelligence is the primary attribute for spellcasting builds. "
            "Every 1 Intelligence grants +2 maximum Mana. "
            "It also increases maximum Energy Shield. "
            "Required by energy shield armour, wands, staves, and sceptres."
        ),
        "formula": "+2 max Mana per 1 Intelligence. Energy Shield bonus per 10 Intelligence.",
        "see_also": ["Mana", "Energy Shield", "Attributes", "Knightly Tenets"],
    },

    # ── Defence ───────────────────────────────────────────────────────────────

    {
        "name": "Armour",
        "category": "defence",
        "summary": "Reduces physical damage taken from hits, scales with hit size.",
        "mechanics": (
            "Armour provides physical damage reduction for hits (not DoT). "
            "Its effectiveness is proportional — it reduces larger hits by less percentage than "
            "smaller hits. Against a hit of X damage: reduction = Armour / (Armour + 10 × X). "
            "Only reduces physical damage; does not affect elemental or chaos damage."
        ),
        "formula": "Phys reduction % = Armour / (Armour + 10 × hit_damage) × 100.",
        "see_also": ["Physical Damage", "Crushed", "Armour Break", "Overwhelm", "Iron Reflexes"],
    },
    {
        "name": "Evasion",
        "category": "defence",
        "summary": "Grants a percentage chance to completely avoid incoming hits.",
        "mechanics": (
            "Evasion provides a chance to avoid Attack hits entirely. When evaded, "
            "no damage or on-hit effects are applied. Evasion chance is calculated from your "
            "Evasion Rating vs the attacker's Accuracy Rating. It only works against Attacks, "
            "not Spells. Blind reduces attacker Accuracy by 20%."
        ),
        "formula": "Evade chance = 1 − (attacker accuracy / (attacker accuracy + (evasion / 4)^0.8)).",
        "see_also": ["Accuracy", "Blind", "Dexterity", "Iron Reflexes", "Glancing Blows"],
    },
    {
        "name": "Energy Shield",
        "category": "defence",
        "summary": "A buffer that absorbs damage before Life, recharges when not hit.",
        "mechanics": (
            "Energy Shield protects Life by taking damage instead. It recharges at 12.5% per second "
            "after a 2-second delay without taking ES damage. Chaos damage removes twice its value "
            "from ES. Recharge can be sped up with 'Faster Start of Energy Shield Recharge' mods. "
            "Eldritch Battery converts ES to Mana instead."
        ),
        "formula": "ES recharge: 12.5%/s after 2s delay. Chaos removes ×2 ES.",
        "see_also": ["Chaos Damage", "Intelligence", "Eldritch Battery", "Eternal Youth", "Chaos Inoculation"],
    },
    {
        "name": "Ward",
        "category": "defence",
        "summary": "Absorbs a fixed amount of damage per hit before other defences apply.",
        "mechanics": (
            "Ward absorbs a flat amount of damage from every hit before armour, evasion, "
            "or resistances are considered. After being hit, Ward breaks and must recharge. "
            "It applies to all damage types equally."
        ),
        "formula": "Damage reduced by Ward value per hit (flat, pre-mitigation).",
        "see_also": ["Armour", "Energy Shield", "Block"],
    },
    {
        "name": "Block",
        "category": "defence",
        "summary": "Completely prevents all damage from a blocked hit.",
        "mechanics": (
            "Block chance is a percentage chance to completely negate an incoming hit. "
            "When a hit is blocked, no damage or on-hit effects are applied. "
            "Shields provide block chance passively. Bucklers provide Parry instead of normal block. "
            "Maximum block chance is typically capped at 75%."
        ),
        "formula": "Block chance up to 75% cap. Full hit prevented on success.",
        "see_also": ["Evasion", "Shields", "Glancing Blows", "Suppress", "Deflect"],
    },
    {
        "name": "Suppress",
        "category": "defence",
        "summary": "Prevents 50% of damage from Suppressed hits and ailments.",
        "mechanics": (
            "When a hit is Suppressed (chance-based), 50% of its damage and any ailments it "
            "would apply are prevented. Unlike Block (full negation) or Evasion (full avoidance), "
            "Suppress reduces the hit by half. The chance to Suppress is based on Suppress Rating."
        ),
        "formula": "50% of hit damage and ailment magnitude prevented on Suppress.",
        "see_also": ["Block", "Evasion", "Deflect"],
    },
    {
        "name": "Deflect",
        "category": "defence",
        "summary": "Chance-based defence that prevents 40% of hit damage.",
        "mechanics": (
            "Deflection Rating provides a chance to Deflect incoming hits, preventing 40% of "
            "their damage. Deflect sits between Suppress (50% prevention) and no mitigation. "
            "Deflection Rating is gained from certain items and passives."
        ),
        "formula": "40% of hit damage prevented on Deflect.",
        "see_also": ["Suppress", "Block", "Glancing Blows"],
    },
    {
        "name": "Resistances",
        "category": "defence",
        "summary": "Reduce damage taken of the corresponding elemental or chaos type.",
        "mechanics": (
            "Elemental resistances (Fire, Cold, Lightning) cap at 75% by default. "
            "Chaos resistance also caps at 75% but starts at -60%. "
            "Endgame maps apply a -60% resistance penalty. "
            "Overcapped resistance is the amount exceeding the cap — it protects against "
            "resistance-reducing debuffs like Exposure."
        ),
        "formula": "Default cap: 75%. Chaos starts at -60%. Endgame penalty: -60%.",
        "see_also": ["Exposure", "Elemental Damage Types", "Chaos Damage", "Maximum Resistances"],
    },
    {
        "name": "Maximum Resistances",
        "category": "defence",
        "summary": "Default cap for elemental and chaos resistances is 75%.",
        "mechanics": (
            "The maximum effective resistance for all types is 75% by default. "
            "This cap can be raised by specific items and passives. "
            "Overcapping resistance (having uncapped res above 75%) provides a buffer "
            "against resistance-reducing effects like Exposure or Withered."
        ),
        "formula": "Default max: 75%. Can be raised beyond 75% with specific mods.",
        "see_also": ["Resistances", "Exposure", "Uncapped Resistance", "Overcapped Resistance"],
    },

    # ── Offence ───────────────────────────────────────────────────────────────

    {
        "name": "Critical Hits",
        "category": "offence",
        "summary": "Deal +100% extra damage (twice the normal damage) by default.",
        "mechanics": (
            "Critical Hits deal +100% increased damage by default (Critical Damage Bonus). "
            "The chance to land a Critical Hit is the Critical Hit Chance stat. "
            "Critical Damage Bonus can be increased beyond 100%. "
            "Resolute Technique doubles Accuracy but prevents all Critical Hits."
        ),
        "formula": "Crit damage = base × (1 + critical_damage_bonus / 100). Default bonus: 100%.",
        "see_also": ["Brittle", "Accuracy", "Pain Attunement", "Resolute Technique", "CritChance", "CritMultiplier"],
    },
    {
        "name": "Accuracy",
        "category": "offence",
        "summary": "Determines hit chance for Attacks against enemy Evasion.",
        "mechanics": (
            "Accuracy Rating is checked against target's Evasion Rating to calculate the "
            "probability that an Attack will hit. A hit chance of 100% can be reached with "
            "sufficient Accuracy. Dexterity grants +8 Accuracy per point. "
            "Blind reduces attacker Accuracy by 20%."
        ),
        "formula": "Hit chance = accuracy / (accuracy + (evasion / 4)^0.8), capped at 95%.",
        "see_also": ["Evasion", "Dexterity", "Blind", "Resolute Technique", "HitChance"],
    },
    {
        "name": "Leech",
        "category": "offence",
        "summary": "Recover Life, ES, or Mana equal to a percentage of damage dealt, over 1 second.",
        "mechanics": (
            "Leech converts a percentage of damage dealt into recovery of Life, Energy Shield, "
            "or Mana over one second. Multiple leech instances stack. "
            "Vaal Pact doubles Life Leech rate but reduces Leech speed by 67%. "
            "Leech is applied per hit and is based on total damage dealt."
        ),
        "formula": "Recovery per second = damage_dealt × leech_% / leech_duration (1s default).",
        "see_also": ["Life", "Energy Shield", "Mana", "Vaal Pact", "Life Leech"],
    },
    {
        "name": "Culling Strike",
        "category": "offence",
        "summary": "Instantly kills enemies below a life threshold (default 10%).",
        "mechanics": (
            "Culling Strike instantly kills enemies whose life is at or below the culling threshold. "
            "The default threshold is 10% of maximum life. "
            "Normal enemies have a 35% threshold. "
            "Higher Culling Strike Threshold mods increase the kill threshold."
        ),
        "formula": "Instantly kills targets at ≤10% life (Normal enemies at ≤35% life).",
        "see_also": ["Overkill", "Low Life"],
    },
    {
        "name": "Penetration",
        "category": "offence",
        "summary": "Causes target's resistance to be treated as lower for your hits.",
        "mechanics": (
            "Penetration reduces the effective resistance of a target for damage calculation "
            "purposes, but does not change the target's actual resistance stat. "
            "It applies after all other resistance modifiers. "
            "Exposure is a separate debuff that actually lowers resistance."
        ),
        "formula": "Effective resistance = actual resistance − penetration value.",
        "see_also": ["Resistances", "Exposure", "Elemental Damage Types"],
    },
    {
        "name": "Damage Conversion",
        "category": "offence",
        "summary": "Changes a portion of damage from one type to another; scales with new type.",
        "mechanics": (
            "Converted damage scales with modifiers for BOTH the original and converted type. "
            "Gained-as-Extra damage only scales with the extra type's modifiers. "
            "Conversion happens before other damage calculations. "
            "Avatar of Fire converts 75% of all damage to Fire."
        ),
        "formula": "Converted portion scales with both source and target type modifiers.",
        "see_also": ["Damage Types", "Avatar of Fire", "Gained as Extra X"],
    },
    {
        "name": "Hit Damage",
        "category": "offence",
        "summary": "Any damage that is not damage over time.",
        "mechanics": (
            "Hit damage is all damage dealt by a direct hit (as opposed to DoT from ailments). "
            "It is the only damage type that can trigger on-hit effects, leech, Stun buildup, "
            "and ailment application. Critical Hit bonuses apply to hit damage. "
            "Damage Over Time cannot crit and cannot trigger on-hit effects."
        ),
        "formula": "",
        "see_also": ["Critical Hits", "Ailments", "Leech", "Stun", "Damage Over Time"],
    },
    {
        "name": "Damage Over Time",
        "category": "offence",
        "summary": "Damage dealt per second from ailments or skills; cannot crit.",
        "mechanics": (
            "DoT includes Bleeding, Ignite, and Poison ailments as well as skills with "
            "inherent DoT components. DoT cannot critically hit and does not trigger on-hit "
            "effects. DoT scales with 'increased/more damage over time' modifiers and the "
            "relevant damage type (physical for bleed, fire for ignite, chaos for poison)."
        ),
        "formula": "",
        "see_also": ["Bleeding", "Ignite", "Poison", "Hit Damage", "Ailments"],
    },
    {
        "name": "Overkill",
        "category": "offence",
        "summary": "Damage in excess of enemy remaining life on a killing hit.",
        "mechanics": (
            "Overkill is the amount of damage dealt beyond what was needed to kill an enemy. "
            "Some skills and modifiers scale with or trigger on Overkill damage. "
            "It has no mechanical effect by itself but is referenced by specific skills."
        ),
        "formula": "Overkill = hit_damage − enemy_remaining_life (when hit_damage > life).",
        "see_also": ["Culling Strike", "Low Life"],
    },

    # ── Charges ───────────────────────────────────────────────────────────────

    {
        "name": "Charges",
        "category": "charge",
        "summary": "Temporary buffs gained from skills, passives, or kills; last 15 seconds.",
        "mechanics": (
            "Charges provide powerful bonuses and last 15 seconds by default before expiring. "
            "Each charge type has a maximum stack count. "
            "Charges are gained through specific skills, passive keystones, and on-kill effects. "
            "The Conduit keystone shares charges with allies."
        ),
        "formula": "Default duration: 15 seconds.",
        "see_also": ["Power Charge", "Frenzy Charge", "Endurance Charge", "Conduit", "usePowerCharges"],
    },
    {
        "name": "Power Charge",
        "category": "charge",
        "summary": "Each Power Charge grants +30% Critical Hit Chance.",
        "mechanics": (
            "Power Charges are blue charges. Each one grants +30% to Critical Hit Chance "
            "(multiplicative modifier). Maximum Power Charges is typically 3, extendable by passives. "
            "Gained from kills with sufficient Power Charge on Kill, specific skills, or passives. "
            "Particularly valuable for crit-based builds."
        ),
        "formula": "+30% Critical Hit Chance per Power Charge.",
        "see_also": ["Charges", "Critical Hits", "usePowerCharges", "PowerChargesMax"],
    },
    {
        "name": "Frenzy Charge",
        "category": "charge",
        "summary": "Each Frenzy Charge grants +5% Attack/Cast Speed and +4% more Damage.",
        "mechanics": (
            "Frenzy Charges are green charges providing both speed and damage bonuses. "
            "Each grants +5% increased Attack and Cast Speed and +4% more Damage. "
            "Maximum is typically 3. Gained from hits against enemies, specific skills, or passives. "
            "Very strong for any offensive build."
        ),
        "formula": "+5% Attack/Cast Speed and +4% more Damage per Frenzy Charge.",
        "see_also": ["Charges", "useFrenzyCharges", "FrenzyChargesMax"],
    },
    {
        "name": "Endurance Charge",
        "category": "charge",
        "summary": "Each Endurance Charge grants +4% Physical Damage Reduction and +4% Elemental Resistances.",
        "mechanics": (
            "Endurance Charges are red charges providing defensive bonuses. "
            "Each grants +4% Physical Damage Reduction and +4% to all Elemental Resistances. "
            "Maximum is typically 3. Gained from Warcries, specific skills, or passives. "
            "Particularly valuable for tanky builds."
        ),
        "formula": "+4% Physical Damage Reduction, +4% all Elemental Resistances per Endurance Charge.",
        "see_also": ["Charges", "Resistances", "useEnduranceCharges", "EnduranceChargesMax"],
    },

    # ── Resources ─────────────────────────────────────────────────────────────

    {
        "name": "Life",
        "category": "resource",
        "summary": "Your main health pool; reaching 0 causes death.",
        "mechanics": (
            "Life is the primary health resource. When reduced to 0 you die (revival may be available). "
            "Life Recharge begins after 4 seconds without taking life damage, recovering 12.5%/s. "
            "Low Life is defined as 35% or less of maximum Life. "
            "Strength grants +2 maximum Life per point."
        ),
        "formula": "Life Recharge: 12.5%/s after 4s delay. Low Life threshold: 35%.",
        "see_also": ["Strength", "Energy Shield", "Low Life", "Leech", "Life Recharge"],
    },
    {
        "name": "Mana",
        "category": "resource",
        "summary": "Resource spent to use skills; regenerates over time.",
        "mechanics": (
            "Mana is spent when using skills. It regenerates naturally over time. "
            "Intelligence grants +2 maximum Mana per point. "
            "Mind Over Matter causes damage to be taken from Mana before Life. "
            "Blood Magic converts all Mana costs to Life costs."
        ),
        "formula": "+2 max Mana per 1 Intelligence. Regen rate varies by build.",
        "see_also": ["Intelligence", "Mind Over Matter", "Blood Magic", "Eldritch Battery", "Low Mana"],
    },
    {
        "name": "Spirit",
        "category": "resource",
        "summary": "Reserve of power used to activate and maintain persistent skills.",
        "mechanics": (
            "Spirit is a resource that is reserved (not spent) to activate persistent skills like "
            "auras, heralds, and other toggled skills. It is not regenerated. "
            "Higher Spirit allows more persistent skills to be active simultaneously. "
            "Sceptres and certain passives grant additional Spirit."
        ),
        "formula": "Spirit is reserved, not consumed. Persistent skills cost Spirit to remain active.",
        "see_also": ["Persistent Skills", "Auras", "Herald Skills", "Reserve"],
    },
    {
        "name": "Rage",
        "category": "resource",
        "summary": "Grants 1% more Attack Damage per Rage; maximum 30 by default.",
        "mechanics": (
            "Rage is a temporary combat resource for specific builds. "
            "Each point of Rage grants 1% more Attack Damage. "
            "Maximum Rage is 30 by default, meaning up to 30% more Attack Damage at full rage. "
            "Rage is generated by attacking and decays when not in combat."
        ),
        "formula": "+1% more Attack Damage per Rage. Max: 30 (moddable). Decays out of combat.",
        "see_also": ["multiplierRage", "RageRegen", "MaximumRage"],
    },
    {
        "name": "Energy",
        "category": "resource",
        "summary": "A build-specific resource generated and spent by certain skills.",
        "mechanics": (
            "Energy is a secondary resource used by specific ascendancy builds or skill gems. "
            "It is generated and spent differently depending on the skill. "
            "Not to be confused with Energy Shield."
        ),
        "formula": "",
        "see_also": ["Spirit", "Rage", "Valour"],
    },

    # ── Buffs ─────────────────────────────────────────────────────────────────

    {
        "name": "Onslaught",
        "category": "buff",
        "summary": "Grants 20% increased Skill Speed and 10% increased movement speed.",
        "mechanics": (
            "Onslaught is a temporary buff that significantly increases skill speed and movement. "
            "It is typically gained on kill or from specific skills. "
            "The effect lasts for a short duration and can be extended by passives."
        ),
        "formula": "+20% Skill Speed, +10% Movement Speed.",
        "see_also": ["Buffs", "buffOnslaught"],
    },
    {
        "name": "Elusive",
        "category": "buff",
        "summary": "Increases Movement Speed and provides a chance to avoid damage.",
        "mechanics": (
            "Elusive grants increased Movement Speed and a chance to avoid incoming damage "
            "(similar to a dodge). The buff fades as it absorbs hits. "
            "It is primarily associated with Shadow/Assassin-type builds and certain skills."
        ),
        "formula": "Grants movement speed and avoidance chance; degrades as it absorbs hits.",
        "see_also": ["Buffs", "Evasion"],
    },
    {
        "name": "Tailwind",
        "category": "buff",
        "summary": "Stacking buff granting 1% increased Movement Speed per stack, up to 10.",
        "mechanics": (
            "Tailwind stacks up to 10 times, each stack granting 1% increased Movement Speed. "
            "At maximum stacks: +10% increased Movement Speed. "
            "Gained from specific skills and ascendancy nodes."
        ),
        "formula": "+1% Movement Speed per stack × max 10 stacks = +10% max.",
        "see_also": ["Buffs"],
    },
    {
        "name": "Arcane Surge",
        "category": "buff",
        "summary": "Grants 15% increased Cast Speed and 20% more Mana Regeneration Rate.",
        "mechanics": (
            "Arcane Surge is a buff triggered when spending Mana on skills. "
            "It grants 15% increased Cast Speed and 20% more Mana Regeneration Rate. "
            "Applied via the Arcane Surge Support gem or specific skill effects."
        ),
        "formula": "+15% Cast Speed, +20% Mana Regeneration Rate.",
        "see_also": ["Buffs", "Mana", "Cast Speed"],
    },
    {
        "name": "Jade",
        "category": "buff",
        "summary": "Stacking buff granting 1% Physical Damage Reduction per stack.",
        "mechanics": (
            "Jade is a stacking defensive buff. Each stack grants 1% additional Physical "
            "Damage Reduction. Gained from specific skills, primarily associated with Monk builds."
        ),
        "formula": "+1% Physical Damage Reduction per stack.",
        "see_also": ["Buffs", "Physical Damage", "Armour"],
    },
    {
        "name": "Ancestral Boost",
        "category": "buff",
        "summary": "Grants 30% more damage and 25% increased area of effect.",
        "mechanics": (
            "Ancestral Boost is a buff linked to Ancestral Totems. "
            "When an Ancestral Totem is active, you receive 30% more damage and "
            "25% increased area of effect while it remains."
        ),
        "formula": "+30% more damage, +25% increased AoE.",
        "see_also": ["Totems", "Buffs", "Ancestral Bond"],
    },

    # ── Debuffs ───────────────────────────────────────────────────────────────

    {
        "name": "Exposure",
        "category": "debuff",
        "summary": "Lowers enemy elemental resistance by 20% for 4 seconds.",
        "mechanics": (
            "Exposure debuffs an enemy's elemental resistance for a specific element "
            "(Fire/Cold/Lightning) by 20% by default. Duration is 4 seconds. "
            "It stacks with Penetration but not with itself — only the strongest exposure applies. "
            "Applied by specific skills and ascendancy nodes."
        ),
        "formula": "-20% elemental resistance to affected type. Duration: 4s.",
        "see_also": ["Resistances", "Penetration", "Fire Damage", "Cold Damage", "Lightning Damage"],
    },
    {
        "name": "Blind",
        "category": "debuff",
        "summary": "Reduces enemy Accuracy Rating and Evasion by 20% for 4 seconds.",
        "mechanics": (
            "Blind is a debuff that reduces the affected target's Accuracy Rating and Evasion "
            "Rating by 20%. Applied by specific skills. Duration is 4 seconds. "
            "Very effective against enemies that rely on high Accuracy."
        ),
        "formula": "-20% Accuracy Rating and -20% Evasion Rating. Duration: 4s.",
        "see_also": ["Accuracy", "Evasion", "Debuffs"],
    },
    {
        "name": "Maim",
        "category": "debuff",
        "summary": "Slows enemy movement by 30% and reduces Evasion by 15%.",
        "mechanics": (
            "Maim is a debuff that reduces enemy movement speed by 30% (Slow) "
            "and reduces their Evasion Rating by 15%. "
            "Applied by physical hits with sufficient Maim chance. Duration varies."
        ),
        "formula": "-30% movement speed (Slow), -15% Evasion Rating.",
        "see_also": ["Slow", "Evasion", "Physical Damage", "Debuffs"],
    },
    {
        "name": "Hinder",
        "category": "debuff",
        "summary": "Slows enemy movement speed by 30%.",
        "mechanics": (
            "Hinder is a movement slow debuff reducing movement speed by 30% unless otherwise "
            "specified. Multiple sources of Hinder do not stack — only the strongest applies."
        ),
        "formula": "-30% movement speed.",
        "see_also": ["Slow", "Maim", "Debuffs"],
    },
    {
        "name": "Intimidate",
        "category": "debuff",
        "summary": "Enemy takes 10% increased damage and deals 10% reduced damage.",
        "mechanics": (
            "Intimidate is a debuff applied to enemies that causes them to both deal less damage "
            "and take more damage. Duration and application vary by source. "
            "It is gained from certain ascendancy passives and skill modifiers."
        ),
        "formula": "+10% increased damage taken, -10% damage dealt.",
        "see_also": ["Debuffs", "conditionChampionIntimidate"],
    },
    {
        "name": "Crushed",
        "category": "debuff",
        "summary": "Lowers target's Physical Damage Reduction by 15%.",
        "mechanics": (
            "Crushed is a debuff that reduces Physical Damage Reduction by 15%. "
            "This effectively reduces the benefit they get from Armour. "
            "Applied by specific skills and modifiers."
        ),
        "formula": "-15% Physical Damage Reduction.",
        "see_also": ["Armour", "Physical Damage", "Overwhelm", "Debuffs"],
    },
    {
        "name": "Overwhelm",
        "category": "debuff",
        "summary": "Negates a percentage of the target's Physical Damage Reduction.",
        "mechanics": (
            "Overwhelm is a modifier (not a debuff) that ignores a percentage of the target's "
            "Physical Damage Reduction from Armour. It is a property of the attacker, not a "
            "status on the target. Effective for bypassing heavily armoured enemies."
        ),
        "formula": "Target's effective Physical Damage Reduction reduced by Overwhelm %.",
        "see_also": ["Armour", "Physical Damage", "Crushed"],
    },
    {
        "name": "Curses",
        "category": "debuff",
        "summary": "Powerful debuffs affecting a single target; default limit of 1 per target.",
        "mechanics": (
            "Curses significantly debuff targets with various effects. Only one Curse can be "
            "active per target by default. The Hex Master and Whispers of Doom keystones allow "
            "an additional Curse. Marks are a family of single-target Curses with unique effects."
        ),
        "formula": "1 Curse per target by default.",
        "see_also": ["Marks", "Hex Master", "Whispers of Doom", "Enfeeble", "Debuffs"],
    },
    {
        "name": "Marks",
        "category": "debuff",
        "summary": "Powerful single-target Debuffs with special activation effects.",
        "mechanics": (
            "Marks are a family of single-target Curses. They apply effects to one target "
            "and can be Activated for a powerful secondary effect. "
            "Only one Mark can be active per target at once."
        ),
        "formula": "",
        "see_also": ["Curses", "Debuffs"],
    },
    {
        "name": "Slow",
        "category": "debuff",
        "summary": "Reduces action speed; effects are always multiplicative with each other.",
        "mechanics": (
            "Slow reduces how quickly an enemy performs actions. Unlike most modifiers in PoE2, "
            "multiple Slow sources are multiplicative with each other rather than additive. "
            "Chill, Maim, Hinder, and Freeze Buildup all contribute Slow."
        ),
        "formula": "Multiple Slow sources are multiplicative: total = (1 − slow1) × (1 − slow2) × …",
        "see_also": ["Chill", "Maim", "Hinder", "Freeze"],
    },

    # ── Mechanics ─────────────────────────────────────────────────────────────

    {
        "name": "Recently",
        "category": "mechanic",
        "summary": "Refers to the past 4 seconds.",
        "mechanics": (
            "When a passive, modifier, or condition uses 'recently', it refers to events that "
            "occurred within the last 4 seconds. Examples: 'Killed Recently', 'Used a Skill Recently', "
            "'Hit a Rare or Unique Enemy Recently'."
        ),
        "formula": "Time window: 4 seconds.",
        "see_also": ["conditionKilledRecently", "conditionCritRecently", "Conditions"],
    },
    {
        "name": "Low Life",
        "category": "mechanic",
        "summary": "Below 35% of maximum Life.",
        "mechanics": (
            "A character or monster is considered on Low Life when their current Life is at "
            "or below 35% of their maximum Life. Many passives and skills have bonuses "
            "or penalties that trigger when on Low Life."
        ),
        "formula": "Low Life threshold: 35% of maximum Life.",
        "see_also": ["Life", "Pain Attunement", "Culling Strike"],
    },
    {
        "name": "Stun",
        "category": "mechanic",
        "summary": "Interrupts enemy actions; Light Stuns briefly, Heavy Stuns for multiple seconds.",
        "mechanics": (
            "Light Stuns interrupt the current action for a fraction of a second. "
            "Heavy Stuns occur when Stun buildup fills the Stun bar and last multiple seconds. "
            "Stun buildup scales with hit damage vs enemy Stun Threshold (based on their max life). "
            "Enemies Primed for Stun take Heavy Stuns from Crushing Blows."
        ),
        "formula": "Heavy Stun buildup threshold = enemy max life. Light Stun base chance: 15%.",
        "see_also": ["Daze", "Heavy Stun", "Crushing Blows", "Primed for Stun", "Immobilised"],
    },
    {
        "name": "Lucky",
        "category": "mechanic",
        "summary": "Roll twice, take the better result.",
        "mechanics": (
            "When something is Lucky, it is rolled twice and the more favourable result is used. "
            "For damage, this means the higher of two rolls. For chance, the higher probability result. "
            "Glancing Blows makes Evasion Unlucky and Deflect Lucky."
        ),
        "formula": "P(success) = 1 − (1 − p)² for Lucky chance rolls.",
        "see_also": ["Unlucky", "Glancing Blows"],
    },
    {
        "name": "Unlucky",
        "category": "mechanic",
        "summary": "Roll twice, take the worse result.",
        "mechanics": (
            "When something is Unlucky, it is rolled twice and the less favourable result is used. "
            "For damage, this means the lower of two rolls. For chance, the lower probability result."
        ),
        "formula": "P(success) = p² for Unlucky chance rolls.",
        "see_also": ["Lucky", "Glancing Blows"],
    },
    {
        "name": "Recoup",
        "category": "mechanic",
        "summary": "Recover a percentage of damage taken as Life/ES/Mana over 8 seconds.",
        "mechanics": (
            "Recoup returns a percentage of damage taken back to the player over 8 seconds. "
            "It is not the same as regeneration — it specifically recovers based on how much "
            "damage was taken. Multiple sources of Recoup stack."
        ),
        "formula": "Recovery over 8 seconds = damage_taken × recoup_%.",
        "see_also": ["Life", "Energy Shield", "Mana", "Leech"],
    },
    {
        "name": "Reserve",
        "category": "mechanic",
        "summary": "Prevents a portion of a resource from being used for other purposes.",
        "mechanics": (
            "Reservation sets aside a portion of Life, Mana, or Spirit so it cannot be spent "
            "but maintains a persistent effect (aura, herald, etc.). "
            "Spirit is always reserved rather than spent. "
            "Blood Magic can affect reservation of Mana by converting it to Life reservation."
        ),
        "formula": "Reserved amount unavailable for normal use while effect is active.",
        "see_also": ["Spirit", "Mana", "Life", "Auras", "Blood Magic"],
    },
    {
        "name": "Immobilised",
        "category": "mechanic",
        "summary": "Cannot move; caused by Freeze, Pin, Petrify, or Heavy Stun.",
        "mechanics": (
            "A target is Immobilised if it cannot move due to Freeze, Pin (from Pin buildup), "
            "Petrify, or Heavy Stun. Immobilised targets are unable to dodge or reposition. "
            "Different sources of Immobilise have different durations and removal conditions."
        ),
        "formula": "",
        "see_also": ["Freeze", "Stun", "Petrify", "Pinned"],
    },
    {
        "name": "Surrounding",
        "category": "mechanic",
        "summary": "You are Surrounded if at least 5 enemies are within 3 metres.",
        "mechanics": (
            "The Surrounded condition is active when 5 or more enemies are within 3 metres "
            "of the player. Several passives and skills provide bonuses or trigger effects "
            "when Surrounded."
        ),
        "formula": "Surrounded: ≥5 enemies within 3m.",
        "see_also": ["Mechanics", "conditionSurrounded"],
    },
    {
        "name": "Pinned",
        "category": "mechanic",
        "summary": "Prevents enemy movement once Pin buildup reaches the Pin Threshold.",
        "mechanics": (
            "Pin buildup accumulates from physical hits. When it exceeds the Pin Threshold "
            "(proportional to enemy max life), the target is Pinned and cannot move. "
            "Normal enemies require less buildup than rare/unique monsters."
        ),
        "formula": "Pin threshold: 500% of ailment threshold for players. Duration: 3s (monsters), 2s (players).",
        "see_also": ["Stun", "Immobilised", "Physical Damage"],
    },
    {
        "name": "Daze",
        "category": "mechanic",
        "summary": "Dazed enemies take 50% more Stun Buildup for 8 seconds.",
        "mechanics": (
            "Daze is a debuff that amplifies Stun buildup on the target. "
            "A Dazed enemy takes 50% more Stun Buildup, making Heavy Stuns easier to apply. "
            "Duration is 8 seconds."
        ),
        "formula": "+50% Stun Buildup taken while Dazed. Duration: 8s.",
        "see_also": ["Stun", "Heavy Stun", "Debuffs"],
    },

    # ── Skill Keywords ────────────────────────────────────────────────────────

    {
        "name": "Attacks",
        "category": "keyword",
        "summary": "Skills that use weapon stats to deal damage directly.",
        "mechanics": (
            "Attacks use your equipped weapon's damage and stats. They check Accuracy against "
            "target Evasion and can trigger on-hit effects. Attack speed is affected by "
            "weapon attack speed and Dexterity-based mods. Most melee and ranged skills are Attacks."
        ),
        "formula": "",
        "see_also": ["Spells", "Melee", "Accuracy", "Hit Damage"],
    },
    {
        "name": "Spells",
        "category": "keyword",
        "summary": "Skills using raw magic; do not use weapon damage, always hit.",
        "mechanics": (
            "Spells use raw magical damage independent of weapon stats. "
            "They always hit (no Accuracy check) and are affected by Cast Speed instead of "
            "Attack Speed. Spell damage scales with Intelligence-based modifiers and "
            "spell damage increases."
        ),
        "formula": "",
        "see_also": ["Attacks", "Cast Speed", "Intelligence"],
    },
    {
        "name": "Melee",
        "category": "keyword",
        "summary": "Attacks that directly hit with a melee weapon or unarmed.",
        "mechanics": (
            "Melee attacks are close-range Attacks made with melee weapons or unarmed. "
            "They include Strikes (single-target) and Slams (area of effect). "
            "Melee attacks benefit from Melee Damage modifiers and are affected by Strength."
        ),
        "formula": "",
        "see_also": ["Attacks", "Strike", "Slam", "Strength", "Unarmed"],
    },
    {
        "name": "Projectile",
        "category": "keyword",
        "summary": "Moving Attack or Spell that damages targets it collides with.",
        "mechanics": (
            "Projectile skills fire moving objects that deal damage on impact. "
            "They can Pierce, Fork, Chain, or Split to hit multiple targets. "
            "Projectile distance and speed can be modified. "
            "Bows and Wands fire Projectiles."
        ),
        "formula": "",
        "see_also": ["Pierce", "Fork", "Chain", "Split", "Attacks"],
    },
    {
        "name": "Area of Effect",
        "category": "keyword",
        "summary": "Skill that applies its effect to all targets in a defined area.",
        "mechanics": (
            "AoE skills hit every valid target within their area simultaneously. "
            "Area size can be increased by AoE modifiers. "
            "Slams and many spells are AoE skills."
        ),
        "formula": "Area scales with AoE modifiers.",
        "see_also": ["Slam", "Skills", "Nova Skills"],
    },
    {
        "name": "Channelling",
        "category": "keyword",
        "summary": "Skills held down to gain power or continue their effect.",
        "mechanics": (
            "Channelled skills require holding the button down. They often ramp up in power "
            "the longer they are channelled. Channelling can be interrupted by Stun. "
            "Skill Speed affects channel tick rate."
        ),
        "formula": "",
        "see_also": ["Skills", "Stun", "Skill Speed"],
    },
    {
        "name": "Persistent Skills",
        "category": "keyword",
        "summary": "Toggled skills that remain active and often require Spirit.",
        "mechanics": (
            "Persistent skills are toggled on/off in the Skills panel. "
            "They commonly reserve Spirit to stay active (auras, heralds). "
            "They provide continuous effects rather than one-time use."
        ),
        "formula": "",
        "see_also": ["Spirit", "Auras", "Herald Skills", "Reserve"],
    },
    {
        "name": "Triggered Skills",
        "category": "keyword",
        "summary": "Occur immediately without attack or cast time when a condition is met.",
        "mechanics": (
            "Triggered skills fire automatically when their trigger condition is met "
            "(e.g. on hit, on kill, when you use a skill). They have no cast or attack time "
            "overhead. Often used in conjunction with Traps, Mines, or on-hit effects."
        ),
        "formula": "",
        "see_also": ["Skills", "Traps"],
    },
    {
        "name": "Warcries",
        "category": "keyword",
        "summary": "Skills that empower subsequent Melee Attacks based on nearby enemy power.",
        "mechanics": (
            "Warcries count enemy Power within their area and use it to Exert Attacks. "
            "Exerted Attacks gain powerful bonuses based on the Warcry used. "
            "Warcry cooldown recovery can be boosted, and Endurance Charges often interact with them."
        ),
        "formula": "Exert count scales with enemy Power in area.",
        "see_also": ["Melee", "Endurance Charge", "Skills"],
    },
    {
        "name": "Totems",
        "category": "keyword",
        "summary": "Allied constructs that use your skills for you, benefiting from your stats.",
        "mechanics": (
            "Totems are placed constructs that automatically use the linked skill. "
            "They use your character's stats for damage calculation. "
            "Ancestral Bond doubles Totem limit but prevents you from dealing damage directly. "
            "Each Totem reserves 75 Spirit with Ancestral Bond."
        ),
        "formula": "Default Totem limit: 1 (extendable). Totems use player stats.",
        "see_also": ["Ancestral Bond", "Ancestral Boost", "Skills", "Spirit"],
    },
    {
        "name": "Minions",
        "category": "keyword",
        "summary": "Summoned allies that fight alongside you with their own stats.",
        "mechanics": (
            "Minions are creatures summoned by the player. Unlike Totems, Minions use their "
            "own stats (modified by your Minion modifiers) rather than your character's stats. "
            "Necromantic Talisman transfers your amulet bonuses to Minions instead of you."
        ),
        "formula": "",
        "see_also": ["Totems", "Necromantic Talisman", "Skills"],
    },
    {
        "name": "Strike",
        "category": "keyword",
        "summary": "A melee attack that directly hits with a weapon.",
        "mechanics": (
            "Strikes are direct melee attacks that hit a single primary target (though some "
            "have built-in AoE). They benefit from Strike-specific modifiers in addition to "
            "general melee and attack modifiers."
        ),
        "formula": "",
        "see_also": ["Melee", "Slam", "Attacks"],
    },
    {
        "name": "Slam",
        "category": "keyword",
        "summary": "Melee attacks that create a damaging area of effect.",
        "mechanics": (
            "Slams are melee attacks that deal AoE damage around the impact point. "
            "They benefit from both Melee Damage and AoE modifiers. "
            "Slam skills generally have higher damage but lower speed than Strikes."
        ),
        "formula": "",
        "see_also": ["Melee", "Strike", "Area of Effect"],
    },

    # ── PoE2 Combat Mechanics ─────────────────────────────────────────────────

    {
        "name": "Combo",
        "category": "mechanic",
        "summary": "Strike skills build Combo stacks, which Finisher skills consume for enhanced effects.",
        "mechanics": (
            "Combo (ComboStacks) is built by successfully Striking enemies. "
            "Some skills and effects require a minimum Combo count to use. "
            "Finisher skills consume all Combo stacks when activated for a powerful effect. "
            "Maximum Combo stacks vary by build and passive investment."
        ),
        "formula": "Combo built per Strike: 1 (base). Finisher consumes all stacks on use.",
        "see_also": ["Finisher", "Strike", "multiplierCombo", "ComboStacks"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Finisher",
        "category": "mechanic",
        "summary": "Skills that require and consume Combo stacks for a powerful effect.",
        "mechanics": (
            "Finisher skills are activated when you have sufficient Combo stacks. "
            "They consume all Combo on use and deal significantly enhanced damage or apply "
            "powerful effects. They are a subset of Strike skills available to classes that "
            "build Combo (e.g. Warrior, Monk)."
        ),
        "formula": "",
        "see_also": ["Combo", "Strike", "Melee"],
        "source": "PoB:SkillTypes",
    },
    {
        "name": "Parry",
        "category": "mechanic",
        "summary": "Monk defensive mechanic: successful Parry debuffs the attacker, making them take 50% more Attack Damage.",
        "mechanics": (
            "Parry is a Monk-specific ability. When you successfully Parry an attack, "
            "the attacker gains the Parry debuff. While a target has the Parry debuff, "
            "they take 50% more Attack Damage from you. "
            "Parry can be activated as a reaction skill in the skill bar."
        ),
        "formula": "Parry debuff: enemy takes 50% more Attack Damage.",
        "see_also": ["Guard", "parryActive", "conditionParryActive"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Exerted Attack",
        "category": "mechanic",
        "summary": "Warcries empower your next N attacks as 'Exerted Attacks' with bonus effects.",
        "mechanics": (
            "When you use a Warcry, your next few attacks become Exerted Attacks. "
            "Exerted Attacks gain bonus effects specific to the Warcry used "
            "(e.g. Infernal Cry adds Combustion, Rallying Cry adds damage). "
            "The number of attacks exerted scales with Warcry Power (nearby enemy strength). "
            "Support gems like Battershout interact specifically with Exerted Attacks."
        ),
        "formula": "Exert count = base + scales with Warcry Power (1 per Normal, 2 Magic, 10 Rare, 20 Unique enemy).",
        "see_also": ["Warcries", "multiplierWarcryPower", "bannerValour"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Armour Break",
        "category": "mechanic",
        "summary": "Debuff that reduces enemy Armour; Fully Broken Armour sets it to 0 for 12 seconds.",
        "mechanics": (
            "Armour Break reduces a target's Armour by a specified amount per stack. "
            "If Armour is reduced to 0 the target becomes Fully Broken: their Armour is "
            "overridden to 0 for 12 seconds, meaning physical hits bypass all Armour mitigation. "
            "Some skills can break Armour below 0 (stated explicitly on the skill). "
            "Not to be confused with the Crushed debuff, which reduces Physical Damage Reduction by 15%."
        ),
        "formula": "Fully Broken: Armour = 0 for 12 seconds. Stacks reduce Armour by 1 per stack.",
        "see_also": ["Armour", "Crushed", "conditionEnemyArmourBroken", "multiplierArmourBreak"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Ailment Threshold",
        "category": "mechanic",
        "summary": "Minimum hit size required to apply non-damaging ailments (Chill, Freeze, Shock, Electrocute).",
        "mechanics": (
            "Non-damaging ailments are only applied if the hit exceeds the enemy's Ailment Threshold. "
            "Threshold is a percentage of the enemy's maximum life. "
            "For maps and bosses the threshold is high, making large hits required to reliably ailment. "
            "Ailment Threshold modifiers directly increase or decrease this requirement. "
            "This mechanic replaced PoE1's instant Freeze from any cold hit."
        ),
        "formula": "Ailment applied if: hit damage ≥ enemy ailment threshold (% of max life).",
        "see_also": ["Chill", "Freeze", "Shock", "Electrocute", "Freeze Buildup"],
        "source": "manual",
    },
    {
        "name": "Freeze Buildup",
        "category": "mechanic",
        "summary": "Cold hits accumulate Freeze Buildup on enemies; reaching 100% applies Freeze.",
        "mechanics": (
            "Unlike PoE1, Freeze in PoE2 is not applied instantly. Instead, cold hits add Freeze "
            "Buildup proportional to the hit size relative to the enemy's max life. "
            "When Buildup reaches 100%, the enemy becomes Frozen. "
            "Buildup decays over time if hits stop. "
            "Skills and modifiers that say 'increased Freeze Buildup' accelerate this accumulation."
        ),
        "formula": "Buildup per hit = cold_hit / enemy_ailment_threshold × 100%.",
        "see_also": ["Freeze", "Cold Damage", "Ailment Threshold", "Chill"],
        "source": "manual",
    },
    {
        "name": "Trinity",
        "category": "mechanic",
        "summary": "Spirit skill that builds Resonance by alternating fire/cold/lightning hits; triggers powerful elemental explosions.",
        "mechanics": (
            "Trinity is a persistent Spirit skill that generates Resonance when you hit an enemy "
            "with a damage type different from your last hit (fire → cold → lightning cycling). "
            "Resonance stacks from 0–300. At 200 Resonance (configResonanceCount=200 for PoB), "
            "Trinity triggers bonus explosions on kill and grants elemental penetration. "
            "Builds that deal multiple element types in a single hit (via conversion or dual elements) "
            "generate Resonance efficiently."
        ),
        "formula": "Resonance max: 300. PoB config: configResonanceCount (0–300).",
        "see_also": ["Resonance", "Spirit", "Aura", "configResonanceCount", "Damage Conversion"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Resonance",
        "category": "mechanic",
        "summary": "Resource built by the Trinity skill; enables its damage and explosion bonuses.",
        "mechanics": (
            "Resonance is the internal counter for the Trinity skill, ranging from 0 to 300. "
            "It is gained by hitting enemies with different elemental damage types consecutively. "
            "Higher Resonance unlocks stronger Trinity effects. "
            "In PoB, set configResonanceCount to 200 for a realistic combat scenario with Trinity."
        ),
        "formula": "Range: 0–300. Set configResonanceCount in PoB for accurate DPS.",
        "see_also": ["Trinity", "configResonanceCount", "Fire Damage", "Cold Damage", "Lightning Damage"],
        "source": "PoB:ConfigOptions",
    },

    # ── Additional Skill Keywords ──────────────────────────────────────────────

    {
        "name": "Aura",
        "category": "keyword",
        "summary": "Persistent Spirit-reservation skills that grant buffs to you and nearby allies.",
        "mechanics": (
            "Auras reserve a portion of your Spirit while active and continuously grant their "
            "effects to you and nearby party members. Unlike PoE1, PoE2 auras use Spirit "
            "rather than Mana. Common auras: Haste, Grace, Determination, Discipline. "
            "Aura effect modifiers scale how powerful the granted buff is."
        ),
        "formula": "Cost: Spirit reservation (flat). Effect scales with Aura Effect %.",
        "see_also": ["Spirit", "Herald", "Reserve", "Persistent Skills"],
        "source": "PoB:SkillTypes",
    },
    {
        "name": "Herald",
        "category": "keyword",
        "summary": "Persistent Spirit-reservation skills that grant bonuses on kill or on hit.",
        "mechanics": (
            "Heralds reserve Spirit and grant a passive bonus plus a triggered effect when you "
            "kill or hit enemies. Examples: Herald of Ice (shatters frozen enemies on kill), "
            "Herald of Ash (burns enemies on overkill), Herald of Thunder (calls lightning on kill). "
            "Herald effect modifiers scale their proc damage and buff strength."
        ),
        "formula": "Cost: Spirit reservation. Trigger condition varies per Herald.",
        "see_also": ["Aura", "Spirit", "Reserve", "conditionCritWithHeraldSkillRecently"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Banner",
        "category": "keyword",
        "summary": "Persistent area skills planted as flags; build Valour stacks and grant aura effects when placed.",
        "mechanics": (
            "Banners are initially kept active in hand (providing a basic aura effect). "
            "When planted, they become stationary and gain power from Valour stacks "
            "built up while the banner was held. Planted banners grant a stronger aura effect "
            "to nearby allies. Banners are destroyed if you move too far away. "
            "PoB config: bannerValour controls the Valour amount when placed."
        ),
        "formula": "Valour = enemy kills while banner held. Placed effect scales with Valour consumed.",
        "see_also": ["Aura", "Spirit", "bannerValour", "Warcries"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Trap",
        "category": "keyword",
        "summary": "Skills thrown as Traps that trigger when an enemy walks over them.",
        "mechanics": (
            "Trap skills are thrown by the player and placed as objects on the ground. "
            "They trigger automatically when an enemy comes within proximity. "
            "Traps can be supported by Trap-specific support gems. "
            "Multiple traps can be active simultaneously up to the trap limit. "
            "Trap throw speed and trigger radius are moddable."
        ),
        "formula": "Default trap limit: 3 (moddable). Trigger: enemy proximity.",
        "see_also": ["Mine", "Triggered Skills", "multiplierTrapTriggeredRecently"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Mine",
        "category": "keyword",
        "summary": "Skills thrown as Mines that must be manually detonated.",
        "mechanics": (
            "Mine skills are thrown by the player and placed on the ground. "
            "Unlike Traps they do not auto-trigger — they are detonated manually "
            "using the Detonate Mines skill. Multiple mines can be active simultaneously. "
            "Mines can be supported by Mine-specific support gems and benefit from "
            "mine throw speed and detonation chain modifiers."
        ),
        "formula": "Default mine limit: varies by skill. Detonation: manual via Detonate Mines.",
        "see_also": ["Trap", "Triggered Skills", "multiplierMineDetonatedRecently"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Guard",
        "category": "keyword",
        "summary": "Skills that provide a temporary absorption layer or defensive reaction.",
        "mechanics": (
            "Guard skills create a temporary protective effect that absorbs or mitigates "
            "incoming damage for a short duration. Examples: Molten Shell (armour shell that "
            "absorbs hits), Steelskin (temporary life buffer). "
            "Guard skills typically have a cooldown and are triggered or manually activated. "
            "In PoE2 Guard skills include Barrier Invocation-type effects."
        ),
        "formula": "Absorption varies per skill. Duration: 2–4 seconds typically.",
        "see_also": ["Energy Shield", "Armour", "Triggered Skills", "Parry"],
        "source": "PoB:SkillTypes",
    },
    {
        "name": "Invocation",
        "category": "keyword",
        "summary": "Meta Spirit skills that store energy from hits and release powerful effects when fully charged.",
        "mechanics": (
            "Invocation skills (Barrier Invocation, Elemental Invocation, Feral Invocation, "
            "Reaper's Invocation) are persistent Trigger-type skills that accumulate Energy "
            "from hits and release a powerful effect once fully charged. "
            "They are tagged Persistent, Trigger, Invocation, Meta in PoB. "
            "Invocations use Spirit for reservation and trigger automatically — no manual activation."
        ),
        "formula": "Energy threshold varies per Invocation skill. Trigger: automatic at full charge.",
        "see_also": ["Spirit", "Aura", "Herald", "Triggered Skills", "GeneratesEnergy"],
        "source": "PoB:Gems",
    },
    {
        "name": "Shapeshift",
        "category": "keyword",
        "summary": "Class mechanic (Druid/Warbringer) that transforms you into an animal form with different skills.",
        "mechanics": (
            "Shapeshift transforms the player into a form (Wolf, Bear, Wyvern) with a dedicated "
            "skill bar and different stat scaling. Shapeshifted forms often have higher base "
            "movement speed and access to form-specific skills. "
            "Returning to human form is treated as Shapeshifting to human (conditionShapeshiftToHuman). "
            "Modifiers to Shapeshift forms only apply while in that form."
        ),
        "formula": "",
        "see_also": ["conditionShapeshifted", "conditionShapeshiftToAnimal", "conditionShapeshiftToHuman"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Duration",
        "category": "keyword",
        "summary": "Skills and effects with Duration last for a set time; Duration modifiers extend this.",
        "mechanics": (
            "Many skills, buffs, and debuffs have a Duration tag meaning their effect expires "
            "after a set number of seconds. Increased Duration modifiers extend how long they last. "
            "Skills tagged Duration benefit from support gems like Intensify and Persistence. "
            "Base duration varies per skill and is shown in the skill description."
        ),
        "formula": "Effective duration = base_duration × (1 + increased_duration / 100).",
        "see_also": ["Channelling", "Persistent Skills", "Triggered Skills", "Cooldown"],
        "source": "PoB:SkillTypes",
    },
    {
        "name": "Cooldown",
        "category": "keyword",
        "summary": "Rate limit on skill use; Cooldown Recovery Rate reduces the wait between uses.",
        "mechanics": (
            "Skills with a Cooldown cannot be used again until the cooldown period expires. "
            "Cooldown Recovery Rate (%) reduces the effective cooldown time proportionally. "
            "At 100% increased Cooldown Recovery Rate the cooldown is halved. "
            "Some skills have independent cooldowns per instance (traps, mines). "
            "PoB supports both base and average cooldown calculation modes."
        ),
        "formula": "Effective cooldown = base_cooldown / (1 + cooldown_recovery_rate / 100).",
        "see_also": ["Trap", "Mine", "Travel", "cooldownMode"],
        "source": "PoB:ConfigOptions",
    },
    {
        "name": "Companion",
        "category": "keyword",
        "summary": "Persistent beast ally summoned by certain skills; uses your presence to apply buffs.",
        "mechanics": (
            "Companion skills summon a persistent beast that fights alongside you. "
            "Unlike regular Minions, Companions interact with 'Companion in Presence' conditions, "
            "enabling specific passive and item bonuses. "
            "Companions can have their own buff and curse skills enabled in PoB config. "
            "A Companion can absorb damage taken before you (with certain items/passives)."
        ),
        "formula": "",
        "see_also": ["Minions", "summonCompanionEnableBuffs", "companionInPresence", "TotalCompanionLife"],
        "source": "PoB:ConfigOptions",
    },

    # ── Keystones ─────────────────────────────────────────────────────────────

    {
        "name": "Chaos Inoculation",
        "category": "keystone",
        "summary": "Maximum Life is 1; immune to Chaos Damage and Bleeding.",
        "mechanics": (
            "Chaos Inoculation sets your maximum Life to 1, making you almost entirely reliant "
            "on Energy Shield for survival. In exchange, you become immune to Chaos Damage "
            "and Bleeding. Very powerful for high-ES builds."
        ),
        "formula": "Max Life = 1. Full Chaos immunity.",
        "see_also": ["Energy Shield", "Chaos Damage", "Life"],
    },
    {
        "name": "Iron Reflexes",
        "category": "keystone",
        "summary": "Converts all Evasion Rating to Armour.",
        "mechanics": (
            "Iron Reflexes converts your total Evasion Rating into an equivalent amount of Armour. "
            "This sacrifices your evasion chance entirely in exchange for greatly increased "
            "physical damage reduction from a much higher Armour pool."
        ),
        "formula": "All Evasion Rating → added to Armour. Evasion chance becomes 0.",
        "see_also": ["Armour", "Evasion", "Dexterity"],
    },
    {
        "name": "Eldritch Battery",
        "category": "keystone",
        "summary": "Converts all Energy Shield to Mana; skills spend Mana instead of ES.",
        "mechanics": (
            "Eldritch Battery converts 100% of maximum Energy Shield into maximum Mana. "
            "This greatly increases your Mana pool but removes Energy Shield as a defensive layer. "
            "Combined with Mind Over Matter, skills drain Mana which is protected by the former ES."
        ),
        "formula": "Max Mana += (Max ES × conversion). Max ES becomes 0.",
        "see_also": ["Energy Shield", "Mana", "Mind Over Matter"],
    },
    {
        "name": "Mind Over Matter",
        "category": "keystone",
        "summary": "Damage is taken from Mana before Life.",
        "mechanics": (
            "Mind Over Matter causes a portion of incoming damage (before mitigation) to be taken "
            "from Mana instead of Life. The percentage taken from Mana depends on your Mana "
            "relative to Life. Mana must be above 0 for the effect to work."
        ),
        "formula": "Portion of incoming damage redirected to Mana before hitting Life.",
        "see_also": ["Mana", "Life", "Eldritch Battery"],
    },
    {
        "name": "Blood Magic",
        "category": "keystone",
        "summary": "You have no Mana; all skill Mana costs converted to Life costs.",
        "mechanics": (
            "Blood Magic sets your maximum Mana to 0 and converts all skill costs to Life costs. "
            "This frees up gear from needing Mana and allows Life to power all skills, "
            "but requires careful Life management."
        ),
        "formula": "Max Mana = 0. All skill costs use Life instead.",
        "see_also": ["Life", "Mana", "Reserve"],
    },
    {
        "name": "Resolute Technique",
        "category": "keystone",
        "summary": "Accuracy Rating is doubled; never deal Critical Hits.",
        "mechanics": (
            "Resolute Technique provides 100% Hit Chance (by doubling Accuracy effectively past cap) "
            "at the cost of completely disabling Critical Hits. "
            "Useful for builds that do not invest in crit but want guaranteed hits."
        ),
        "formula": "Hit Chance = 100%. Critical Hit Chance = 0%.",
        "see_also": ["Accuracy", "Critical Hits", "Attacks"],
    },
    {
        "name": "Vaal Pact",
        "category": "keystone",
        "summary": "50% more Life Leeched but Leech recovers Life 67% less quickly.",
        "mechanics": (
            "Vaal Pact doubles the amount Leeched per hit (50% more Life Leech rate) "
            "but reduces the rate at which Leech recovers Life by 67%. "
            "This means larger but slower recovery bursts."
        ),
        "formula": "+50% Leech rate, −67% Leech recovery speed.",
        "see_also": ["Leech", "Life"],
    },
    {
        "name": "Avatar of Fire",
        "category": "keystone",
        "summary": "75% of damage converted to Fire; deal no non-Fire damage.",
        "mechanics": (
            "Avatar of Fire converts 75% of all damage to Fire Damage and prevents dealing "
            "any non-Fire damage. This allows stacking a single damage type (Fire) and "
            "benefits from both source and fire damage modifiers on converted damage."
        ),
        "formula": "75% of all damage → Fire. Cannot deal non-Fire damage.",
        "see_also": ["Fire Damage", "Damage Conversion", "Ignite"],
    },
    {
        "name": "Glancing Blows",
        "category": "keystone",
        "summary": "Evasion chance is Unlucky; Deflect chance is Lucky.",
        "mechanics": (
            "Glancing Blows makes your Evasion roll Unlucky (rolled twice, takes worse result) "
            "but makes your Deflect roll Lucky (rolled twice, takes better result). "
            "This shifts your defence profile away from Evasion and toward Deflect."
        ),
        "formula": "Evasion: Unlucky (p²). Deflect: Lucky (1−(1−p)²).",
        "see_also": ["Evasion", "Deflect", "Lucky", "Unlucky"],
    },
    {
        "name": "Ancestral Bond",
        "category": "keystone",
        "summary": "Totem Limit doubled; Totems reserve 75 Spirit each; you deal no damage.",
        "mechanics": (
            "Ancestral Bond doubles the maximum number of Totems you can have active. "
            "Each Totem costs 75 Spirit to maintain. The trade-off is that you personally "
            "cannot deal damage — only your Totems can."
        ),
        "formula": "Totem limit ×2. Each Totem reserves 75 Spirit. Player damage = 0.",
        "see_also": ["Totems", "Spirit", "Ancestral Boost"],
    },
    {
        "name": "Pain Attunement",
        "category": "keystone",
        "summary": "30% less Critical Damage Bonus when on Full Life.",
        "mechanics": (
            "Pain Attunement reduces your Critical Hit Damage bonus by 30% while you are on "
            "Full Life. This encourages staying at low or moderate life levels to maintain "
            "full Critical Hit effectiveness. Often paired with life-spending mechanics."
        ),
        "formula": "−30% Critical Damage Bonus while at full Life.",
        "see_also": ["Critical Hits", "Life", "Low Life"],
    },

    # ── Projectile Modifiers ──────────────────────────────────────────────────

    {
        "name": "Pierce",
        "category": "projectile",
        "summary": "Projectile passes through targets while dealing damage to each.",
        "mechanics": (
            "Piercing projectiles travel through targets without stopping. "
            "Each target they pass through takes damage. Useful for hitting multiple enemies "
            "in a line. Pierce chance can be set to 100% by modifiers."
        ),
        "formula": "",
        "see_also": ["Projectile", "Fork", "Chain", "Split"],
    },
    {
        "name": "Fork",
        "category": "projectile",
        "summary": "Projectile splits into two on its first collision.",
        "mechanics": (
            "A Forking projectile splits into two new projectiles travelling at angles "
            "when it first hits a target or surface. Each fork can then hit additional enemies. "
            "Good for area coverage."
        ),
        "formula": "",
        "see_also": ["Projectile", "Pierce", "Chain", "Split"],
    },
    {
        "name": "Chain",
        "category": "projectile",
        "summary": "Projectile redirects to a nearby target after each collision.",
        "mechanics": (
            "Chaining projectiles bounce between targets. After hitting, the projectile "
            "seeks the nearest valid target and redirects toward it. "
            "The number of chains is limited but can be increased by modifiers."
        ),
        "formula": "",
        "see_also": ["Projectile", "Pierce", "Fork", "Split"],
    },
    {
        "name": "Split",
        "category": "projectile",
        "summary": "Projectile splits into multiple projectiles on collision.",
        "mechanics": (
            "A Splitting projectile creates multiple child projectiles when it hits. "
            "Unlike Fork (two at angles), Split creates several projectiles that fan out. "
            "Useful for wide area coverage."
        ),
        "formula": "",
        "see_also": ["Projectile", "Fork", "Pierce", "Chain"],
    },

    # ── Ground Effects ────────────────────────────────────────────────────────

    {
        "name": "Shocked Ground",
        "category": "ground",
        "summary": "Area of ground that Shocks entities standing in it for 6 seconds.",
        "mechanics": (
            "Shocked Ground applies Shock to any entity standing within it. "
            "The ground effect lasts 6 seconds by default. "
            "It can be created by certain lightning skills."
        ),
        "formula": "Duration: 6s.",
        "see_also": ["Shock", "Lightning Damage", "Ground Effects"],
    },
    {
        "name": "Chilled Ground",
        "category": "ground",
        "summary": "Area of ground that Chills entities standing in it for 6 seconds.",
        "mechanics": (
            "Chilled Ground applies Chill to any entity standing within it. "
            "The ground effect lasts 6 seconds by default. "
            "Created by certain cold skills and effects."
        ),
        "formula": "Duration: 6s.",
        "see_also": ["Chill", "Cold Damage", "Ground Effects"],
    },
    {
        "name": "Ignited Ground",
        "category": "ground",
        "summary": "Ground that repeatedly inflicts Flammability and Ignites at 50%.",
        "mechanics": (
            "Ignited Ground repeatedly inflicts Flammability on enemies standing in it. "
            "When Flammability reaches 50%, the enemy is Ignited. "
            "Used by fire skills and certain traps."
        ),
        "formula": "",
        "see_also": ["Ignite", "Fire Damage", "Flammability", "Ground Effects"],
    },
    {
        "name": "Consecrated Ground",
        "category": "ground",
        "summary": "Ground that regenerates 5% of maximum Life per second for those standing in it.",
        "mechanics": (
            "Consecrated Ground provides significant Life regeneration to those standing in it. "
            "It regenerates 5% of maximum Life per second. Often created by Templar/Holy skills."
        ),
        "formula": "+5% max Life regeneration per second.",
        "see_also": ["Life", "Ground Effects"],
    },
    {
        "name": "Desecrated Ground",
        "category": "ground",
        "summary": "Ground that deals Chaos Damage over time to those standing in it.",
        "mechanics": (
            "Desecrated Ground deals chaos DoT to any entity standing within it. "
            "It is hostile to the player and created by certain enemy skills and necromantic effects."
        ),
        "formula": "",
        "see_also": ["Chaos Damage", "Ground Effects"],
    },

    # ── Item Base Types ───────────────────────────────────────────────────────

    {
        "name": "Armour Base Tags",
        "category": "base_type",
        "summary": "Internal tags that identify which defence type(s) an armour base provides.",
        "mechanics": (
            "Every armour item base carries an internal tag used by the mod weight system to "
            "determine which mods can roll on it. The tag is derived from the base's stat "
            "requirements and sub-type: "
            "int_armour = Energy Shield (INT req, e.g. Sombre Gloves, Lacquered Helmet); "
            "str_armour = Armour only (STR req, e.g. Riveted Mitts, Plate Helmet); "
            "dex_armour = Evasion only (DEX req, e.g. Rawhide Boots, Jade Mask); "
            "str_int_armour = Armour + Energy Shield (STR+INT, e.g. Crusader Gauntlets); "
            "dex_int_armour = Evasion + Energy Shield (DEX+INT, e.g. Scholar Boots); "
            "str_dex_armour = Armour + Evasion (STR+DEX, e.g. Zealot Gauntlets); "
            "str_dex_int_armour = Armour + Evasion + Energy Shield (STR+DEX+INT, e.g. Vanguard Gloves). "
            "To look up bases of a specific type: poe2-lookup <slot> --type bases --tag int_armour. "
            "To look up mods for a specific base type: poe2-lookup <stat> --type mods --tag int_armour. "
            "A base's tags are visible in the Tags line of the base lookup output."
        ),
        "formula": (
            "int_armour → sub_type 'Energy Shield' | "
            "str_armour → 'Armour' | "
            "dex_armour → 'Evasion' | "
            "str_int_armour → 'Armour/Energy Shield' | "
            "dex_int_armour → 'Evasion/Energy Shield' | "
            "str_dex_armour → 'Armour/Evasion' | "
            "str_dex_int_armour → 'Armour/Evasion/Energy Shield'"
        ),
        "see_also": [
            "int_armour", "str_armour", "dex_armour",
            "str_int_armour", "dex_int_armour", "str_dex_armour", "str_dex_int_armour",
            "Armour", "Evasion", "Energy Shield", "Strength", "Dexterity", "Intelligence",
        ],
    },
    {
        "name": "int_armour",
        "category": "base_type",
        "summary": "Tag for Energy Shield armour bases (pure INT requirement).",
        "mechanics": (
            "Bases tagged int_armour are pure Energy Shield armour pieces. "
            "They require Intelligence to equip and provide Energy Shield as their defence stat. "
            "Examples: Sombre Gloves, Quilted Vest, Lacquered Helmet, Scholar Boots. "
            "Mods that target int_armour include: LocalEnergyShieldPercent (% increased ES, "
            "T1=Unassailable 92-100%), LocalIncreasedEnergyShieldAndMana, flat ES prefix. "
            "Unfaltering (101-110% ES) does NOT roll on int_armour — it is body_armour/shield only. "
            "To find all int_armour gloves: poe2-lookup gloves --type bases --tag int_armour. "
            "To find mods for int_armour: poe2-lookup 'energy shield' --type mods --tag int_armour."
        ),
        "formula": "sub_type = 'Energy Shield'. Requires INT. Defence: ES only.",
        "see_also": ["Armour Base Tags", "Energy Shield", "Intelligence", "str_int_armour", "dex_int_armour"],
    },
    {
        "name": "str_armour",
        "category": "base_type",
        "summary": "Tag for pure Armour bases (STR requirement).",
        "mechanics": (
            "Bases tagged str_armour are pure physical Armour pieces. "
            "They require Strength to equip and provide Armour as their defence. "
            "Examples: Riveted Mitts, Plate Helmet, Titan Greaves, Iron Gauntlets. "
            "To find all str_armour boots: poe2-lookup boots --type bases --tag str_armour."
        ),
        "formula": "sub_type = 'Armour'. Requires STR. Defence: Armour only.",
        "see_also": ["Armour Base Tags", "Armour", "Strength", "str_int_armour", "str_dex_armour"],
    },
    {
        "name": "dex_armour",
        "category": "base_type",
        "summary": "Tag for pure Evasion bases (DEX requirement).",
        "mechanics": (
            "Bases tagged dex_armour are pure Evasion pieces. "
            "They require Dexterity to equip and provide Evasion Rating as their defence. "
            "Examples: Rawhide Boots, Jade Mask, Wyrmscale Gauntlets. "
            "To find all dex_armour gloves: poe2-lookup gloves --type bases --tag dex_armour."
        ),
        "formula": "sub_type = 'Evasion'. Requires DEX. Defence: Evasion only.",
        "see_also": ["Armour Base Tags", "Evasion", "Dexterity", "dex_int_armour", "str_dex_armour"],
    },
    {
        "name": "str_int_armour",
        "category": "base_type",
        "summary": "Tag for Armour + Energy Shield bases (STR+INT requirement).",
        "mechanics": (
            "Bases tagged str_int_armour provide both Armour and Energy Shield. "
            "They require both Strength and Intelligence. "
            "Examples: Crusader Gauntlets, Chainmail, Sage's Robe. "
            "Mods like LocalArmourAndEnergyShield (% increased Armour and ES) roll here. "
            "To find all str_int_armour helmets: poe2-lookup helmet --type bases --tag str_int_armour."
        ),
        "formula": "sub_type = 'Armour/Energy Shield'. Requires STR+INT. Defence: Armour + ES.",
        "see_also": ["Armour Base Tags", "Armour", "Energy Shield", "str_armour", "int_armour"],
    },
    {
        "name": "dex_int_armour",
        "category": "base_type",
        "summary": "Tag for Evasion + Energy Shield bases (DEX+INT requirement).",
        "mechanics": (
            "Bases tagged dex_int_armour provide both Evasion and Energy Shield. "
            "They require Dexterity and Intelligence. "
            "Examples: Scholar Boots, Occultist's Vestment, Silken Hood. "
            "To find all dex_int_armour boots: poe2-lookup boots --type bases --tag dex_int_armour."
        ),
        "formula": "sub_type = 'Evasion/Energy Shield'. Requires DEX+INT. Defence: Evasion + ES.",
        "see_also": ["Armour Base Tags", "Evasion", "Energy Shield", "dex_armour", "int_armour"],
    },
    {
        "name": "str_dex_armour",
        "category": "base_type",
        "summary": "Tag for Armour + Evasion bases (STR+DEX requirement).",
        "mechanics": (
            "Bases tagged str_dex_armour provide both Armour and Evasion. "
            "They require Strength and Dexterity. "
            "Examples: Zealot Gauntlets, Ringmail, Scale Vest. "
            "To find all str_dex_armour gloves: poe2-lookup gloves --type bases --tag str_dex_armour."
        ),
        "formula": "sub_type = 'Armour/Evasion'. Requires STR+DEX. Defence: Armour + Evasion.",
        "see_also": ["Armour Base Tags", "Armour", "Evasion", "str_armour", "dex_armour"],
    },
    {
        "name": "str_dex_int_armour",
        "category": "base_type",
        "summary": "Tag for tri-defence bases (STR+DEX+INT requirement, all three defences).",
        "mechanics": (
            "Bases tagged str_dex_int_armour provide Armour, Evasion, AND Energy Shield. "
            "They require all three attributes. "
            "Examples: Vanguard Gloves, Glorious Plate, Royal Burgonet. "
            "The mod Unfaltering (101-110% increased Armour, Evasion and Energy Shield) rolls on "
            "str_dex_int_armour as the top tier. "
            "To find all tri-defence body armours: poe2-lookup 'body armour' --type bases --tag str_dex_int_armour."
        ),
        "formula": "sub_type = 'Armour/Evasion/Energy Shield'. Requires STR+DEX+INT. Defence: all three.",
        "see_also": ["Armour Base Tags", "Armour", "Evasion", "Energy Shield"],
    },

    # ── Item Modification System ───────────────────────────────────────────────

    {
        "name": "Desecrated Mod",
        "category": "item_mod",
        "summary": "An Unrevealed modifier added to an item via the Desecration mechanic; revealed at the Well of Souls.",
        "mechanics": (
            "Desecrating an item adds an Unrevealed Desecrated modifier. "
            "If the item's modifier slots are full, a random existing modifier is also removed to make room. "
            "Once desecrated, the modifier remains hidden until revealed at the Well of Souls (found in Abyss encounters). "
            "Items with a Desecrated Modifier cannot be Desecrated again. "
            "The primary way to Desecrate an item is by socketing an Abyss Jewel (Rib, Jawbone, Collarbone, etc.) "
            "into a Bone Socket on the item — the jewel is consumed and determines the mod pool. "
            "Desecrated mods are separate from explicit, implicit, fractured, and crafted mods. "
            "On the trade site they use the stat type prefix 'desecrated.' (e.g. desecrated.stat_XXXX). "
            "They appear in the item's mod list tagged as (desecrated). "
            "To search for items with desecrated mods, use stat_type='desecrated' in trade searches."
        ),
        "formula": "Desecrated mod value is determined by the Abyss Jewel's mod pool at time of socketing.",
        "see_also": ["Abyss Jewel", "Bone Socket", "Well of Souls", "Rune", "Corruption"],
    },
    {
        "name": "Abyss Jewel",
        "category": "item_mod",
        "summary": "A jewel socketed into a Bone Socket to Desecrate an item; consumed on use.",
        "mechanics": (
            "Abyss Jewels are obtained from Abyss encounters in maps. "
            "When socketed into a Bone Socket on an item, the Abyss Jewel is consumed and the item "
            "gains an Unrevealed Desecrated modifier drawn from the jewel's mod pool. "
            "The modifier must then be revealed at the Well of Souls. "
            "Bone type determines which item slots it can target: "
            "Ribs → armour, Jawbones → weapons/quivers, Collarbones → accessories (amulet/ring/belt), "
            "Craniums → helmets, Vertebrae → body armours. "
            "Abyss Jewels can also be placed in passive tree jewel sockets like normal jewels. "
            "Desecrated mod stats include life/mana on kill, added damage, resistances, "
            "and bonuses not available in the standard explicit mod pool. "
            "To find items with specific desecrated mods on trade, use stat_type='desecrated'."
        ),
        "formula": "",
        "see_also": ["Desecrated Mod", "Bone Socket", "Well of Souls", "Jewel"],
    },
    {
        "name": "Bone Socket",
        "category": "item_mod",
        "summary": "A special socket on items that accepts Abyss Jewels to Desecrate the item.",
        "mechanics": (
            "Bone Sockets are a socket type found on certain item bases in PoE2. "
            "Unlike Rune Sockets (which accept Runes for flat stat bonuses), Bone Sockets accept Abyss Jewels. "
            "When an Abyss Jewel is socketed, it is consumed and the item gains an Unrevealed Desecrated modifier. "
            "Once an item has a Desecrated Modifier it cannot be Desecrated again. "
            "Items with Bone Sockets are valuable crafting targets because desecrated mods "
            "add stats outside the normal explicit mod pool, effectively giving an extra affix. "
            "On the trade site, Bone Sockets use the same 'rune sockets' count filter as Rune Sockets."
        ),
        "formula": "",
        "see_also": ["Abyss Jewel", "Desecrated Mod", "Well of Souls", "Rune Socket"],
    },
    {
        "name": "Well of Souls",
        "category": "item_mod",
        "summary": "An Abyss mechanic station that reveals Unrevealed Desecrated modifiers on items.",
        "mechanics": (
            "After an item is Desecrated (via an Abyss Jewel socketed into a Bone Socket), "
            "it shows an 'Unrevealed Desecrated Modifier' in its mod list. "
            "The Well of Souls is an interactive object found within Abyss encounters in maps. "
            "Interacting with the Well of Souls reveals the hidden desecrated modifier, "
            "showing its actual stat and value. "
            "The Well of Souls cannot be used on items that already have a revealed Desecrated Modifier."
        ),
        "formula": "",
        "see_also": ["Desecrated Mod", "Abyss Jewel", "Bone Socket"],
    },
    {
        "name": "Fractured Mod",
        "category": "item_mod",
        "summary": "A permanently locked mod on a Fractured Item that cannot be changed by crafting.",
        "mechanics": (
            "Fractured mods are created by using a Fracturing Orb on an item. One random mod "
            "becomes 'fractured' — it is permanently locked and cannot be removed or changed by "
            "any crafting currency. The item gains the Fractured Item tag. "
            "Fractured items are valuable crafting bases because they guarantee one T1 mod, "
            "reducing the crafting goal to hitting the remaining affixes. "
            "On trade, use stat_type='fractured' to find items with a specific fractured mod. "
            "In item listings, fractured mods appear tagged as (fractured). "
            "Fractured items cannot be Mirrored."
        ),
        "formula": "",
        "see_also": ["Fracturing Orb", "Crafting", "Item Mod Tiers"],
    },
    {
        "name": "Crafted Mod",
        "category": "item_mod",
        "summary": "A mod added via the Crafting Bench that occupies a prefix or suffix slot.",
        "mechanics": (
            "Crafted mods are added to items via the Crafting Bench in your hideout. "
            "They behave like normal explicit mods and occupy a prefix or suffix slot. "
            "Only one crafted mod can be on an item at a time. "
            "Crafted mods are removed when you use certain crafting currencies (e.g. Scour, Chaos). "
            "They appear on the item tagged as (crafted). "
            "Common uses: fill the last open prefix/suffix with a useful defensive mod "
            "while you continue crafting the remaining slots."
        ),
        "formula": "",
        "see_also": ["Crafting", "Prefix", "Suffix", "Affix"],
    },
    {
        "name": "Jewel Socket",
        "category": "passive_tree",
        "summary": "A passive tree node that holds a Jewel, applying its mods to the build.",
        "mechanics": (
            "Jewel Sockets are special nodes on the passive tree that accept Jewels. "
            "Allocating a Jewel Socket node (costs 1 passive point) enables you to socket a jewel. "
            "The jewel's mods then apply to the build as if they were passive nodes. "
            "Each jewel socket has a node_id in PoB — use get_tree_jewels() to see which jewels "
            "are currently socketed and at which node_ids. "
            "Use set_tree_jewel(node_id, item_text) to simulate a different jewel in that slot. "
            "Jewel sockets near keystones or large cluster areas amplify their value via "
            "radius mods that affect nearby passive nodes."
        ),
        "formula": "",
        "see_also": ["Jewel", "Passive Tree", "Cluster Jewel", "Abyss Jewel"],
    },

    # ── Item Rarity ────────────────────────────────────────────────────────────

    {
        "name": "Rarity",
        "category": "mechanic",
        "summary": "Items have one of four rarities: Normal, Magic, Rare, and Unique.",
        "mechanics": (
            "Normal items have no affixes. "
            "Magic items have 1–2 affixes (1 prefix and/or 1 suffix). "
            "Rare items have 3–6 affixes (up to 3 prefixes and 3 suffixes). "
            "Unique items have fixed modifiers that cannot be rerolled (except their numeric values with Divine Orb). "
            "Currency to change rarity: Orb of Transmutation (Normal→Magic), "
            "Regal Orb (Magic→Rare), Chaos Orb (reroll Rare), "
            "Orb of Alchemy (Normal→Rare). "
            "Item rarity affects which mods can roll, crafting methods available, "
            "and trade search filters (rarity: magic/rare/unique)."
        ),
        "formula": "Magic: ≤2 affixes (1P + 1S). Rare: ≤6 affixes (3P + 3S).",
        "see_also": ["Normal", "Magic", "Rare", "Unique", "Affix", "Prefix", "Suffix"],
    },
    {
        "name": "Normal",
        "category": "mechanic",
        "summary": "Base item rarity — no affixes, white item colour in-game.",
        "mechanics": (
            "Normal (white) items have no explicit modifiers. "
            "They are the starting point for crafting: "
            "Orb of Transmutation upgrades Normal→Magic (adds 1–2 affixes), "
            "Orb of Alchemy upgrades Normal→Rare (adds 3–6 affixes). "
            "Base item stats (armour, ES, evasion, damage) are at fixed values on Normal items. "
            "An item level (ilvl) of 80+ on a Normal base is required for T1 mods when crafting."
        ),
        "formula": "0 explicit affixes.",
        "see_also": ["Rarity", "Magic", "Rare", "Orb of Transmutation"],
    },
    {
        "name": "Magic",
        "category": "mechanic",
        "summary": "Blue item rarity — 1–2 affixes (1 prefix + 1 suffix maximum).",
        "mechanics": (
            "Magic (blue) items have 1–2 explicit modifiers: at most 1 prefix and 1 suffix. "
            "Magic items are the primary target for alteration-spam crafting: "
            "use Orb of Alteration to reroll until target mod(s) appear, "
            "then Regal Orb to upgrade to Rare and add a third mod. "
            "Orb of Augmentation adds a missing affix (prefix or suffix) to a Magic item with only 1 mod. "
            "Essences can be applied to Magic items (guarantees one mod, fills the other slot randomly). "
            "The trade rarity filter for Magic is rarity=magic."
        ),
        "formula": "1–2 explicit affixes: ≤1 prefix + ≤1 suffix.",
        "see_also": ["Rarity", "Rare", "Orb of Alteration", "Orb of Augmentation", "Regal Orb", "Affix"],
    },
    {
        "name": "Rare",
        "category": "mechanic",
        "summary": "Yellow item rarity — 3–6 affixes (up to 3 prefixes + 3 suffixes).",
        "mechanics": (
            "Rare (yellow) items have 3–6 explicit modifiers: up to 3 prefixes and 3 suffixes. "
            "The most powerful endgame crafting target. "
            "Key crafting methods for Rare items: "
            "Chaos Orb rerolls all affixes randomly; "
            "Alteration-spam → Regal is cheaper for targeting 1–2 specific mods; "
            "Essence guarantees one mod on a Rare item (Chaos-equivalent); "
            "Exalted Orb adds a new affix to an item with fewer than 6 (open prefix or suffix required); "
            "Annulment Orb removes a random affix; "
            "Divine Orb re-rolls the numeric values of existing mods. "
            "Rare items on the trade site show as rarity=rare."
        ),
        "formula": "3–6 explicit affixes: ≤3 prefixes + ≤3 suffixes.",
        "see_also": ["Rarity", "Magic", "Affix", "Prefix", "Suffix", "Chaos Orb", "Exalted Orb", "Divine Orb"],
    },
    {
        "name": "Unique",
        "category": "mechanic",
        "summary": "Orange item rarity — fixed predefined modifiers, not craftable with standard orbs.",
        "mechanics": (
            "Unique (orange) items have fixed modifiers defined by the game — they cannot be rerolled "
            "with Chaos Orb or Alteration. "
            "Divine Orb re-rolls the NUMERIC VALUES of Unique item mods within their allowed ranges. "
            "Fractured Unique items are not a thing (fracts only apply to Rares). "
            "Unique items are found by name on the trade site (search by name, not by mods). "
            "Key uniques for ES builds: Voll's Devotion, Kaom's Heart. "
            "Some uniques have variants or alternative art versions. "
            "Unique items identified on the ground have a fixed name shown in orange."
        ),
        "formula": "Fixed mods. Divine Orb re-rolls values within allowed ranges.",
        "see_also": ["Rarity", "Divine Orb", "Unique Items"],
    },

    # ── Flask ──────────────────────────────────────────────────────────────────

    {
        "name": "Flask",
        "category": "mechanic",
        "summary": "Consumable items that recover life or mana, activated manually, fuelled by charges gained from killing monsters.",
        "mechanics": (
            "Each player can equip one Life Flask and one Mana Flask. "
            "Flasks have a charge pool; using the flask expends charges and begins the recovery. "
            "Charges are gained by killing monsters (amount scales with pack size) or from checkpoints/wells. "
            "Flask mods affect charge gain rate, recovery speed, added effects (movement speed, resistance), "
            "and conditions (on critical hit, on stun, etc.). "
            "Charms are separate slot items that auto-trigger on specific conditions (stun, freeze, etc.). "
            "Flask quality increases recovery amount. "
            "Key flask suffixes: of the Tortoise (reduced charges used), of the Ibex (increased recovery), "
            "of the Warding (curse removal), of Grounding (shock removal). "
            "Use poe2-lookup mods --category Flask to see all flask mod options."
        ),
        "formula": "Charge recovery: charges gained per kill × pack size bonus.",
        "see_also": ["Life Flask", "Mana Flask", "Charm", "Charges", "Flask Mods"],
    },

    # ── Desecrate ─────────────────────────────────────────────────────────────

    {
        "name": "Desecrate",
        "category": "item_mod",
        "summary": "The action of socketing an Abyss Jewel into a Bone Socket, adding an Unrevealed Desecrated modifier. Also called Desecrating an item.",
        "mechanics": (
            "To desecrate an item: socket an Abyss Jewel (Rib, Jawbone, Collarbone, Cranium, Vertebra) "
            "into a matching Bone Socket. The jewel is consumed. "
            "The item gains an Unrevealed Desecrated modifier — the mod remains hidden until revealed "
            "at the Well of Souls (found in Abyss encounters in maps). "
            "If all modifier slots are full, a random existing modifier is removed to make room. "
            "An item can only be desecrated once. "
            "Desecrated mods use the stat type 'desecrated.' on the trade site. "
            "Searches: poe2-lookup 'desecrated' --type mods --category Desecrated"
        ),
        "formula": "One Unrevealed Desecrated mod per item. Replaces a random mod if item is full.",
        "see_also": ["Desecrated Mod", "Abyss Jewel", "Bone Socket", "Well of Souls", "Desecrated Ground"],
    },

    # ── League / Endgame Encounter Mechanics ──────────────────────────────────
    # Stubs — filled in from poe2wiki.net via `poe2-lookup concept-seed`

    {
        "name": "Breach",
        "category": "mechanic",
        "summary": "A map encounter where tears in reality summon Hiveborn monsters. Drops Breach Splinters and Wombgifts.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Genesis Tree", "Wombgift", "Breachstone", "Hive Fortress", "Abyss Jewel"],
        "source": "manual",
    },
    {
        "name": "Genesis Tree",
        "category": "mechanic",
        "summary": "A crafting station in the Monastery of the Keepers. Uses Hiveblood and Wombgifts from Breach encounters to birth items.",
        "mechanics": (
            "Hiveblood is gained automatically by killing Breach monsters. "
            "Wombgifts drop from Breach encounters or Hive Fortress chests. "
            "Each womb on the tree has passive skills that modify the birth outcome. "
            "Revelatory Wombgift → Breachstones. Lavish Wombgift → Breach Splinters or items. "
            "Signet Wombgift → Breach Rings (requires specific passive: Otherworldly Clutch)."
        ),
        "formula": "",
        "see_also": ["Breach", "Wombgift", "Hiveblood", "Breach Ring", "Breachstone"],
        "source": "manual",
    },
    {
        "name": "Hive Fortress",
        "category": "mechanic",
        "summary": "A large Breach zone in the endgame Atlas containing Breach Hive encounters and a Breach Fortress near the center.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Breach", "Genesis Tree", "Breachstone"],
        "source": "manual",
    },
    {
        "name": "Breachstone",
        "category": "mechanic",
        "summary": "A map item created from 300 Breach Splinters. Opens a Breach Domain and rewards Breach-specific loot.",
        "mechanics": "",
        "formula": "300 Breach Splinters → 1 Revelatory Wombgift → Breachstone via Genesis Tree.",
        "see_also": ["Breach Splinter", "Breach", "Genesis Tree"],
        "source": "manual",
    },
    {
        "name": "Abyss",
        "category": "mechanic",
        "summary": "A map encounter where Abyssal fissures spawn monsters. Drops Abyss Jewels and leads to the Well of Souls for revealing Desecrated mods.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Well of Souls", "Abyss Jewel", "Desecrated Mod", "Bone Socket"],
        "source": "manual",
    },
    {
        "name": "Delirium",
        "category": "mechanic",
        "summary": "A map encounter triggered by a Delirium mirror. Monsters are empowered; rewards scale with distance from the mirror. Drops Delirium Orbs, Simulacrum Splinters, and Cluster Jewels.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Simulacrum", "Cluster Jewel", "Delirium Orb"],
        "source": "manual",
    },
    {
        "name": "Simulacrum",
        "category": "mechanic",
        "summary": "A Delirium endgame map created from 300 Simulacrum Splinters. Contains 30 waves of Delirium enemies with powerful rewards.",
        "mechanics": "",
        "formula": "300 Simulacrum Splinters → 1 Simulacrum map.",
        "see_also": ["Delirium", "Simulacrum Splinter", "Cluster Jewel"],
        "source": "manual",
    },
    {
        "name": "Expedition",
        "category": "mechanic",
        "summary": "A map encounter where explosives are placed over Kalguuran burial sites to unearth artifacts and monsters. Four NPC traders offer different services including Rog crafting.",
        "mechanics": (
            "Four Expedition NPCs: Rog (crafting — adds/removes mods), "
            "Tujen (haggling for currency/items), Gwennen (gambling for unique items), "
            "Dannig (logbooks, rerolls). "
            "Rog crafting can add specific affixes or remove specific affixes for a cost — "
            "most powerful for targeted crafting. "
            "Expedition Logbooks open Expedition encounters in endgame zones."
        ),
        "formula": "",
        "see_also": ["Rog", "Expedition Logbook", "Tujen", "Gwennen", "Dannig"],
        "source": "manual",
    },
    {
        "name": "Ritual",
        "category": "mechanic",
        "summary": "A map encounter with sacrificial altars. Killing monsters around altars fills a tribute pool which can be spent on specific items from the Ritual trader.",
        "mechanics": (
            "Zones have 3–4 Ritual altars; completing each contributes tribute. "
            "The Ritual trader offers a rotating selection of items purchasable with tribute. "
            "Items can be deferred (costs more later) or rerolled (random new selection). "
            "Ritual is a key source of Omens."
        ),
        "formula": "",
        "see_also": ["Omen", "Tribute", "Ritual Altar"],
        "source": "manual",
    },
    {
        "name": "Ultimatum",
        "category": "mechanic",
        "summary": "The Trials of Chaos — an Ascension Trial in Act 3. Also appears as an endgame encounter with escalating challenges for increasing rewards.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Inscribed Ultimatum", "Ascendancy", "Trials of Chaos"],
        "source": "manual",
    },
    {
        "name": "Cluster Jewel",
        "category": "mechanic",
        "summary": "Special jewels from Delirium that expand the Passive Skill Tree with new sockets and allocatable notables. Socketed in large/medium/small cluster sockets at the tree edge.",
        "mechanics": (
            "Three sizes: Large (8–12 passives, 2 large jewel sockets), "
            "Medium (4–6 passives, 1 large socket), Small (2–4 passives). "
            "Enchanted with specific notable names; rolling the jewel changes which notables appear. "
            "Key crafting: Alt-spam for 2 desired notables on a Small/Medium cluster."
        ),
        "formula": "",
        "see_also": ["Delirium", "Passive Tree", "Notable", "Jewel Socket"],
        "source": "manual",
    },
    {
        "name": "Atlas passive tree",
        "category": "mechanic",
        "summary": "Passive skills that affect the Atlas endgame — improves item drops, encounter frequency, and adds new rewards. Points gained from completing Precursor Fortress maps and defeating bosses.",
        "mechanics": (
            "Main tree: points from Precursor Fortress map bosses. "
            "Side trees: points from completing specific encounter mechanics (Breach, Abyss, etc.). "
            "Pinnacle boss kills grant 6 side-tree points each. "
            "No respec — allocation is permanent (per character). "
            "Keystone passives offer a choice of two bonuses, freely changeable. "
            "Can fully allocate every passive with enough completions."
        ),
        "formula": "",
        "see_also": ["Atlas", "Precursor Fortress", "Breach", "Abyss", "Delirium", "Ritual"],
        "source": "manual",
    },
    {
        "name": "Atlas",
        "category": "mechanic",
        "summary": "The endgame map system. A network of maps organized in Precursor Fortresses, accessible after completing the campaign. Completing maps progresses the Atlas and unlocks encounters.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Waystone", "Atlas passive tree", "Precursor Fortress", "Breach", "Abyss"],
        "source": "manual",
    },
    {
        "name": "Precursor Fortress",
        "category": "mechanic",
        "summary": "The endgame hub structure containing maps. Completing maps in a Precursor Fortress earns Atlas passive points. Activating a section (after killing the Arbiter 5 times) auto-completes contained maps.",
        "mechanics": "",
        "formula": "",
        "see_also": ["Atlas", "Atlas passive tree", "Arbiter of Divinity", "Waystone"],
        "source": "manual",
    },
]

_NAME_INDEX: dict[str, dict] | None = None


def _build_index() -> dict[str, dict]:
    return {c["name"].lower(): c for c in CONCEPTS}


def search_concepts(keyword: str = "", category: str = "", limit: int = 20) -> list[dict]:
    """
    Search concept definitions by keyword and/or category.

    Also searches exchange items (catalysts, liquid emotions, abyss bones, etc.)
    when category is blank or "exchange_item".

    Args:
        keyword:  Text to search in name, summary, and mechanics fields.
        category: Filter by category (e.g. "ailment", "keystone", "charge").
        limit:    Max results returned.

    Returns:
        List of matching concept dicts.
    """
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = _build_index()

    kw = keyword.lower().strip()
    cat = category.lower().strip()

    results: list[dict] = []

    # Search core CONCEPTS unless caller asked only for exchange_item
    if cat != "exchange_item":
        for c in CONCEPTS:
            if cat and c["category"] != cat:
                continue
            if kw:
                haystack = (
                    c["name"] + " " + c["summary"] + " " + c["mechanics"] + " "
                    + " ".join(c["see_also"])
                ).lower()
                if kw not in haystack:
                    continue
            results.append(c)
            if len(results) >= limit:
                return results

    # Also search exchange items when no category filter or "exchange_item"
    if not cat or cat == "exchange_item":
        from poe2_crafting_mcp.data.general_items import search_exchange_items
        remaining = limit - len(results)
        if remaining > 0:
            for e in search_exchange_items(keyword=keyword, limit=remaining):
                results.append({
                    "name": e["name"],
                    "category": "exchange_item",
                    "summary": e.get("description", ""),
                    "mechanics": f"item_type: {e['item_type']}  slug: {e['slug']}",
                    "formula": "",
                    "see_also": [],
                })

    return results


def get_concept(name: str) -> dict | None:
    """Fetch a concept by exact name (case-insensitive)."""
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = _build_index()
    return _NAME_INDEX.get(name.lower())


ALL_CATEGORIES: list[str] = [
    "damage_type", "ailment", "attribute", "defence", "offence",
    "charge", "resource", "buff", "debuff", "mechanic", "keyword",
    "keystone", "projectile", "ground", "base_type", "item_mod",
    "passive_tree", "exchange_item",
]
