"""
Static PoE2 currency definitions.

PoB does not ship currency effect data, so this is maintained here.
Add new currencies as GGG releases patches.
"""

# Each entry: (name, category, subcategory, effect, trade_id)
CURRENCIES: list[tuple[str, str, str, str, str]] = [

    # ── General Item Orbs ────────────────────────────────────────────────────
    ("Orb of Transmutation",   "Orb", "Upgrade",  "Upgrades a Normal item to Magic with 1-2 random modifiers",    "orb-of-transmutation"),
    ("Orb of Augmentation",    "Orb", "Upgrade",  "Adds a random modifier to a Magic item with an open slot",  "orb-of-augmentation"),
    ("Regal Orb",              "Orb", "Upgrade",  "Upgrades a Magic item to Rare, adding one random mod",      "regal-orb"),
    ("Orb of Alchemy",         "Orb", "Upgrade",  "Upgrades a Normal or Magic item to Rare with 4 random modifiers. Current modifiers are not retained.", "orb-of-alchemy"),
    ("Chaos Orb",              "Orb", "Reroll",   "Removes 1 random mod and adds 1 random mod on a Rare item", "chaos-orb"),
    ("Exalted Orb",            "Orb", "Add",      "Adds a new random modifier to a Rare item",                 "exalted-orb"),
    ("Divine Orb",             "Orb", "Revalue",  "Rerandomises the numeric values of all explicit mods within their tier ranges", "divine-orb"),
    ("Orb of Annulment",       "Orb", "Remove",   "Removes one random explicit mod from a Magic or Rare item", "orb-of-annulment"),
    ("Orb of Scouring",        "Orb", "Remove",   "Does not exist in PoE2. Use reforging bench to recycle items.", "orb-of-scouring"),
    ("Vaal Orb",               "Orb", "Corrupt",  "Corrupts an item unpredictably: no change, reroll up to 3 mods, add enchantment, or add socket", "vaal-orb"),
    ("Orb of Chance",          "Orb", "Upgrade",  "Upgrades a Normal item to random rarity (may create Unique)","orb-of-chance"),
    ("Blessed Orb",            "Orb", "Revalue",  "Rerandomises the numeric values of implicit mods",          "blessed-orb"),
    ("Mirror of Kalandra",     "Orb", "Special",  "Creates a mirrored copy of an item (copy cannot be modified)","mirror-of-kalandra"),
    ("Orb of Conflict",        "Orb", "Upgrade",  "Upgrades a Unique item to its next tier variant",           "orb-of-conflict"),
    ("Fracturing Orb",         "Orb", "Special",  "Fractures one random mod on a Rare item with 4+ mods (locked permanently)", "fracturing-orb"),

    # ── Greater/Perfect Variants ──────────────────────────────────────────────
    ("Greater Orb of Transmutation", "Orb", "Upgrade", "Upgrades Normal to Magic. Guaranteed min modifier level 44.", "greater-orb-of-transmutation"),
    ("Perfect Orb of Transmutation", "Orb", "Upgrade", "Upgrades Normal to Magic. Guaranteed min modifier level 70.", "perfect-orb-of-transmutation"),
    ("Greater Orb of Augmentation",  "Orb", "Upgrade", "Adds a mod to Magic item. Guaranteed min modifier level 44.", "greater-orb-of-augmentation"),
    ("Perfect Orb of Augmentation",  "Orb", "Upgrade", "Adds a mod to Magic item. Guaranteed min modifier level 70.", "perfect-orb-of-augmentation"),
    ("Greater Regal Orb",            "Orb", "Upgrade", "Upgrades Magic to Rare, adding one mod. Min modifier level 35.", "greater-regal-orb"),
    ("Perfect Regal Orb",            "Orb", "Upgrade", "Upgrades Magic to Rare, adding one mod. Min modifier level 50.", "perfect-regal-orb"),
    ("Greater Chaos Orb",            "Orb", "Reroll",  "Removes 1 + adds 1 on Rare. Added mod min level 35.",  "greater-chaos-orb"),
    ("Perfect Chaos Orb",            "Orb", "Reroll",  "Removes 1 + adds 1 on Rare. Added mod min level 50.",  "perfect-chaos-orb"),
    ("Greater Exalted Orb",          "Orb", "Add",     "Adds a random mod to Rare. Min modifier level 35.",    "greater-exalted-orb"),
    ("Perfect Exalted Orb",          "Orb", "Add",     "Adds a random mod to Rare. Min modifier level 50.",    "perfect-exalted-orb"),

    # ── Quality Currencies ────────────────────────────────────────────────────
    ("Armourer's Scrap",       "Quality", "Armour",  "+5% quality on an armour piece",                         "armourers-scrap"),
    ("Blacksmith's Whetstone", "Quality", "Weapon",  "+5% quality on a weapon",                                "blacksmiths-whetstone"),
    ("Glassblower's Bauble",   "Quality", "Flask",   "+5% quality on a flask",                                 "glassblowers-bauble"),
    ("Gemcutter's Prism",      "Quality", "Gem",     "+5% quality on a gem (max 20%)",                         "gemcutters-prism"),
    ("Artificer's Orb",        "Quality", "Socketed","Adds or improves a socket on an item",                   "artificers-orb"),

    # ── Essences ──────────────────────────────────────────────────────────────
    # Legacy names (poe.ninja still tracks some of these)
    ("Essence of Electricity", "Essence", "Elemental",  "Guarantees a lightning damage mod; upgrades Normal → Rare","essence-of-electricity"),
    ("Essence of Ice",         "Essence", "Elemental",  "Guarantees a cold damage mod; upgrades Normal → Rare",     "essence-of-ice"),
    ("Essence of Flames",      "Essence", "Elemental",  "Guarantees a fire damage mod; upgrades Normal → Rare",     "essence-of-flames"),
    ("Essence of Misery",      "Essence", "Chaos",      "Guarantees a chaos damage mod; upgrades Normal → Rare",    "essence-of-misery"),
    ("Essence of Haste",       "Essence", "Speed",      "Guarantees an attack/cast speed mod; upgrades Normal → Rare","essence-of-haste"),
    ("Essence of Sorrow",      "Essence", "Life",       "Guarantees a maximum life mod; upgrades Normal → Rare",    "essence-of-sorrow"),
    ("Essence of Greed",       "Essence", "Mana",       "Guarantees a maximum mana mod; upgrades Normal → Rare",    "essence-of-greed"),
    ("Essence of Rage",        "Essence", "Physical",   "Guarantees a physical damage mod; upgrades Normal → Rare", "essence-of-rage"),
    ("Essence of Torment",     "Essence", "Damage",     "Guarantees an increased damage mod; upgrades Normal → Rare","essence-of-torment"),
    ("Essence of Contempt",    "Essence", "Resistance", "Guarantees a resistance penetration mod",                  "essence-of-contempt"),
    ("Essence of Envy",        "Essence", "Attribute",  "Guarantees an attribute mod; upgrades Normal → Rare",      "essence-of-envy"),
    ("Essence of Scorn",       "Essence", "Physical",   "Guarantees an attack damage mod",                          "essence-of-scorn"),
    ("Essence of Woe",         "Essence", "Spell",      "Guarantees a spell damage mod",                            "essence-of-woe"),
    ("Essence of Zeal",        "Essence", "Speed",      "Guarantees a skill speed mod",                             "essence-of-zeal"),
    ("Essence of Dread",       "Essence", "Defence",    "Guarantees a defence mod (armour/evasion/ES)",             "essence-of-dread"),
    ("Essence of Spite",       "Essence", "DoT",        "Guarantees a damage-over-time mod",                        "essence-of-spite"),
    ("Essence of Hysteria",    "Essence", "Speed",      "Guarantees a movement/attack speed mod",                   "essence-of-hysteria"),
    ("Essence of Horror",      "Essence", "Special",    "Guarantees a powerful defence + offence hybrid mod",       "essence-of-horror"),
    ("Essence of Loathing",    "Essence", "Utility",    "Guarantees a movement speed mod (boots)",                  "essence-of-loathing"),
    ("Essence of Insanity",    "Essence", "Special",    "Guarantees an exotic proc mod",                            "essence-of-insanity"),
    ("Essence of Delirium",    "Essence", "Special",    "Guarantees a complex proc/threshold mod",                  "essence-of-delirium"),
    # PoE2 current-league variants — Lesser/Greater tiers (confirmed via poe.ninja)
    ("Lesser Essence of Electricity", "Essence", "Elemental", "Lesser: guarantees a lightning damage mod",          "lesser-essence-of-electricity"),
    ("Greater Essence of Electricity","Essence", "Elemental", "Greater: guarantees a stronger lightning mod",       "greater-essence-of-electricity"),
    ("Lesser Essence of Ice",          "Essence", "Elemental", "Lesser: guarantees a cold damage mod",              "lesser-essence-of-ice"),
    ("Greater Essence of Ice",         "Essence", "Elemental", "Greater: guarantees a stronger cold mod",           "greater-essence-of-ice"),
    ("Lesser Essence of Flames",       "Essence", "Elemental", "Lesser: guarantees a fire damage mod",              "lesser-essence-of-flames"),
    ("Greater Essence of Flames",      "Essence", "Elemental", "Greater: guarantees a stronger fire mod",           "greater-essence-of-flames"),
    ("Lesser Essence of Haste",        "Essence", "Speed",     "Lesser: guarantees an attack/cast speed mod",       "lesser-essence-of-haste"),
    ("Greater Essence of Haste",       "Essence", "Speed",     "Greater: guarantees a stronger speed mod",          "greater-essence-of-haste"),
    ("Lesser Essence of the Body",     "Essence", "Life",      "Lesser: guarantees a life/energy shield mod",       "lesser-essence-of-the-body"),
    ("Greater Essence of the Body",    "Essence", "Life",      "Greater: guarantees a stronger life/ES mod",        "greater-essence-of-the-body"),
    ("Lesser Essence of the Mind",     "Essence", "Mana",      "Lesser: guarantees a mana mod",                     "lesser-essence-of-the-mind"),
    ("Greater Essence of the Mind",    "Essence", "Mana",      "Greater: guarantees a stronger mana mod",           "greater-essence-of-the-mind"),
    ("Lesser Essence of Ruin",         "Essence", "Physical",  "Lesser: guarantees a physical damage mod",          "lesser-essence-of-ruin"),
    ("Greater Essence of Ruin",        "Essence", "Physical",  "Greater: guarantees a stronger physical mod",       "greater-essence-of-ruin"),

    # ── Runes (socketables) ───────────────────────────────────────────────────
    ("Iron Rune",              "Rune", "Armour",       "Grants armour to the socketed item",                "iron-rune"),
    ("Steel Rune",             "Rune", "Armour",       "Grants more armour (higher tier than Iron)",        "steel-rune"),
    ("Guarding Rune",          "Rune", "Armour",       "Grants high armour (highest tier)",                 "guarding-rune"),
    ("Wind Rune",              "Rune", "Evasion",      "Grants evasion to the socketed item",               "wind-rune"),
    ("Zeal Rune",              "Rune", "Evasion",      "Grants more evasion",                               "zeal-rune"),
    ("Flight Rune",            "Rune", "Evasion",      "Grants high evasion",                               "flight-rune"),
    ("Mind Rune",              "Rune", "Energy Shield","Grants energy shield to the socketed item",          "mind-rune"),
    ("Body Rune",              "Rune", "Life",         "Grants maximum life to the socketed item",          "body-rune"),
    ("Blood Rune",             "Rune", "Life",         "Grants more maximum life",                          "blood-rune"),
    ("Spirit Rune",            "Rune", "Mana",         "Grants maximum mana to the socketed item",          "spirit-rune"),
    ("Flame Rune",             "Rune", "Resistance",   "Grants fire resistance",                            "flame-rune"),
    ("Ice Rune",               "Rune", "Resistance",   "Grants cold resistance",                            "ice-rune"),
    ("Storm Rune",             "Rune", "Resistance",   "Grants lightning resistance",                       "storm-rune"),
    ("Chaos Rune",             "Rune", "Resistance",   "Grants chaos resistance",                           "chaos-rune"),
    ("Inspiration Rune",       "Rune", "Attribute",    "Grants attributes to the socketed item",            "inspiration-rune"),
    ("Breach Rune",            "Rune", "League",       "League-specific rune from Breach",                  "breach-rune"),
    # Perfect rune variants (max-quality, confirmed on poe.ninja)
    ("Perfect Iron Rune",      "Rune", "Armour",       "Perfect quality: grants significantly more armour than Iron Rune",       "perfect-iron-rune"),
    ("Perfect Mind Rune",      "Rune", "Energy Shield","Perfect quality: grants significantly more energy shield than Mind Rune", "perfect-mind-rune"),
    ("Perfect Body Rune",      "Rune", "Life",         "Perfect quality: grants significantly more maximum life than Body Rune",  "perfect-body-rune"),
    ("Perfect Storm Rune",     "Rune", "Resistance",   "Perfect quality: grants significantly more lightning resistance",         "perfect-storm-rune"),
    ("Perfect Inspiration Rune","Rune","Attribute",    "Perfect quality: grants significantly more attributes",                   "perfect-inspiration-rune"),

    # ── Soul Cores ────────────────────────────────────────────────────────────
    ("Soul Core of Zalatl",    "SoulCore", "Damage",  "Adds fire damage to attacks and spells",            "soul-core-of-zalatl"),
    ("Soul Core of Azcapa",    "SoulCore", "Damage",  "Adds cold damage to attacks and spells",            "soul-core-of-azcapa"),
    ("Soul Core of Opiloti",   "SoulCore", "Damage",  "Adds lightning damage to attacks and spells",       "soul-core-of-opiloti"),
    ("Soul Core of Tacati",    "SoulCore", "Speed",   "Grants attack speed",                               "soul-core-of-tacati"),
    ("Soul Core of Topotante", "SoulCore", "Life",    "Grants maximum life",                               "soul-core-of-topotante"),
    ("Soul Core of Atmohua",   "SoulCore", "Mana",    "Grants maximum mana",                               "soul-core-of-atmohua"),
    ("Soul Core of Iquihua",   "SoulCore", "Defence", "Grants armour",                                     "soul-core-of-iquihua"),
    ("Soul Core of Cholotl",   "SoulCore", "Defence", "Grants evasion",                                    "soul-core-of-cholotl"),
    ("Soul Core of Citaqualotl","SoulCore","Defence",  "Grants energy shield",                              "soul-core-of-citaqualotl"),
    ("Soul Core of Puhuarte",  "SoulCore", "Resistance","Grants elemental resistance",                      "soul-core-of-puhuarte"),
    ("Soul Core of Quipolatl", "SoulCore", "Crit",    "Grants critical hit chance",                        "soul-core-of-quipolatl"),
    # Runes of Aldur league soul core (new format)
    ("Xopec's Soul Core of Power", "SoulCore", "Charges", "Grants power charge bonuses",                   "xopecs-soul-core-of-power"),

    # ── Distilled Emotions (Essence-like, from Ultimatum/league) ─────────────
    ("Distilled Fear",         "Distilled", "Damage",    "Guarantees a cold or chaos damage mod",          "distilled-fear"),
    ("Distilled Despair",      "Distilled", "Damage",    "Guarantees a chaos damage / DoT mod",            "distilled-despair"),
    ("Distilled Suffering",    "Distilled", "Life",      "Guarantees a maximum life mod",                  "distilled-suffering"),
    ("Distilled Guilt",        "Distilled", "Speed",     "Guarantees an attack or cast speed mod",         "distilled-guilt"),
    ("Distilled Ire",          "Distilled", "Physical",  "Guarantees a physical damage mod",               "distilled-ire"),
    ("Distilled Isolation",    "Distilled", "Evasion",   "Guarantees an evasion mod",                      "distilled-isolation"),
    ("Distilled Disgust",      "Distilled", "Armour",    "Guarantees an armour mod",                       "distilled-disgust"),
    ("Distilled Jealousy",     "Distilled", "Elemental", "Guarantees an elemental damage mod",             "distilled-jealousy"),
    ("Distilled Greed",        "Distilled", "Mana",      "Guarantees a maximum mana mod",                  "distilled-greed"),
    ("Distilled Paranoia",     "Distilled", "Special",   "Guarantees a powerful unique-tier mod",          "distilled-paranoia"),
    ("Distilled Contempt",     "Distilled", "Resistance","Guarantees a resistance mod",                    "distilled-contempt"),

    # ── League-Specific Currencies ────────────────────────────────────────────
    ("Breach Splinter",        "Fragment", "Breach",  "Combine 100 to open a Breachstone",                "breach-splinter"),
    ("Xoph's Splinter",        "Fragment", "Breach",  "Splinter of Xoph (Fire Breach)",                   "xophs-splinter"),
    ("Tul's Splinter",         "Fragment", "Breach",  "Splinter of Tul (Cold Breach)",                    "tuls-splinter"),
    ("Esh's Splinter",         "Fragment", "Breach",  "Splinter of Esh (Lightning Breach)",               "eshs-splinter"),
    ("Uul-Netol's Splinter",   "Fragment", "Breach",  "Splinter of Uul-Netol (Physical Breach)",          "uul-netols-splinter"),
    ("Chayula's Splinter",     "Fragment", "Breach",  "Splinter of Chayula (Chaos Breach)",               "chayulas-splinter"),
    ("Simulacrum Splinter",    "Fragment", "Delirium","Combine 300 to open a Simulacrum",                  "simulacrum-splinter"),
    ("Simulacrum",             "Fragment", "Delirium","Opens a Simulacrum encounter (crafted from 300 splinters)","simulacrum"),
    ("Kulemak's Invitation",   "Fragment", "Boss",    "Opens access to the Kulemak pinnacle boss encounter","kulemaks-invitation"),
    ("Precursor Tablet",       "Other",    "Tower",   "Maps a tower with modifiers for the surrounding region","precursor-tablet"),
    ("Logbook",                "Other",    "Expedition","Expedition logbook to run an Expedition encounter","logbook"),
    ("Barya",                  "Other",    "Trial",   "Currency used for the Trial of the Ancestor",       "barya"),
    ("Ultimatum Inscription",  "Other",    "Trial",   "Currency used for the Trial of Chaos",              "ultimatum-inscription"),

    # ── Idols (Augment socketables for Body Armour / Sceptre) ────────────────
    # Idols socket into Augment Sockets on Body Armour or Sceptres, granting
    # Bonded modifier effects. Bonded mods appear when the idol is socketed.
    # Place into an empty Augment Socket in a Body Armour or Sceptre to apply
    # its effect. Once socketed it cannot be retrieved but can be replaced.
    ("Fox Idol",   "Idol", "Augment", "Socket into a Body Armour or Sceptre Augment Socket to grant fox spirit Bonded modifiers",   "fox-idol"),
    ("Bear Idol",  "Idol", "Augment", "Socket into a Body Armour or Sceptre Augment Socket to grant bear spirit Bonded modifiers",  "bear-idol"),
    ("Wolf Idol",  "Idol", "Augment", "Socket into a Body Armour or Sceptre Augment Socket to grant wolf spirit Bonded modifiers",  "wolf-idol"),
    ("Stag Idol",  "Idol", "Augment", "Socket into a Body Armour or Sceptre Augment Socket to grant stag spirit Bonded modifiers",  "stag-idol"),
    ("Boar Idol",  "Idol", "Augment", "Socket into a Body Armour or Sceptre Augment Socket to grant boar spirit Bonded modifiers",  "boar-idol"),
    ("Owl Idol",   "Idol", "Augment", "Socket into a Body Armour or Sceptre Augment Socket to grant owl spirit Bonded modifiers",   "owl-idol"),

    # ── Omens (single-use crafting items, poe.ninja type = "Ritual") ──────────
    ("Omen of Whittling",        "Omen", "Crafting", "Single-use crafting item: reforges a modifier on an item",           "omen-of-whittling"),
    ("Omen of Sinistral Erasure","Omen", "Crafting", "Single-use crafting item: removes a prefix modifier from an item",   "omen-of-sinistral-erasure"),
    ("Omen of Dextral Erasure",  "Omen", "Crafting", "Single-use crafting item: removes a suffix modifier from an item",   "omen-of-dextral-erasure"),
    ("Omen of Amelioration",     "Omen", "Crafting", "Single-use crafting item: upgrades a modifier to a higher tier",     "omen-of-amelioration"),
    ("Omen of Resurgence",       "Omen", "Crafting", "Single-use item: restores life and mana to full during combat",      "omen-of-resurgence"),

    # ── Lineage Support Gems (Runes of Aldur league mechanic) ─────────────────
    ("Seraph's Heart", "LineageGem", "Support", "Lineage support gem from the Runes of Aldur league mechanic", "seraphs-heart"),

    # ── Expedition Artifacts ──────────────────────────────────────────────────
    ("Chilling Flux",  "Expedition", "Artifact", "Expedition reagent: adds cold-related modifiers to excavated items", "chilling-flux"),

    # ── Verisium ──────────────────────────────────────────────────────────────
    ("Runic Alloy",    "Verisium", "Material", "Verisium crafting material used to upgrade runes to Perfect quality", "runic-alloy"),

    # ── Catalysts ─────────────────────────────────────────────────────────────
    ("Turbulent Catalyst",     "Catalyst", "Elemental", "Adds quality that enhances elemental damage mods","turbulent-catalyst"),
    ("Imbued Catalyst",        "Catalyst", "Elemental", "Adds quality that enhances caster mods",          "imbued-catalyst"),
    ("Fertile Catalyst",       "Catalyst", "Life",      "Adds quality that enhances life and mana mods",   "fertile-catalyst"),
    ("Prismatic Catalyst",     "Catalyst", "Resistance","Adds quality that enhances resistance mods",       "prismatic-catalyst"),
    ("Intrinsic Catalyst",     "Catalyst", "Attribute", "Adds quality that enhances attribute mods",       "intrinsic-catalyst"),
    ("Tempering Catalyst",     "Catalyst", "Defence",   "Adds quality that enhances defence mods",         "tempering-catalyst"),
    ("Abrasive Catalyst",      "Catalyst", "Crit",      "Adds quality that enhances critical strike mods", "abrasive-catalyst"),
    ("Noxious Catalyst",       "Catalyst", "DoT",       "Adds quality that enhances damage-over-time mods","noxious-catalyst"),
]
