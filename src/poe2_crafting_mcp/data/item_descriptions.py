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
    # for category terms like "foci", "jewellery", "shield", "quiver", "charm".
    # They are NOT scraped from the wiki — they summarise slot mechanics.

    {
        "name": "Jewellery",
        "category": "mechanic_item",
        "description": (
            "Collective term for rings, amulets, and belts (also spelled jewelry). "
            "Jewellery items accept Catalysts to add quality on specific mod types. "
            "They cannot have Rune Sockets."
        ),
        "crafting_notes": (
            "Key crafting currency: Orb of Alteration (Magic reroll), Chaos Orb (Rare reroll), "
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

]
