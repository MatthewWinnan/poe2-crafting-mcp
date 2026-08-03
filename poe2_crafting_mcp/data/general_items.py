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

    # ── Fragments (Breach splinters, Simulacrum splinter, Boss invitation) ──────
    # _by_cat("Fragment") covers: breach splinters, simulacrum splinter, simulacrum, kulemak's invitation
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

    # ── Lineage Support Gems (poe.ninja type = "LineageSupportGems") ─────────
    "LineageSupportGems": _by_cat("LineageGem"),

    # ── Idols (Atlas tower socketables, poe.ninja type = "Idols") ────────────
    "Idols": _by_cat("Idol"),

    # ── Omens (crafting consumables, poe.ninja type = "Ritual") ──────────────
    "Ritual": _by_cat("Omen"),

    # ── Expedition Artifacts (poe.ninja type = "Expedition") ─────────────────
    "Expedition": _by_cat("Expedition"),

    # ── Verisium crafting materials (poe.ninja type = "Verisium") ────────────
    "Verisium": _by_cat("Verisium"),
}

# ── Exchange item descriptions (legacy fallback) ───────────────────────────────
# These were manually maintained descriptions before poe2wiki seeding was
# implemented. Kept only for items whose wiki page is a mechanic page rather
# than an {{Item}} page (e.g. Simulacrum is an encounter, not a currency item).
# All other items are now sourced from item_descriptions via _slug_to_description.
EXCHANGE_DESCRIPTIONS: dict[str, str] = {

    # Simulacrum: wiki page is an encounter page, not an {{Item}} page
    # The map fragment "Simulacrum (map fragment)" has a separate page
    "simulacrum": "Opens a Simulacrum encounter (crafted from 300 splinters)",
}


# slug → display name — built at import time from EXCHANGE_SLUGS
_SLUG_TO_DISPLAY = {
    slug: name
    for items in EXCHANGE_SLUGS.values()
    for name, slug in items
}


def _slug_to_description(slug: str, pdb=None) -> str | None:
    """Look up description for any exchange item slug.

    Priority:
    1. item_descriptions DB (wiki-sourced, if pdb provided)
    2. CURRENCIES effect field (for Runes, Essences, SoulCores already there)
    3. EXCHANGE_DESCRIPTIONS fallback dict (manual, legacy)
    """
    # 1. Wiki-sourced item_descriptions via display name
    if pdb is not None:
        display_name = _SLUG_TO_DISPLAY.get(slug)
        if display_name:
            d = pdb.get_item_desc(display_name)
            if d:
                desc = d.get('description', '').strip()
                if desc:
                    return desc
                notes = d.get('crafting_notes', '').strip()
                if notes:
                    return notes

    # 2. CURRENCIES effect field
    for entry in CURRENCIES:
        if entry[4] == slug:
            return entry[3]

    # 3. Legacy fallback
    if slug in EXCHANGE_DESCRIPTIONS:
        return EXCHANGE_DESCRIPTIONS[slug]

    return None


def search_exchange_items(keyword: str = "", limit: int = 20, pdb=None) -> list[dict]:
    """Search all exchange items by keyword.

    Args:
        keyword: filter term (searches name, description, category)
        limit:   max results
        pdb:     optional PriceDatabase — enables wiki-sourced descriptions
                 from item_descriptions table (preferred over manual fallback)

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
            desc = _slug_to_description(slug, pdb=pdb) or ""
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


def all_exchange_item_names() -> list[str]:
    """Return all unique display names across all exchange item categories.

    Used by item-desc-seed to bulk-fetch from poe2wiki.
    """
    seen: set[str] = set()
    names: list[str] = []
    for items in EXCHANGE_SLUGS.values():
        for name, _slug in items:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


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
