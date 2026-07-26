"""
Slug lists for General exchange categories on poe.ninja.

Each key in EXCHANGE_SLUGS is a poe.ninja item_type used with:
  GET /poe2/api/economy/exchange/current/details?league=...&type=<key>&id=<slug>

Categories that use this endpoint (availableViews includes "exchange"):
  Runes, Essences, SoulCores, Breach (Catalysts), Delirium (Liquid Emotions),
  Fragments, UncutGems, LineageSupportGems, Abyss, Idols, Ritual (Omens),
  Expedition, Verisium.

NOTE: poe.ninja's Currency exchange type covers: Orbs, Quality currencies, and
the misc "Other" items (Barya, Logbook, etc.) — those are handled separately
in currencies.py via fetch_currency_rates().
"""
from __future__ import annotations

from poe2_crafting_mcp.data.currencies import CURRENCIES


def _by_cat(cat: str) -> list[tuple[str, str]]:
    """Extract (name, trade_slug) pairs from CURRENCIES filtered by category."""
    return [(c[0], c[4]) for c in CURRENCIES if c[1] == cat and c[4]]


# Maps poe.ninja item_type → list of (display_name, trade_slug)
EXCHANGE_SLUGS: dict[str, list[tuple[str, str]]] = {

    # ── Runes ─────────────────────────────────────────────────────────────────
    "Runes": _by_cat("Rune"),

    # ── Essences ──────────────────────────────────────────────────────────────
    "Essences": _by_cat("Essence"),

    # ── Soul Cores ────────────────────────────────────────────────────────────
    "SoulCores": _by_cat("SoulCore"),

    # ── Breach: Catalysts, Wombgifts, Splinters (poe.ninja type = "Breach") ────
    # PoE2 catalysts apply quality to rings/amulets; Refined variants apply to jewels.
    # Wombgifts are the PoE2 equivalent of Breachstones.
    # NOTE: PoE1 catalyst names (Turbulent, Imbued, etc.) are NOT in PoE2.
    "Breach": [
        # Splinters & Breachstones
        ("Breach Splinter",          "breach-splinter"),
        ("Breachstone",              "breachstone"),
        ("Banded Wombgift",          "banded-wombgift"),
        ("Ornate Wombgift",          "ornate-wombgift"),
        ("Signet Wombgift",          "signet-wombgift"),
        ("Lavish Wombgift",          "lavish-wombgift"),
        ("Revelatory Wombgift",      "revelatory-wombgift"),
        # Catalysts (ring/amulet quality)
        ("Adaptive Catalyst",        "adaptive-catalyst"),
        ("Carapace Catalyst",        "carapace-catalyst"),
        ("Chayula's Catalyst",       "chayulas-catalyst"),
        ("Esh's Catalyst",           "eshs-catalyst"),
        ("Flesh Catalyst",           "flesh-catalyst"),
        ("Necrotic Catalyst",        "necrotic-catalyst"),
        ("Neural Catalyst",          "neural-catalyst"),
        ("Reaver Catalyst",          "reaver-catalyst"),
        ("Sibilant Catalyst",        "sibilant-catalyst"),
        ("Skittering Catalyst",      "skittering-catalyst"),
        ("Tul's Catalyst",           "tuls-catalyst"),
        ("Uul-Netol's Catalyst",     "uul-netols-catalyst"),
        ("Xoph's Catalyst",          "xophs-catalyst"),
        # Refined Catalysts (jewel quality)
        ("Refined Adaptive Catalyst",    "refined-adaptive-catalyst"),
        ("Refined Carapace Catalyst",    "refined-carapace-catalyst"),
        ("Refined Chayula's Catalyst",   "refined-chayulas-catalyst"),
        ("Refined Esh's Catalyst",       "refined-eshs-catalyst"),
        ("Refined Flesh Catalyst",       "refined-flesh-catalyst"),
        ("Refined Necrotic Catalyst",    "refined-necrotic-catalyst"),
        ("Refined Neural Catalyst",      "refined-neural-catalyst"),
        ("Refined Reaver Catalyst",      "refined-reaver-catalyst"),
        ("Refined Sibilant Catalyst",    "refined-sibilant-catalyst"),
        ("Refined Skittering Catalyst",  "refined-skittering-catalyst"),
        ("Refined Tul's Catalyst",       "refined-tuls-catalyst"),
        ("Refined Uul-Netol's Catalyst", "refined-uul-netols-catalyst"),
        ("Refined Xoph's Catalyst",      "refined-xophs-catalyst"),
    ],

    # ── Liquid Emotions (poe.ninja type = "Delirium") ─────────────────────────
    # PoE2 Delirium items are named "Liquid *" variants, NOT "Distilled *".
    # (Distilled items in currencies.py are PoE1 data and don't apply here.)
    "Delirium": [
        # Base tier
        ("Diluted Liquid Greed",      "diluted-liquid-greed"),
        ("Diluted Liquid Guilt",      "diluted-liquid-guilt"),
        ("Diluted Liquid Ire",        "diluted-liquid-ire"),
        ("Liquid Despair",            "liquid-despair"),
        ("Liquid Disgust",            "liquid-disgust"),
        ("Liquid Envy",               "liquid-envy"),
        ("Liquid Paranoia",           "liquid-paranoia"),
        # Potent tier
        ("Concentrated Liquid Fear",      "concentrated-liquid-fear"),
        ("Concentrated Liquid Isolation", "concentrated-liquid-isolation"),
        ("Concentrated Liquid Suffering", "concentrated-liquid-suffering"),
        ("Potent Liquid Contempt",        "potent-liquid-contempt"),
        ("Potent Liquid Ferocity",        "potent-liquid-ferocity"),
        ("Potent Liquid Melancholy",      "potent-liquid-melancholy"),
        # Ancient tier (applied to Time-Lost Jewels)
        ("Ancient Diluted Liquid Greed",          "ancient-diluted-liquid-greed"),
        ("Ancient Diluted Liquid Guilt",          "ancient-diluted-liquid-guilt"),
        ("Ancient Diluted Liquid Ire",            "ancient-diluted-liquid-ire"),
        ("Ancient Liquid Despair",                "ancient-liquid-despair"),
        ("Ancient Liquid Disgust",                "ancient-liquid-disgust"),
        ("Ancient Liquid Envy",                   "ancient-liquid-envy"),
        ("Ancient Liquid Paranoia",               "ancient-liquid-paranoia"),
        ("Ancient Concentrated Liquid Fear",      "ancient-concentrated-liquid-fear"),
        ("Ancient Concentrated Liquid Isolation", "ancient-concentrated-liquid-isolation"),
        ("Ancient Concentrated Liquid Suffering", "ancient-concentrated-liquid-suffering"),
        ("Ancient Potent Liquid Contempt",        "ancient-potent-liquid-contempt"),
        ("Ancient Potent Liquid Ferocity",        "ancient-potent-liquid-ferocity"),
        ("Ancient Potent Liquid Melancholy",      "ancient-potent-liquid-melancholy"),
    ],

    # ── Abyssal Bones (poe.ninja type = "Abyss") ──────────────────────────────
    # Socketable bones that "desecrate" (abyssalify) rare items with Abyss mods.
    "Abyss": [
        # Ribs (armour)
        ("Gnawed Rib",       "gnawed-rib"),
        ("Ancient Rib",      "ancient-rib"),
        ("Preserved Rib",    "preserved-rib"),
        # Jawbones (weapon/quiver)
        ("Gnawed Jawbone",   "gnawed-jawbone"),
        ("Ancient Jawbone",  "ancient-jawbone"),
        ("Preserved Jawbone","preserved-jawbone"),
        # Collarbones (amulet/ring/belt)
        ("Gnawed Collarbone",   "gnawed-collarbone"),
        ("Ancient Collarbone",  "ancient-collarbone"),
        ("Altered Collarbone",  "altered-collarbone"),
        ("Preserved Collarbone","preserved-collarbone"),
        # Other bones
        ("Preserved Cranium",   "preserved-cranium"),
        ("Preserved Vertebrae", "preserved-vertebrae"),
        # Unique Abyss items (Gaze jewels)
        ("Amanamu's Gaze",  "amanamus-gaze"),
        ("Kurgal's Gaze",   "kurgals-gaze"),
        ("Tecrod's Gaze",   "tecrods-gaze"),
        ("Ulaman's Gaze",   "ulamans-gaze"),
    ],

    # ── Fragments (Breach splinters, Simulacrum splinter) ────────────────────
    "Fragments": _by_cat("Fragment"),

    # ── Uncut Gems ────────────────────────────────────────────────────────────
    # Slug format confirmed: "uncut-skill-gem-level-N" / "uncut-spirit-gem-level-N"
    # Level 14 is the lowest tracked; level 20 has the most volume (2000+).
    # Uncut Support Gem does not appear to be tracked by poe.ninja for PoE2.
    "UncutGems": [
        *(
            (f"Uncut Skill Gem (Level {lvl})", f"uncut-skill-gem-level-{lvl}")
            for lvl in range(14, 21)
        ),
        *(
            (f"Uncut Spirit Gem (Level {lvl})", f"uncut-spirit-gem-level-{lvl}")
            for lvl in range(14, 21)
        ),
    ],

    # ── TODO: confirm slugs from poe.ninja for these categories ──────────────
    # "LineageSupportGems": [],  # Lineage support gems from league mechanic
    # "Idols":              [],  # Tower modifier idols for atlas
    # "Ritual":             [],  # Omens (Omen of Whittling, etc.)
    # "Expedition":         [],  # Logbooks / artifacts
    # "Verisium":           [],  # Verisium material
}

