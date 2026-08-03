"""
Item description seed data — mechanic concept entries only.

These are category/concept entries that do NOT have individual {{Item}} pages
on poe2wiki.net (e.g. "Jewellery" as a category concept, "Focus" as a slot
category). They serve as search aliases so users can find relevant content
by typing generic terms like "foci", "jewellery", "shield", etc.

Individual items (currencies, bases, idols, runes, …) are seeded automatically
from poe2wiki.net via:
    poe2-lookup item-desc-seed        # bulk seed from wiki
    poe2-lookup item-desc-get <name>  # fetch + cache single item on demand
"""

from __future__ import annotations

ITEM_DESCRIPTIONS: list[dict] = [

    # ── Mechanic / Slot Concepts ──────────────────────────────────────────────
    # These entries exist to give users a useful landing page when they search
    # for category terms. They are NOT scraped from the wiki — they summarise
    # slot/category mechanics that don't have individual {{Item}} wiki pages.

    {
        "name": "Jewellery",
        "category": "mechanic_item",
        "description": (
            "Collective term for rings, amulets, and belts (also spelled jewelry). "
            "Jewellery items accept Catalysts to add quality on specific mod types. "
            "They cannot have Rune Sockets."
        ),
        "crafting_notes": (
            "Key crafting currency: Orb of Transmutation (Normal → Magic), Chaos Orb (Rare reroll), "
            "Catalysts (quality on a stat type), Divine Orb (re-roll values). "
            "Best endgame bases: Opal Ring, Two-Stone Ring, Prismatic Ring, Onyx Amulet, "
            "Jade Amulet, Stygian Vise."
        ),
        "drop_notes": "Drops throughout the game at all levels.",
        "see_also": ["Ring", "Amulet", "Belt", "Catalyst", "Opal Ring", "Onyx Amulet"],
        "source": "manual",
    },

    {
        "name": "Focus",
        "category": "mechanic_item",
        "description": (
            "Intelligence off-hand items (also called foci, plural). "
            "Provide Energy Shield and spell-damage bonuses. "
            "Used by caster builds instead of shields. "
            "The slot is called 'Focus' in the UI."
        ),
        "crafting_notes": (
            "Best endgame base: Tasalian Focus (req 80, 91 ES base). "
            "Key mods: flat ES (T1 = 91–110), +% ES, spell damage, cast speed, "
            "resistances, +1 to level of all spell gems. "
            "Tags: focus, int_armour. Use poe2-lookup '' --type bases --slot Focus."
        ),
        "drop_notes": "Endgame drop (acts 4+, high-tier maps).",
        "see_also": ["Tasalian Focus", "Sacred Focus", "Energy Shield", "Spell Damage"],
        "source": "manual",
    },

    {
        "name": "Shield",
        "category": "mechanic_item",
        "description": (
            "Defensive off-hand items for melee/hybrid builds. "
            "Can provide Armour, Evasion, Energy Shield, or hybrid defences "
            "depending on base type. Shields have an implicit block chance. "
            "Bucklers are the Evasion-based subtype."
        ),
        "crafting_notes": (
            "Prioritise block chance (implicit), ES (for hybrid), or armour. "
            "Key mods: block chance, ES, armour, resistances, life. "
            "Use poe2-lookup '' --type bases --slot Shield."
        ),
        "drop_notes": "Drops throughout the game.",
        "see_also": ["Buckler", "Block Chance", "Energy Shield", "Armour"],
        "source": "manual",
    },

    {
        "name": "Quiver",
        "category": "mechanic_item",
        "description": (
            "Off-hand items exclusive to bow builds. "
            "Provide bonuses to bows and projectile attacks. "
            "Cannot be used with other weapon types."
        ),
        "crafting_notes": (
            "Key mods: adds X–Y physical/elemental damage to attacks, "
            "attack speed, critical strike chance, pierce/fork/chain projectiles, "
            "resistances. Use poe2-lookup '' --type bases --slot Quiver."
        ),
        "drop_notes": "Drops throughout the game.",
        "see_also": ["Bow", "Projectile", "Attack Speed"],
        "source": "manual",
    },

    {
        "name": "Charm",
        "category": "mechanic_item",
        "description": (
            "Small consumable-style items that auto-trigger effects when specific "
            "conditions are met (e.g. losing life, being stunned, being frozen). "
            "Equipped in dedicated Charm slots (unlocked via Attribute requirements). "
            "Each charm has charges that refill from killing monsters."
        ),
        "crafting_notes": (
            "Charms have their own mod pool (Charm category) — they cannot be "
            "crafted with standard orbs. Key charms: anti-stun, anti-freeze, "
            "life/mana recovery. "
            "Use poe2-lookup '' --type mods --category Charm to see available mods."
        ),
        "drop_notes": "Drops throughout the game. Higher tiers from harder content.",
        "see_also": ["Flask", "Stun", "Freeze"],
        "source": "manual",
    },

    {
        "name": "Idol",
        "category": "mechanic_item",
        "description": (
            "Augment items that socket into Augment Sockets on Body Armour or Sceptres "
            "to grant Bonded modifier effects. Six spirit types: Fox, Bear, Wolf, Stag, "
            "Boar, Owl — each grants different bonuses depending on which slot it "
            "is socketed into. Search for individual idols: fox idol, bear idol, etc."
        ),
        "crafting_notes": (
            "Place into an empty Augment Socket in a Body Armour or Sceptre. "
            "Once socketed it cannot be retrieved but can be replaced by another Augment item. "
            "Individual idol effects vary by equipment slot (see wiki for full stat text)."
        ),
        "drop_notes": (
            "Drop from Azmeri spirit-possessed monsters with specific hunt modifiers. "
            "Fox Idol drops level 65+."
        ),
        "see_also": ["Fox Idol", "Bear Idol", "Wolf Idol", "Augment Socket", "Sceptre"],
        "source": "manual",
    },

    {
        "name": "Rune",
        "category": "mechanic_item",
        "description": (
            "Augment items that socket into Rune Sockets on weapons and armour pieces. "
            "Each rune provides a significant bonus (elemental damage, life, ES, leech, etc.) "
            "that varies by weapon or armour type. "
            "Runes cannot be retrieved once socketed but can be replaced."
        ),
        "crafting_notes": (
            "Socket into Rune Sockets (not Augment Sockets). "
            "Key runes: Body Rune (life/ES), Mind Rune (mana/ES), "
            "elemental runes for weapon damage. "
            "Higher-tier runes drop from harder endgame content."
        ),
        "drop_notes": "Drops from monsters throughout the game; higher tiers from endgame.",
        "see_also": ["Body Rune", "Mind Rune", "Augment Socket"],
        "source": "manual",
    },

    {
        "name": "Weapon",
        "category": "mechanic_item",
        "description": (
            "Weapons determine your attack skills and damage type. "
            "One-handed: Sword, Axe, Mace, Claw, Dagger, Wand, Sceptre, Flail. "
            "Two-handed: Staff, Quarterstaff, Spear, Bow, Crossbow, Two Hand Sword/Axe/Mace. "
            "Weapons have a Rune Socket for augment effects. "
            "Wands and Staves are spell-casting weapons; Bows/Crossbows are ranged attack weapons."
        ),
        "crafting_notes": (
            "Key weapon mods (by type): "
            "Physical weapons — physical damage %, adds phys damage, attack speed, crit chance. "
            "Spell weapons (Staff/Wand) — spell damage %, cast speed, +1 to level of gems, mana. "
            "Bow/Crossbow — adds elemental damage to attacks, attack speed, crit. "
            "Use poe2-lookup '' --type bases --slot Staff (or Bow, Wand, etc.)."
        ),
        "drop_notes": "All weapon types drop throughout the game; endgame bases from high-tier maps.",
        "see_also": ["Staff", "Wand", "Bow", "Crossbow", "Spear", "Sceptre", "Attack Speed"],
        "source": "manual",
    },

    {
        "name": "Armour",
        "category": "mechanic_item",
        "description": (
            "Armour pieces occupy five slots: Body Armour, Helmet, Gloves, Boots, and Shield/Focus. "
            "Each can be Strength (Armour), Dexterity (Evasion), Intelligence (Energy Shield), "
            "or hybrid combinations. "
            "Armour pieces can have Rune Sockets. "
            "Body Armour and Sceptres can have Augment Sockets for Idols."
        ),
        "crafting_notes": (
            "Defensive stat priority by build type: "
            "ES builds — max ES base + flat ES + %ES + ES recharge. "
            "Armour builds — high base armour + %armour + life. "
            "Evasion builds — base evasion + %evasion + life. "
            "All builds want: resistances + life (or ES). "
            "Use poe2-lookup '' --type bases --slot 'Body Armour' (or Helmet, Gloves, Boots)."
        ),
        "drop_notes": "Drops throughout the game; endgame bases (Vaal Regalia, etc.) from high-tier maps.",
        "see_also": ["Body Armour", "Helmet", "Gloves", "Boots", "Energy Shield", "Evasion"],
        "source": "manual",
    },

    {
        "name": "Flask",
        "category": "mechanic_item",
        "description": (
            "Flask slots: 1 Life Flask + 1 Mana Flask (always available). "
            "Utility Flask slots unlock later (up to 2 extra). "
            "Flasks have charges; using a flask expends charges and begins recovery. "
            "Charges refill from killing monsters, checkpoints, and wells. "
            "Magic flasks have 1–2 mods (prefix + suffix) that add extra effects."
        ),
        "crafting_notes": (
            "Flask mod categories: prefix adds duration/effect, suffix adds conditions/utility. "
            "Key prefixes: Divine (instant recovery), Avian (adds movement speed), "
            "of the Order (reduced charges used). "
            "Key suffixes: of the Ibex (increased recovery), of the Antelope (movement speed), "
            "of Grounding (removes Shock), of the Warding (removes Curses). "
            "Use poe2-lookup '' --type mods --category Flask to list all flask mods. "
            "Alt-spam Flask base to get desired prefix+suffix combo."
        ),
        "drop_notes": "Life/Mana Flasks drop from the start. Utility Flasks from act 2+.",
        "see_also": ["Life Flask", "Mana Flask", "Charges", "Charm"],
        "source": "manual",
    },

    {
        "name": "Jewel",
        "category": "mechanic_item",
        "description": (
            "Small items socketed into Jewel Sockets on the Passive Skill Tree. "
            "Provide powerful stat bonuses (life, ES, damage %, resists, etc.). "
            "Jewel Sockets are scattered throughout the tree; you socket jewels by "
            "clicking the socket and selecting a jewel. "
            "Jewels have their own mod pool (category: Jewel) — different from item mods."
        ),
        "crafting_notes": (
            "Jewels are crafted the same as items: Alt spam (Magic) or Chaos reroll (Rare). "
            "Key jewel mods: % increased damage, life, resistances, % ES, attack/cast speed. "
            "Abyss Jewels (Preserved/Altered variants) can be socketed into Bone Sockets "
            "on items to add a Desecrated modifier. "
            "Use poe2-lookup '' --type mods --category Jewel to see jewel mod pool. "
            "Use poe2-lookup '' --type bases --slot Jewel to see jewel base types."
        ),
        "drop_notes": "Drops from monsters throughout the game.",
        "see_also": ["Abyss Jewel", "Bone Socket", "Passive Tree", "Desecrated Mod"],
        "source": "manual",
    },

    {
        "name": "Waystone",
        "category": "mechanic_item",
        "description": (
            "Waystones are endgame map items used to open map instances in the Atlas. "
            "They have a Tier (1–16) that controls monster level and difficulty. "
            "Magic Waystones have 1–2 mods; Rare Waystones have 3–6 mods. "
            "Mods increase pack size, item rarity, monster damage/life, and add special "
            "mechanics (extra strongboxes, breach, etc.)."
        ),
        "crafting_notes": (
            "Recommended: Chaos reroll to 4–5 mods with high pack size + IIR. "
            "Avoid: monster reflect, no regeneration (if not prepared). "
            "Higher tier Waystones give better bases and more atlas progression. "
            "Use poe2-lookup '' --type bases --slot Waystone to see Waystone tiers."
        ),
        "drop_notes": "Drop from monsters in maps. Higher tier Waystones from higher tier maps.",
        "see_also": ["Atlas", "Map Tier", "Pack Size", "Item Rarity"],
        "source": "manual",
    },

    {
        "name": "Essence",
        "category": "mechanic_item",
        "description": (
            "Essences are currency items that craft a guaranteed explicit modifier onto an item. "
            "Using an Essence on a Normal item creates a Magic item with the guaranteed mod. "
            "Using on a Rare item rerolls all mods (like Chaos Orb) but guarantees one specific mod. "
            "The guaranteed mod varies by essence type AND item class (helmet vs gloves vs weapon etc.)."
        ),
        "crafting_notes": (
            "Essence route: use essence to guarantee your most important mod, "
            "then Alt/Chaos the remaining slots for other desired mods. "
            "Useful when a mod has low weight in the normal pool (or is essence-only). "
            "Key essence types: Horror (life), Sorcery (spell damage), Electricity (lightning), "
            "Battle (physical), Haste (attack speed), Opulence (resistances). "
            "Stack size: 10. Use poe2-lookup <essence name> for exact mod per item class."
        ),
        "drop_notes": "Drop from Essence monsters found in maps and acts.",
        "see_also": ["Chaos Orb", "Orb of Transmutation", "Mod Weight"],
        "source": "manual",
    },

    {
        "name": "Omen",
        "category": "mechanic_item",
        "description": (
            "Omens are single-use currency items that modify the next use of a specific orb. "
            "They are consumed automatically when the trigger orb is used. "
            "Three main Omen types affect Chaos Orb behaviour: "
            "Omen of Whittling (removes lowest-level mod), "
            "Omen of Sinistral Erasure (removes a suffix), "
            "Omen of Dextral Erasure (removes a prefix). "
            "Other Omens affect Exalted Orb, Orb of Annulment, etc."
        ),
        "crafting_notes": (
            "Omens are used with Chaos Orb to protect mods you want to keep. "
            "Example: have a good prefix, use Omen of Sinistral Erasure + Chaos "
            "to reroll only the suffix side. "
            "Omen of Whittling is useful when your worst mod is the lowest-level one. "
            "Omens are expensive — use poe2-price to check current cost before planning."
        ),
        "drop_notes": "Drop from Ritual encounters and special endgame content.",
        "see_also": ["Chaos Orb", "Orb of Annulment", "Prefix", "Suffix"],
        "source": "manual",
    },

    {
        "name": "Abyss Jewel",
        "category": "mechanic_item",
        "description": (
            "Abyss Jewels (Preserved and Altered variants) are socketed into Bone Sockets "
            "on items to grant a hidden Desecrated modifier. "
            "The jewel is consumed when socketed. "
            "The mod is hidden ('Unrevealed') until revealed at a Well of Souls "
            "(found in Abyss encounters in maps). "
            "Five jewel types target different item slots: "
            "Jawbone → Weapon/Quiver, Rib → Armour, Collarbone → Amulet/Ring/Belt, "
            "Cranium → Jewel, Vertebra → Body Armour. "
            "Altered variants (Breach league) have a different 'Otherworldly' mod pool."
        ),
        "crafting_notes": (
            "Desecration adds 1 extra modifier BEYOND the 6-affix cap (special slot). "
            "If the item has no open mod slots, a random existing mod is removed instead. "
            "Do desecration BEFORE bench crafting your last mod to avoid losing it. "
            "Each item can only be desecrated once. "
            "Standard (Preserved) jewels vs Altered (Breach) jewels have different mod pools."
        ),
        "drop_notes": "Preserved variants drop from Abyss encounters. Altered variants from Breach encounters.",
        "see_also": ["Bone Socket", "Well of Souls", "Desecrated Mod", "Abyss", "Breach"],
        "source": "manual",
    },

    {
        "name": "Distilled Emotion",
        "category": "mechanic_item",
        "description": (
            "Distilled Emotions are league currency items (Runes of Aldur league). "
            "They are applied to items to add or modify mods related to emotional resonance. "
            "Types include: Distilled Fear, Distilled Greed, Distilled Guilt, "
            "Distilled Ire, Distilled Suffering, Distilled Disgust, "
            "Distilled Paranoia, Distilled Envy, Distilled Despair."
        ),
        "crafting_notes": (
            "League-specific crafting — mechanic varies by league. "
            "Check poe2wiki for current league mechanics. "
            "Use poe2-lookup <distilled type> for individual item descriptions."
        ),
        "drop_notes": "League-specific drop (Runes of Aldur league encounters).",
        "see_also": ["Runes of Aldur", "Verisium", "Celestial Alloy"],
        "source": "manual",
    },

]
