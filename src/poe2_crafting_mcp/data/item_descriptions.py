"""
Item descriptions seed data — currencies, bases, and gems with crafting context.

Seeded into the item_descriptions SQLite table during ETL.
Updatable at runtime via poe2-lookup item-desc-add / item-desc-refresh.

Fields per entry:
    name           TEXT PRIMARY KEY
    category       "base" | "currency" | "gem" | "unique" | "mechanic_item"
    description    What it is / what it does
    crafting_notes When and how to use it in crafting
    drop_notes     Where it comes from
    see_also       List of related item/concept names
    source         "manual" | "poe2wiki" | "poe2db"
    league_version None = all leagues; string = league-specific
"""

from __future__ import annotations

ITEM_DESCRIPTIONS: list[dict] = [

    # ── Orbs ─────────────────────────────────────────────────────────────────

    {
        "name": "Orb of Transmutation",
        "category": "currency",
        "description": "Upgrades a Normal item to Magic rarity.",
        "crafting_notes": "First step in alteration-spam crafting. Apply to a Normal base, then use Alterations to reroll until you hit your target mod(s).",
        "drop_notes": "Common drop from monsters and chests.",
        "see_also": ["Orb of Alteration", "Orb of Augmentation"],
        "source": "manual",
    },
    {
        "name": "Orb of Alteration",
        "category": "currency",
        "description": "Rerolls the mods on a Magic item.",
        "crafting_notes": "Core currency for alteration-spam crafting. Keep rerolling until you hit your 1-2 target mods. Use Orb of Augmentation if result has only 1 mod and you need 2. Regal Orb to upgrade to Rare when satisfied.",
        "drop_notes": "Common drop; also obtained by vendoring rare items.",
        "see_also": ["Orb of Augmentation", "Regal Orb", "Orb of Transmutation"],
        "source": "manual",
    },
    {
        "name": "Orb of Augmentation",
        "category": "currency",
        "description": "Adds a random mod to a Magic item that has only one mod.",
        "crafting_notes": "Use after an Alteration results in a single good prefix/suffix. The second mod is random — if it clashes, re-alt and try again.",
        "drop_notes": "Common drop.",
        "see_also": ["Orb of Alteration", "Regal Orb"],
        "source": "manual",
    },
    {
        "name": "Regal Orb",
        "category": "currency",
        "description": "Upgrades a Magic item to Rare, adding one random mod.",
        "crafting_notes": "Final step in alt-spam: apply when Magic item has exactly the mods you want. The added Rare mod is random. Can then Exalt for more mods or bench-craft the remaining affix slot.",
        "drop_notes": "Uncommon drop; tradeable.",
        "see_also": ["Orb of Alteration", "Orb of Exalted", "Bench Craft"],
        "source": "manual",
    },
    {
        "name": "Chaos Orb",
        "category": "currency",
        "description": "Rerolls all mods on a Rare item.",
        "crafting_notes": "Use on Rare items to gamble for better mods. Unlike Alterations, you cannot chaos-spam efficiently — use Essences or Alterations for targeted crafting. Chaos is the baseline trade currency.",
        "drop_notes": "Common drop. Baseline trade currency (1 chaos ≈ 1 unit of value).",
        "see_also": ["Orb of Exalted", "Orb of Annulment", "Divine Orb"],
        "source": "manual",
    },
    {
        "name": "Orb of Exalted",
        "category": "currency",
        "description": "Adds one random mod to a Rare item that is not full.",
        "crafting_notes": "Use when a Rare item has open affix slots. Pairs well with Annulment: if the added mod is bad, annul it and try again (expensive). Best used to fill the last open slot when other mods are perfect.",
        "drop_notes": "Uncommon drop; significant trade value.",
        "see_also": ["Orb of Annulment", "Chaos Orb", "Bench Craft"],
        "source": "manual",
    },
    {
        "name": "Orb of Annulment",
        "category": "currency",
        "description": "Removes one random mod from a Magic or Rare item.",
        "crafting_notes": "Risky — removes a random mod. Use to remove a bad mod added by Exalt or Regal. Pair with Exalt: Exalt → bad result → Annul → retry. Also used in meta-crafting with bench mods to block and annul predictably.",
        "drop_notes": "Rare drop; high trade value.",
        "see_also": ["Orb of Exalted", "Bench Craft"],
        "source": "manual",
    },
    {
        "name": "Divine Orb",
        "category": "currency",
        "description": "Rerolls the numeric values of all mods on an item within their existing ranges.",
        "crafting_notes": "Use to push low-rolled mods to higher values on an otherwise perfect item. Does NOT change which mods are present — only the numbers. Best used on high-value items where the tier is right but the roll is low.",
        "drop_notes": "Rare drop. Primary high-value trade currency (1 divine ≈ 40–80 chaos depending on league).",
        "see_also": ["Chaos Orb", "Fracture Orb"],
        "source": "manual",
    },
    {
        "name": "Vaal Orb",
        "category": "currency",
        "description": "Corrupts an item, applying a random corruption effect and making it unmodifiable.",
        "crafting_notes": "IRREVERSIBLE. Possible outcomes: add an implicit, change sockets, become a mirrored copy (rare), or no effect. Use only when the item is already excellent and you want to gamble for a powerful implicit. Cannot be Blessed/Crafted/Exalted after corruption.",
        "drop_notes": "Drops in Vaal side areas.",
        "see_also": ["Corruption", "Corrupted Implicit"],
        "source": "manual",
    },
    {
        "name": "Fracture Orb",
        "category": "currency",
        "description": "Fractures one mod on a Magic or Rare item, locking it permanently.",
        "crafting_notes": "Fracture a T1 mod you want to keep, then reroll the rest freely with Chaos/Alterations without losing that mod. Fractured bases are highly tradeable if the locked mod is desirable (e.g. T1 flat ES on gloves).",
        "drop_notes": "Rare drop; high trade value.",
        "see_also": ["Chaos Orb", "Orb of Alteration", "Fractured Item"],
        "source": "manual",
    },
    {
        "name": "Blessed Orb",
        "category": "currency",
        "description": "Rerolls the numeric values of implicit mods on an item.",
        "crafting_notes": "Used specifically for implicits, not explicit mods (use Divine for those). Target items where the implicit has a wide range and a high roll matters (e.g. rings with +% resistances as implicits).",
        "drop_notes": "Uncommon drop.",
        "see_also": ["Divine Orb", "Vaal Orb"],
        "source": "manual",
    },

    # ── Essences ──────────────────────────────────────────────────────────────

    {
        "name": "Essence",
        "category": "mechanic_item",
        "description": "Guarantees a specific mod when applied to a Normal item, then rerolls remaining mods randomly.",
        "crafting_notes": "Most reliable single-mod targeting method. Use on a good base: the Essence mod is locked, remaining affixes are random. If the random affixes are bad, Chaos reroll and repeat. More expensive per attempt than Alterations but more consistent for high-tier target mods.",
        "drop_notes": "Drops from Essence encounters (imprisoned monsters). Higher-tier essences from higher-tier encounters.",
        "see_also": ["Chaos Orb", "Regal Orb", "Wailing Essence", "Screaming Essence", "Shrieking Essence", "Deafening Essence"],
        "source": "manual",
    },
    {
        "name": "Deafening Essence of Greed",
        "category": "currency",
        "description": "Upgrades a Normal item to Rare, guaranteeing a T1 maximum Life mod.",
        "crafting_notes": "Best essence for life-stacking builds. Guarantees T1 life (~90+ max life) on the item. Remaining mods random — keep rerolling with Chaos if other mods are bad. Target high-ilvl bases to ensure T1 rolls.",
        "drop_notes": "Deafening tier essences from high-tier Essence encounters.",
        "see_also": ["Essence", "Maximum Life", "Chaos Orb"],
        "source": "manual",
    },
    {
        "name": "Deafening Essence of Loathing",
        "category": "currency",
        "description": "Upgrades a Normal item to Rare, guaranteeing a T1 Mana mod.",
        "crafting_notes": "For mana-reservation or mana-focused builds. The T1 mana roll is locked; other mods are random.",
        "drop_notes": "Deafening tier essences from high-tier encounters.",
        "see_also": ["Essence", "Maximum Mana"],
        "source": "manual",
    },

    # ── Equipment Bases — Gloves ───────────────────────────────────────────────

    {
        "name": "Gold Gloves",
        "category": "base",
        "description": "High-end Intelligence Armour gloves with strong Energy Shield base.",
        "crafting_notes": "Best-in-slot ES gloves base. Target ilvl 80+ for T1 flat ES (91+ ES). Key mods to target: flat ES (T1 = 91–110), +% ES, maximum life, resistances, attack speed. Tags: int_armour, gloves — check mods with --tag int_armour.",
        "drop_notes": "Endgame drop, ilvl 80+ zones and maps.",
        "see_also": ["Energy Shield", "Orb of Alteration", "Essence"],
        "source": "manual",
    },
    {
        "name": "Titan Gauntlets",
        "category": "base",
        "description": "High-end Strength Armour gloves with strong Armour base.",
        "crafting_notes": "Best-in-slot Armour gloves. Target ilvl 80+ for T1 flat armour. Tags: str_armour, gloves. Key mods: armour, life, resistances, attack speed.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Armour", "Maximum Life"],
        "source": "manual",
    },
    {
        "name": "Slink Gloves",
        "category": "base",
        "description": "High-end Dexterity/Intelligence hybrid gloves with Evasion and Energy Shield.",
        "crafting_notes": "Best hybrid Evasion/ES gloves. Tags: dex_int_armour, gloves. Good for hybrid defence builds (Grace + Discipline). Key mods: flat ES, evasion, life, res, attack speed.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Evasion", "Energy Shield"],
        "source": "manual",
    },

    # ── Equipment Bases — Boots ───────────────────────────────────────────────

    {
        "name": "Sorcerer Boots",
        "category": "base",
        "description": "High-end Intelligence Armour boots with strong Energy Shield base.",
        "crafting_notes": "Best-in-slot ES boots. Target ilvl 75+ for T1 movement speed (35%). Key mods: movement speed (suffix, highest priority), flat ES, maximum life, resistances. Movement speed T1 = 35%, T2 = 30%.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Energy Shield", "Movement Speed"],
        "source": "manual",
    },
    {
        "name": "Dragonscale Boots",
        "category": "base",
        "description": "High-end hybrid Armour/Evasion boots.",
        "crafting_notes": "Best hybrid AR/EV boots. Tags: str_dex_armour, boots. Key mods: movement speed, life, resistances.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Armour", "Evasion", "Movement Speed"],
        "source": "manual",
    },

    # ── Equipment Bases — Helmets ─────────────────────────────────────────────

    {
        "name": "Mind Cage",
        "category": "base",
        "description": "High-end Intelligence Armour helmet with strong Energy Shield base.",
        "crafting_notes": "Best-in-slot ES helmet. Target ilvl 80+ for T1 flat ES. Tags: int_armour, helmet. Key mods: flat ES, +% ES, life, resistances, gem level bonuses.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Energy Shield"],
        "source": "manual",
    },
    {
        "name": "Titan Helmet",
        "category": "base",
        "description": "High-end Strength Armour helmet.",
        "crafting_notes": "Best-in-slot Armour helmet. Tags: str_armour, helmet. Key mods: armour, life, resistances.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Armour"],
        "source": "manual",
    },

    # ── Equipment Bases — Body Armour ──────────────────────────────────────────

    {
        "name": "Vaal Regalia",
        "category": "base",
        "description": "High-end Intelligence Armour body armour with the highest ES base in the game.",
        "crafting_notes": "Best-in-slot ES body armour. Target ilvl 86 for max base ES (~600+ ES). Tags: int_armour, body_armour. Key mods: flat ES, +% ES, life, resistances, socket count. Extremely expensive to craft well — consider buying fractured T1 ES base.",
        "drop_notes": "Rare endgame drop, ilvl 86 from endgame maps.",
        "see_also": ["Energy Shield", "Fracture Orb"],
        "source": "manual",
    },
    {
        "name": "Astral Plate",
        "category": "base",
        "description": "High-end Strength Armour body armour with very high Armour base.",
        "crafting_notes": "Best Armour body armour. Implicit: +% to all Elemental Resistances — very strong. Tags: str_armour, body_armour. Key mods: life, resistances, armour.",
        "drop_notes": "Rare endgame drop.",
        "see_also": ["Armour", "Resistances"],
        "source": "manual",
    },
    {
        "name": "Zodiac Leather",
        "category": "base",
        "description": "High-end Dexterity Evasion body armour.",
        "crafting_notes": "Best pure evasion body armour. Tags: dex_armour, body_armour. Key mods: evasion, life, resistances, Elusive chance.",
        "drop_notes": "Rare endgame drop.",
        "see_also": ["Evasion"],
        "source": "manual",
    },

    # ── Equipment Bases — Rings ────────────────────────────────────────────────

    {
        "name": "Opal Ring",
        "category": "base",
        "description": "Ring with implicit +% elemental damage. Best base for damage-focused builds.",
        "crafting_notes": "Best ring base for damage builds — the implicit boosts all elemental spell and attack damage. Key mods: flat ES, life, resistances, added elemental damage. Tags: ring.",
        "drop_notes": "Rare endgame drop.",
        "see_also": ["Two-Stone Ring", "Amethyst Ring"],
        "source": "manual",
    },
    {
        "name": "Two-Stone Ring",
        "category": "base",
        "description": "Ring with implicit +% to two elemental resistances (fire+cold, fire+lightning, or cold+lightning).",
        "crafting_notes": "Best defensive ring base. The dual-res implicit frees up 2 suffix slots normally needed for res mods. Choose variant based on which resistances your build is short on. Key mods: life, flat ES, remaining resistance.",
        "drop_notes": "Common drop.",
        "see_also": ["Opal Ring", "Resistances"],
        "source": "manual",
    },
    {
        "name": "Amethyst Ring",
        "category": "base",
        "description": "Ring with implicit +% chaos resistance.",
        "crafting_notes": "Choose when chaos resistance is a critical gap. The implicit can cap chaos res without using a suffix slot. Key mods: life, ES, resistances.",
        "drop_notes": "Uncommon drop.",
        "see_also": ["Two-Stone Ring", "Chaos Resistance"],
        "source": "manual",
    },

    # ── Equipment Bases — Amulets ──────────────────────────────────────────────

    {
        "name": "Onyx Amulet",
        "category": "base",
        "description": "Amulet with implicit +N to all Attributes (Strength, Dexterity, Intelligence).",
        "crafting_notes": "Best general amulet base — implicit provides all three attributes, solving stat requirements. Key mods: flat ES, life, resistances, damage multiplier, gem level bonuses. Tags: amulet.",
        "drop_notes": "Common drop.",
        "see_also": ["Jade Amulet", "Attributes", "Strength", "Dexterity", "Intelligence"],
        "source": "manual",
    },
    {
        "name": "Jade Amulet",
        "category": "base",
        "description": "Amulet with implicit +N to Dexterity.",
        "crafting_notes": "Choose when Dexterity is your stat bottleneck (e.g. Ranger builds). Key mods: life, ES, resistances, evasion.",
        "drop_notes": "Common drop.",
        "see_also": ["Onyx Amulet", "Dexterity"],
        "source": "manual",
    },

    # ── Equipment Bases — Belts ────────────────────────────────────────────────

    {
        "name": "Stygian Vise",
        "category": "base",
        "description": "Belt with an Abyss socket for an Abyss Jewel. Best belt base.",
        "crafting_notes": "Best-in-slot belt due to the Abyss Jewel socket — adds an extra item's worth of mods. Insert a Ghastly Eye Jewel (life + damage) or Hypnotic Eye (ES + damage) depending on build. Key belt mods: life, ES, resistances, attributes.",
        "drop_notes": "Endgame drop; Abyss encounters.",
        "see_also": ["Heavy Belt", "Abyss Jewel"],
        "source": "manual",
    },
    {
        "name": "Heavy Belt",
        "category": "base",
        "description": "Belt with implicit +N to Strength.",
        "crafting_notes": "Best Strength-stacking belt base. The implicit adds Strength which also provides bonus life (1 Strength = 0.5 life). Key mods: life, resistances, strength.",
        "drop_notes": "Common drop.",
        "see_also": ["Stygian Vise", "Strength"],
        "source": "manual",
    },

    # ── Equipment Bases — Weapons ──────────────────────────────────────────────

    {
        "name": "Siege Axe",
        "category": "base",
        "description": "High-end two-handed Strength Axe with high physical damage range.",
        "crafting_notes": "Best-in-slot two-handed axe base for physical melee. Target ilvl 85+ for top physical damage tiers. Key mods: flat physical damage, +% physical damage, attack speed, critical strike chance/multiplier. Tags: str_weapon, axe, two_hand.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Physical Damage", "Attack Speed"],
        "source": "manual",
    },
    {
        "name": "Imperial Claw",
        "category": "base",
        "description": "High-end Dexterity Claw with fast attack speed.",
        "crafting_notes": "Best Dexterity Claw. High implicit life gained on hit. Tags: dex_weapon, claw. Key mods: flat physical damage, attack speed, critical chance/multiplier, added elemental damage.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Physical Damage", "Life Gain on Hit"],
        "source": "manual",
    },
    {
        "name": "Driftwood Wand",
        "category": "base",
        "description": "Low-level wand base — not for endgame crafting.",
        "crafting_notes": "Starter base only. Replace as soon as possible with higher-ilvl wand bases.",
        "drop_notes": "Common early drop.",
        "see_also": ["Prophecy Wand", "Imbued Wand"],
        "source": "manual",
    },
    {
        "name": "Imbued Wand",
        "category": "base",
        "description": "High-end Intelligence Wand with high spell damage implicit.",
        "crafting_notes": "Best-in-slot wand for caster builds. Implicit provides +% spell damage. Tags: int_weapon, wand. Key mods: +% spell damage, flat/+% added spell damage by type, cast speed, critical strike chance/multiplier, gem levels.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Spell Damage", "Cast Speed", "Critical Strike"],
        "source": "manual",
    },
    {
        "name": "Convoking Wand",
        "category": "base",
        "description": "High-end Intelligence Wand with +1 to level of all Summoning Skill Gems implicit.",
        "crafting_notes": "Best wand for minion builds — implicit gives +1 gem level to all minion skills. Key mods: +1 to minion skills, minion damage/life/speed, +% spell damage. Target ilvl 80+.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Minion", "Imbued Wand"],
        "source": "manual",
    },

    # ── Equipment Bases — Shields / Offhand ────────────────────────────────────

    {
        "name": "Titanium Spirit Shield",
        "category": "base",
        "description": "High-end Intelligence Spirit Shield (focus-type) with high Energy Shield base.",
        "crafting_notes": "Best ES shield. High ES base + implicit +% ES. Tags: int_armour, focus. Key mods: flat ES, +% ES, spell damage, resistances, block chance. Can reach very high ES totals with T1 mods.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Energy Shield", "Block", "Focus"],
        "source": "manual",
    },

    # ── Jewels ────────────────────────────────────────────────────────────────

    {
        "name": "Crimson Jewel",
        "category": "base",
        "description": "Strength-attribute jewel for the passive tree.",
        "crafting_notes": "Rolls Strength-related mods and generic jewel mods. Key mods: maximum life, physical damage, melee damage, area damage, strength. Use Alterations on Magic or Chaos on Rare to craft.",
        "drop_notes": "Common drop.",
        "see_also": ["Cobalt Jewel", "Viridian Jewel", "Jewel Socket"],
        "source": "manual",
    },
    {
        "name": "Cobalt Jewel",
        "category": "base",
        "description": "Intelligence-attribute jewel for the passive tree.",
        "crafting_notes": "Rolls Intelligence-related mods. Key mods: maximum energy shield, spell damage, elemental damage, mana. Use Alterations or Chaos to craft.",
        "drop_notes": "Common drop.",
        "see_also": ["Crimson Jewel", "Viridian Jewel"],
        "source": "manual",
    },
    {
        "name": "Viridian Jewel",
        "category": "base",
        "description": "Dexterity-attribute jewel for the passive tree.",
        "crafting_notes": "Rolls Dexterity-related mods. Key mods: attack speed, evasion, accuracy, projectile damage. Use Alterations or Chaos to craft.",
        "drop_notes": "Common drop.",
        "see_also": ["Crimson Jewel", "Cobalt Jewel"],
        "source": "manual",
    },

    # ── Runes ─────────────────────────────────────────────────────────────────

    {
        "name": "Rune",
        "category": "mechanic_item",
        "description": "Socketable items that add a mod to a socketed equipment piece.",
        "crafting_notes": "Insert into Rune Sockets on weapons and armour. Runes provide significant bonuses (elemental damage, resistances, life, ES). Higher-tier runes require matching the weapon/armour type. Can be removed and reused.",
        "drop_notes": "Drops from monsters and chests. Higher tiers from harder content.",
        "see_also": ["Runic Alloy", "Socket"],
        "source": "manual",
    },
    {
        "name": "Body Rune",
        "category": "currency",
        "description": "Armour rune that grants a significant bonus to maximum life.",
        "crafting_notes": "Insert into rune sockets on body armour or gloves/boots/helmets for a large life bonus. Stacks with life mods. Prioritise T3+ for endgame.",
        "drop_notes": "Drops from monsters; higher tiers from endgame content.",
        "see_also": ["Rune", "Maximum Life"],
        "source": "manual",
    },
    {
        "name": "Mind Rune",
        "category": "currency",
        "description": "Armour rune that grants a bonus to maximum Energy Shield.",
        "crafting_notes": "Best rune for ES builds. Insert into body armour or other gear with ES. Higher tiers give substantially more ES.",
        "drop_notes": "Drops from monsters; higher tiers from endgame.",
        "see_also": ["Rune", "Energy Shield"],
        "source": "manual",
    },

    # ── Catalysts ─────────────────────────────────────────────────────────────

    {
        "name": "Catalyst",
        "category": "mechanic_item",
        "description": "Applied to rings, amulets, and belts to increase the quality of a specific mod type, then randomly rerolls the item.",
        "crafting_notes": "Catalysts improve quality of specific mod types (e.g. Turbulent Catalyst boosts elemental damage mods). Higher quality means higher roll values for matching mods. Apply before Divine Orb for maximum value. Use on Magic items for targeted quality before Regaling.",
        "drop_notes": "Drops from the Metamorph encounter (catalysts from Metamorph organs).",
        "see_also": ["Divine Orb", "Quality"],
        "source": "manual",
    },
    {
        "name": "Turbulent Catalyst",
        "category": "currency",
        "description": "Increases quality of elemental damage mods on rings, amulets, and belts.",
        "crafting_notes": "Apply to jewellery with elemental damage mods (fire, cold, lightning, elemental). Each application adds 5% quality, capped at 20%. Use before Divine Orb for best roll.",
        "drop_notes": "Metamorph organs.",
        "see_also": ["Catalyst", "Elemental Damage"],
        "source": "manual",
    },
    {
        "name": "Prismatic Catalyst",
        "category": "currency",
        "description": "Increases quality of resistance mods on rings, amulets, and belts.",
        "crafting_notes": "Best catalyst for defensive jewellery — resistance mods are the most universally useful. Apply to jewellery before Divine for max res values.",
        "drop_notes": "Metamorph organs.",
        "see_also": ["Catalyst", "Resistances"],
        "source": "manual",
    },
    {
        "name": "Intrinsic Catalyst",
        "category": "currency",
        "description": "Increases quality of attribute mods (Strength, Dexterity, Intelligence) on rings, amulets, and belts.",
        "crafting_notes": "Use on attribute-stacking builds or to fix stat requirements. Boosts all three attribute mod types.",
        "drop_notes": "Metamorph organs.",
        "see_also": ["Catalyst", "Attributes"],
        "source": "manual",
    },

    # ── Distilled Emotions (Amulet Bases) ─────────────────────────────────────

    {
        "name": "Distilled Disgust",
        "category": "currency",
        "description": "Applies a Chaos Resistance implicit to an amulet.",
        "crafting_notes": "Use on amulets to add +% Chaos Resistance as an implicit. Extremely valuable for builds with low chaos resistance. Stack up to 3x for maximum implicit value.",
        "drop_notes": "Drops from Delirium encounters.",
        "see_also": ["Chaos Resistance", "Distilled Emotions"],
        "source": "manual",
    },
    {
        "name": "Distilled Fear",
        "category": "currency",
        "description": "Applies a Cold Resistance implicit to an amulet.",
        "crafting_notes": "Use to add cold resistance implicit on amulets. Stack 3x for maximum value.",
        "drop_notes": "Delirium encounters.",
        "see_also": ["Resistances", "Distilled Emotions"],
        "source": "manual",
    },
    {
        "name": "Distilled Envy",
        "category": "currency",
        "description": "Applies an Energy Shield implicit to an amulet.",
        "crafting_notes": "Best Distilled for ES builds — adds flat ES as an amulet implicit. Stack up to 3x.",
        "drop_notes": "Delirium encounters.",
        "see_also": ["Energy Shield", "Distilled Emotions"],
        "source": "manual",
    },

    # ── Focus (Foci) ──────────────────────────────────────────────────────────

    {
        "name": "Focus",
        "category": "mechanic_item",
        "description": "Intelligence off-hand items (also called foci, plural). Provide Energy Shield and spell bonuses. Used in place of shields by caster builds.",
        "crafting_notes": "Best endgame focus: Tasalian Focus (req 80, 91 ES base). Key mods: flat ES, +% ES, spell damage, cast speed, resistances, gem level bonuses. Tags: focus, int_armour. Use --slot Focus to filter.",
        "drop_notes": "Endgame drop. Search: poe2-lookup '' --type bases --slot Focus",
        "see_also": ["Tasalian Focus", "Sacred Focus", "Energy Shield", "Spell Damage"],
        "source": "manual",
    },
    {
        "name": "Tasalian Focus",
        "category": "base",
        "description": "Best-in-slot Intelligence Focus (foci) with highest Energy Shield base (91 ES, req 80).",
        "crafting_notes": "Best endgame focus base. Target ilvl 80+ for T1 flat ES. Key mods: flat ES (T1 = 91–110), +% ES, spell damage, cast speed, resistances. Tags: focus, int_armour — use --tag focus for mod pool.",
        "drop_notes": "Endgame drop, ilvl 80+ zones.",
        "see_also": ["Sacred Focus", "Focus", "Energy Shield"],
        "source": "manual",
    },
    {
        "name": "Sacred Focus",
        "category": "base",
        "description": "High-end Intelligence Focus with 81 ES base (req 75). Second-best ES focus.",
        "crafting_notes": "Good alternative when Tasalian Focus is unavailable/too expensive. Same mod pool. Tags: focus, int_armour.",
        "drop_notes": "Endgame drop, ilvl 75+ zones.",
        "see_also": ["Tasalian Focus", "Focus"],
        "source": "manual",
    },

    # ── Shields ────────────────────────────────────────────────────────────────

    {
        "name": "Shield",
        "category": "mechanic_item",
        "description": "Off-hand defensive items providing Block chance. Armour shields use Strength; Evasion shields use Dexterity. ES shields (Spirit Shields) use Intelligence.",
        "crafting_notes": "Key mods: block chance, life/ES, resistances, spell damage (ES shields). Armour shields provide the highest block; evasion shields may Parry. Bucklers grant Parry instead of Block.",
        "drop_notes": "Drops throughout the game.",
        "see_also": ["Block", "Parry", "Titanium Spirit Shield", "Buckler"],
        "source": "manual",
    },
    {
        "name": "Buckler",
        "category": "mechanic_item",
        "description": "Evasion-based off-hand shield that grants Parry instead of Block. Parry is a Monk/Dexterity-build mechanic.",
        "crafting_notes": "Use on Dexterity melee builds (e.g. Monk) that benefit from Parry. Key mods: Parry chance, evasion, life, attack speed, resistances.",
        "drop_notes": "Drops throughout the game.",
        "see_also": ["Parry", "Block", "Evasion", "Shield"],
        "source": "manual",
    },

    # ── Quivers ────────────────────────────────────────────────────────────────

    {
        "name": "Quiver",
        "category": "mechanic_item",
        "description": "Off-hand items required for bows. Provide mods affecting projectiles, attack damage, and critical strikes.",
        "crafting_notes": "Key mods: flat physical damage to attacks, +% physical damage, attack speed, critical strike chance/multiplier, projectile speed, added elemental damage to attacks. Top base: Visceral Quiver (req 64). Tags: quiver.",
        "drop_notes": "Drops throughout the game.",
        "see_also": ["Visceral Quiver", "Bow", "Projectile", "Physical Damage"],
        "source": "manual",
    },
    {
        "name": "Visceral Quiver",
        "category": "base",
        "description": "Highest-level quiver base (req 64). Best-in-slot quiver for endgame bow builds.",
        "crafting_notes": "Target ilvl 64+ for T1 bow mods. Key mods: flat physical damage to attacks, attack speed, critical multiplier. Tags: quiver.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Quiver", "Physical Damage", "Attack Speed"],
        "source": "manual",
    },

    # ── Rings (additional) ────────────────────────────────────────────────────

    {
        "name": "Jewellery",
        "category": "mechanic_item",
        "description": "Collective term for rings, amulets, and belts. Jewellery items use Catalysts to boost quality on specific mod types.",
        "crafting_notes": "Key crafting currency: Orb of Alteration (for Magic), Chaos Orb (for Rare), Catalysts (for quality), Divine Orb (for values). Jewellery cannot have Rune Sockets. Best bases: Opal Ring, Two-Stone Ring, Prismatic Ring, Onyx Amulet, Stygian Vise.",
        "drop_notes": "Drops throughout the game.",
        "see_also": ["Ring", "Amulet", "Belt", "Catalyst", "Opal Ring", "Onyx Amulet", "Stygian Vise"],
        "source": "manual",
    },
    {
        "name": "Prismatic Ring",
        "category": "base",
        "description": "Ring with implicit +% to all Elemental Resistances (fire, cold, and lightning). Strongest defensive ring implicit.",
        "crafting_notes": "Best ring for fixing all three elemental resistances at once. The tri-res implicit can free up multiple suffix slots. Key mods: life, ES, remaining resistances, attributes. Pairs with Catalyst (Prismatic) for even higher implicit.",
        "drop_notes": "Uncommon drop; requires req 35.",
        "see_also": ["Two-Stone Ring", "Opal Ring", "Resistances", "Prismatic Catalyst"],
        "source": "manual",
    },
    {
        "name": "Unset Ring",
        "category": "base",
        "description": "Ring with an implicit socket that can hold a Skill Gem, granting its effect without linking.",
        "crafting_notes": "Use to socket a utility skill gem (e.g. Flame Dash, Arcane Surge) without consuming a weapon/armour link. Frees up linked skill slots for main skill. Key mods: life, ES, resistances.",
        "drop_notes": "Uncommon drop; req 44.",
        "see_also": ["Opal Ring", "Two-Stone Ring", "Gem"],
        "source": "manual",
    },
    {
        "name": "Grasping Ring",
        "category": "base",
        "description": "Ring with an implicit offensive effect: your attacks chain an additional time.",
        "crafting_notes": "Best-in-slot ring for Attack builds that benefit from chaining (projectile attacks, AoE chains). The chain implicit is very powerful for coverage and single-target in some scenarios. Key mods: added elemental damage, life, resistances.",
        "drop_notes": "Rare endgame drop; req 40.",
        "see_also": ["Opal Ring", "Chain", "Projectile"],
        "source": "manual",
    },
    {
        "name": "Gold Ring",
        "category": "base",
        "description": "Ring with implicit +% increased Item Rarity of Items found. Best base for MF (magic find) builds.",
        "crafting_notes": "Only relevant for dedicated magic find / item rarity builds. Sacrifices offensive/defensive mods for the rarity implicit. Key mods: item rarity, life, resistances.",
        "drop_notes": "Common drop; req 40.",
        "see_also": ["Opal Ring", "Item Rarity"],
        "source": "manual",
    },

    # ── Amulets (additional) ──────────────────────────────────────────────────

    {
        "name": "Lapis Amulet",
        "category": "base",
        "description": "Amulet with implicit +N to Intelligence.",
        "crafting_notes": "Choose when Intelligence is your stat bottleneck (e.g. high-ES builds requiring heavy int investment). Key mods: ES, life, resistances, spell damage.",
        "drop_notes": "Common drop.",
        "see_also": ["Onyx Amulet", "Intelligence", "Energy Shield"],
        "source": "manual",
    },
    {
        "name": "Amber Amulet",
        "category": "base",
        "description": "Amulet with implicit +N to Strength.",
        "crafting_notes": "Choose when Strength is needed. Strength also provides +0.5 life per point. Key mods: life, resistances, strength.",
        "drop_notes": "Common drop.",
        "see_also": ["Onyx Amulet", "Strength"],
        "source": "manual",
    },
    {
        "name": "Veridical Chain",
        "category": "base",
        "description": "Unique-pattern amulet base with special implicit. Associated with specific game mechanics.",
        "crafting_notes": "Rare endgame base. Check the implicit mod before crafting — it can have powerful unique modifiers not available on other amulets.",
        "drop_notes": "Endgame drop.",
        "see_also": ["Onyx Amulet", "Jade Amulet"],
        "source": "manual",
    },

    # ── Charms ────────────────────────────────────────────────────────────────

    {
        "name": "Charm",
        "category": "mechanic_item",
        "description": "Small items that auto-trigger effects when specific conditions are met (e.g. losing life, being stunned). Equipped in dedicated Charm slots.",
        "crafting_notes": "Charms cannot be crafted with standard orbs — they have their own mod pool (Charm category). Key charms: anti-stun, anti-freeze, life/mana flask effects. Use poe2-lookup '' --type mods --category Charm to see available mods.",
        "drop_notes": "Drops throughout the game. Higher tiers from harder content.",
        "see_also": ["Flask", "Stun", "Freeze"],
        "source": "manual",
    },

    # ── Fragments & Splinters ─────────────────────────────────────────────────

    {
        "name": "Simulacrum",
        "category": "currency",
        "description": "Fragment used to open the Simulacrum encounter (high-density Delirium challenge).",
        "crafting_notes": "Not a crafting item. Used to access high-reward Simulacrum maps for currency farming. Assembles from Simulacrum Splinters (300 splinters = 1 Simulacrum).",
        "drop_notes": "Built from Simulacrum Splinters dropped in Delirium encounters.",
        "see_also": ["Simulacrum Splinter", "Delirium"],
        "source": "manual",
    },
    {
        "name": "Breach Splinter",
        "category": "currency",
        "description": "Fragment of a Breach — collect 300 to create a Breachstone.",
        "crafting_notes": "Not a crafting item. Farm by running Breach encounters in maps. Full Breachstones open dedicated Breach domains with high rewards.",
        "drop_notes": "Dropped by monsters in Breach encounters.",
        "see_also": ["Breach", "Breachstone"],
        "source": "manual",
    },

    # ── Idols ─────────────────────────────────────────────────────────────────

    {
        "name": "Idol",
        "category": "mechanic_item",
        "description": "Augment items that socket into the Augment Sockets on Body Armour or Sceptres to grant Bonded modifiers. Six idol types: Fox, Bear, Wolf, Stag, Boar, Owl — each grants a unique spirit modifier. Idols are also called fox idol, bear idol, wolf idol, stag idol, boar idol, owl idol.",
        "crafting_notes": "Not craftable — drop as-is. Place into an empty Augment Socket in a Body Armour or Sceptre. Higher-quality Augment Sockets accept more powerful idols. Cannot be removed once socketed without a currency item.",
        "drop_notes": "Drops from monsters and league content. Rarer idols from harder encounters.",
        "see_also": ["Body Armour", "Sceptre", "Augment Socket"],
        "source": "manual",
    },

]