# ── Exchange item descriptions ─────────────────────────────────────────────────
# Maps trade_slug → human-readable description for items NOT already in CURRENCIES.
# Items from _by_cat() (Runes, Essences, SoulCores, Fragments) inherit their
# effect strings from CURRENCIES; only list extras here.
EXCHANGE_DESCRIPTIONS: dict[str, str] = {

    # ── Breach Splinters & Stones ──────────────────────────────────────────
    "breach-splinter":   "Combine 100 Breach Splinters to create a Breachstone",
    "breachstone":       "Opens a portal to a Breach domain map containing a Breachlord encounter",

    # ── Wombgifts (Breach domain keys, PoE2 Breachstone equivalents) ───────
    "banded-wombgift":       "Opens a portal to a Banded Breach domain (lowest tier)",
    "ornate-wombgift":       "Opens a portal to an Ornate Breach domain",
    "signet-wombgift":       "Opens a portal to a Signet Breach domain",
    "lavish-wombgift":       "Opens a portal to a Lavish Breach domain",
    "revelatory-wombgift":   "Opens a portal to a Revelatory Breach domain (highest tier)",

    # ── Catalysts (add quality to rings/amulets, quality improves specific mods) ─
    "adaptive-catalyst":     "Adds quality to a ring or amulet; quality improves all modifier types",
    "carapace-catalyst":     "Adds quality to a ring or amulet; quality improves armour, evasion, and energy shield modifiers",
    "chayulas-catalyst":     "Adds quality to a ring or amulet; quality improves chaos damage modifiers",
    "eshs-catalyst":         "Adds quality to a ring or amulet; quality improves lightning damage modifiers",
    "flesh-catalyst":        "Adds quality to a ring or amulet; quality improves life and flask modifiers",
    "necrotic-catalyst":     "Adds quality to a ring or amulet; quality improves minion modifiers",
    "neural-catalyst":       "Adds quality to a ring or amulet; quality improves mana modifiers",
    "reaver-catalyst":       "Adds quality to a ring or amulet; quality improves physical and attack modifiers",
    "sibilant-catalyst":     "Adds quality to a ring or amulet; quality improves cold and chaos modifiers",
    "skittering-catalyst":   "Adds quality to a ring or amulet; quality improves dexterity and movement modifiers",
    "tuls-catalyst":         "Adds quality to a ring or amulet; quality improves cold damage modifiers",
    "uul-netols-catalyst":   "Adds quality to a ring or amulet; quality improves physical damage modifiers",
    "xophs-catalyst":        "Adds quality to a ring or amulet; quality improves fire damage modifiers",

    # ── Refined Catalysts (add quality to jewels) ──────────────────────────
    "refined-adaptive-catalyst":    "Adds quality to a jewel; quality improves all modifier types",
    "refined-carapace-catalyst":    "Adds quality to a jewel; quality improves armour, evasion, and energy shield modifiers",
    "refined-chayulas-catalyst":    "Adds quality to a jewel; quality improves chaos damage modifiers",
    "refined-eshs-catalyst":        "Adds quality to a jewel; quality improves lightning damage modifiers",
    "refined-flesh-catalyst":       "Adds quality to a jewel; quality improves life and flask modifiers",
    "refined-necrotic-catalyst":    "Adds quality to a jewel; quality improves minion modifiers",
    "refined-neural-catalyst":      "Adds quality to a jewel; quality improves mana modifiers",
    "refined-reaver-catalyst":      "Adds quality to a jewel; quality improves physical and attack modifiers",
    "refined-sibilant-catalyst":    "Adds quality to a jewel; quality improves cold and chaos modifiers",
    "refined-skittering-catalyst":  "Adds quality to a jewel; quality improves dexterity and movement modifiers",
    "refined-tuls-catalyst":        "Adds quality to a jewel; quality improves cold damage modifiers",
    "refined-uul-netols-catalyst":  "Adds quality to a jewel; quality improves physical damage modifiers",
    "refined-xophs-catalyst":       "Adds quality to a jewel; quality improves fire damage modifiers",

    # ── Liquid Emotions (Delirium currency — apply Delirium to maps) ────────
    # Ancient prefix variants enchant Time-Lost Jewels (atlas passive jewel slots).
    "diluted-liquid-greed":      "Applies a weak Greed (more items) Delirium effect to a map",
    "diluted-liquid-guilt":      "Applies a weak Guilt (more currency) Delirium effect to a map",
    "diluted-liquid-ire":        "Applies a weak Ire (more monsters) Delirium effect to a map",
    "liquid-despair":            "Applies a Despair Delirium effect to a map",
    "liquid-disgust":            "Applies a Disgust Delirium effect to a map",
    "liquid-envy":               "Applies an Envy (more rare monsters) Delirium effect to a map",
    "liquid-paranoia":           "Applies a Paranoia Delirium effect to a map",
    "concentrated-liquid-fear":      "Applies a potent Fear Delirium effect to a map",
    "concentrated-liquid-isolation": "Applies a potent Isolation Delirium effect to a map",
    "concentrated-liquid-suffering": "Applies a potent Suffering Delirium effect to a map",
    "potent-liquid-contempt":        "Applies a powerful Contempt Delirium effect to a map",
    "potent-liquid-ferocity":        "Applies a powerful Ferocity (stronger monsters) Delirium effect to a map",
    "potent-liquid-melancholy":      "Applies a powerful Melancholy Delirium effect to a map",
    # Ancient variants → enchant Time-Lost Jewels
    "ancient-diluted-liquid-greed":          "Enchants a Time-Lost Jewel with a weak Greed Delirium effect",
    "ancient-diluted-liquid-guilt":          "Enchants a Time-Lost Jewel with a weak Guilt Delirium effect",
    "ancient-diluted-liquid-ire":            "Enchants a Time-Lost Jewel with a weak Ire Delirium effect",
    "ancient-liquid-despair":                "Enchants a Time-Lost Jewel with a Despair Delirium effect",
    "ancient-liquid-disgust":                "Enchants a Time-Lost Jewel with a Disgust Delirium effect",
    "ancient-liquid-envy":                   "Enchants a Time-Lost Jewel with an Envy Delirium effect",
    "ancient-liquid-paranoia":               "Enchants a Time-Lost Jewel with a Paranoia Delirium effect",
    "ancient-concentrated-liquid-fear":      "Enchants a Time-Lost Jewel with a potent Fear Delirium effect",
    "ancient-concentrated-liquid-isolation": "Enchants a Time-Lost Jewel with a potent Isolation Delirium effect",
    "ancient-concentrated-liquid-suffering": "Enchants a Time-Lost Jewel with a potent Suffering Delirium effect",
    "ancient-potent-liquid-contempt":        "Enchants a Time-Lost Jewel with a powerful Contempt Delirium effect",
    "ancient-potent-liquid-ferocity":        "Enchants a Time-Lost Jewel with a powerful Ferocity Delirium effect",
    "ancient-potent-liquid-melancholy":      "Enchants a Time-Lost Jewel with a powerful Melancholy Delirium effect",

    # ── Abyss Bones (socket into items to add Abyss mods via desecration) ──
    # Gnawed < Ancient < Preserved quality tiers; Altered = special variant
    "gnawed-rib":          "Socket into armour to add an Abyss (bone) modifier (lowest tier rib)",
    "ancient-rib":         "Socket into armour to add an Abyss modifier (mid tier rib)",
    "preserved-rib":       "Socket into armour to add an Abyss modifier (highest tier rib)",
    "gnawed-jawbone":      "Socket into a weapon or quiver to add an Abyss modifier (lowest tier)",
    "ancient-jawbone":     "Socket into a weapon or quiver to add an Abyss modifier (mid tier)",
    "preserved-jawbone":   "Socket into a weapon or quiver to add an Abyss modifier (highest tier)",
    "gnawed-collarbone":   "Socket into an amulet, ring, or belt to add an Abyss modifier (lowest tier)",
    "ancient-collarbone":  "Socket into an amulet, ring, or belt to add an Abyss modifier (mid tier)",
    "altered-collarbone":  "Socket into an amulet, ring, or belt to add a special Abyss modifier (altered variant)",
    "preserved-collarbone":"Socket into an amulet, ring, or belt to add an Abyss modifier (highest tier)",
    "preserved-cranium":   "Socket into a helmet to add an Abyss modifier (highest tier cranium)",
    "preserved-vertebrae": "Socket into a body armour to add an Abyss modifier (highest tier vertebrae)",
    # Unique Abyss Gaze jewels
    "amanamus-gaze":  "Unique Abyss jewel: Amanamu's Gaze — grants special Abyss-themed bonuses",
    "kurgals-gaze":   "Unique Abyss jewel: Kurgal's Gaze — grants special Abyss-themed bonuses",
    "tecrods-gaze":   "Unique Abyss jewel: Tecrod's Gaze — grants special Abyss-themed bonuses",
    "ulamans-gaze":   "Unique Abyss jewel: Ulaman's Gaze — grants special Abyss-themed bonuses",

    # ── Uncut Gems ──────────────────────────────────────────────────────────
    **{f"uncut-skill-gem-level-{lvl}":   f"Cut to create a level {lvl} active skill gem of your choice"
       for lvl in range(14, 21)},
    **{f"uncut-spirit-gem-level-{lvl}":  f"Cut to create a level {lvl} spirit (trigger/reserve) gem of your choice"
       for lvl in range(14, 21)},
}


