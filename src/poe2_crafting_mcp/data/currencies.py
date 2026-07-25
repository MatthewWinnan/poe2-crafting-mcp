"""
Static PoE2 currency definitions.

PoB does not ship currency effect data, so this is maintained here.
Add new currencies as GGG releases patches.
"""

# Each entry: (name, category, subcategory, effect, trade_id)
CURRENCIES: list[tuple[str, str, str, str, str]] = [

    # ── General Item Orbs ────────────────────────────────────────────────────
    ("Orb of Transmutation",   "Orb", "Upgrade",  "Upgrades a Normal item to Magic",                           "orb-of-transmutation"),
    ("Orb of Augmentation",    "Orb", "Upgrade",  "Adds an affix to a Magic item with an open slot",           "orb-of-augmentation"),
    ("Orb of Alteration",      "Orb", "Reroll",   "Rerolls the explicit mods on a Magic item",                 "orb-of-alteration"),
    ("Regal Orb",              "Orb", "Upgrade",  "Upgrades a Magic item to Rare, adding one mod",             "regal-orb"),
    ("Orb of Alchemy",         "Orb", "Upgrade",  "Upgrades a Normal item to Rare",                            "orb-of-alchemy"),
    ("Chaos Orb",              "Orb", "Reroll",   "Rerolls the explicit mods on a Rare item",                  "chaos-orb"),
    ("Exalted Orb",            "Orb", "Add",      "Adds a new random mod to a Rare item",                      "exalted-orb"),
    ("Divine Orb",             "Orb", "Revalue",  "Rerandomises the numeric values of all mods on an item",    "divine-orb"),
    ("Orb of Annulment",       "Orb", "Remove",   "Removes one random mod from an item",                       "orb-of-annulment"),
    ("Orb of Scouring",        "Orb", "Remove",   "Removes all mods from an item, returning it to Normal",     "orb-of-scouring"),
    ("Vaal Orb",               "Orb", "Corrupt",  "Corrupts an item with a random outcome",                    "vaal-orb"),
    ("Orb of Chance",          "Orb", "Upgrade",  "Upgrades a Normal item to random rarity (may create Unique)","orb-of-chance"),
    ("Blessed Orb",            "Orb", "Revalue",  "Rerandomises the numeric values of implicit mods",          "blessed-orb"),
    ("Mirror of Kalandra",     "Orb", "Special",  "Creates a mirrored copy of an item (copy cannot be modified)","mirror-of-kalandra"),
    ("Orb of Conflict",        "Orb", "Upgrade",  "Upgrades a Unique item to its next tier variant",           "orb-of-conflict"),
    ("Fracturing Orb",         "Orb", "Special",  "Fractures one random mod on a Rare item (locked permanently)","fracturing-orb"),

    # ── Quality Currencies ────────────────────────────────────────────────────
    ("Armourer's Scrap",       "Quality", "Armour",  "+5% quality on an armour piece",                         "armourers-scrap"),
    ("Blacksmith's Whetstone", "Quality", "Weapon",  "+5% quality on a weapon",                                "blacksmiths-whetstone"),
    ("Glassblower's Bauble",   "Quality", "Flask",   "+5% quality on a flask",                                 "glassblowers-bauble"),
    ("Gemcutter's Prism",      "Quality", "Gem",     "+5% quality on a gem (max 20%)",                         "gemcutters-prism"),
    ("Artificer's Orb",        "Quality", "Socketed","Adds or improves a socket on an item",                   "artificers-orb"),

    # ── Essences ──────────────────────────────────────────────────────────────
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
    ("Precursor Tablet",       "Other",    "Tower",   "Maps a tower with modifiers for the surrounding region","precursor-tablet"),
    ("Logbook",                "Other",    "Expedition","Expedition logbook to run an Expedition encounter","logbook"),
    ("Barya",                  "Other",    "Trial",   "Currency used for the Trial of the Ancestor",       "barya"),
    ("Ultimatum Inscription",  "Other",    "Trial",   "Currency used for the Trial of Chaos",              "ultimatum-inscription"),

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