def _slug_to_description(slug: str) -> str | None:
    """Look up description for any exchange item slug.

    Checks EXCHANGE_DESCRIPTIONS first, then falls back to CURRENCIES effect field.
    """
    if slug in EXCHANGE_DESCRIPTIONS:
        return EXCHANGE_DESCRIPTIONS[slug]
    # Fall back to CURRENCIES for Runes, Essences, SoulCores, Fragments
    for entry in CURRENCIES:
        if entry[4] == slug:
            return entry[3]
    return None


def search_exchange_items(keyword: str = "", limit: int = 20) -> list[dict]:
    """Search all exchange items by keyword.

    Returns dicts with keys: name, slug, item_type, category, description.
    """
    kw = keyword.lower().strip()
    results: list[dict] = []
    seen: set[str] = set()

    for item_type, items in EXCHANGE_SLUGS.items():
        cat = EXCHANGE_CATEGORIES.get(item_type, item_type.lower())
        for name, slug in items:
            if slug in seen:
                continue
            desc = _slug_to_description(slug) or ""
            if kw:
                if kw not in name.lower() and kw not in desc.lower() and kw not in cat.lower():
                    continue
            results.append({
                "name": name,
                "slug": slug,
                "item_type": item_type,
                "category": cat,
                "description": desc,
            })
            seen.add(slug)
            if len(results) >= limit:
                return results

    return results


# Internal category names for each poe.ninja type (mirrors economy._ITEM_TYPE_TO_CATEGORY)
EXCHANGE_CATEGORIES: dict[str, str] = {
    "Runes":             "rune",
    "Essences":          "essence",
    "SoulCores":         "soul_core",
    "Breach":            "catalyst",
    "Delirium":          "liquid_emotion",
    "Fragments":         "fragment",
    "UncutGems":         "uncut_gem",
    "LineageSupportGems": "lineage_gem",
    "Abyss":             "abyss",
    "Idols":             "idol",
    "Ritual":            "omen",
    "Expedition":        "expedition",
    "Verisium":          "verisium",
}
