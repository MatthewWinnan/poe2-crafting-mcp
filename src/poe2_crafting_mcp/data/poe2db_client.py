"""
poe2db.tw scraper — fetch modifier spawn weights for crafting probability calculations.

The modifier data (including real spawn weights) is embedded as inline JSON in
each item class page on poe2db.tw. No API or headless browser needed — just HTTP
fetch + regex extraction + JSON parse.

URL pattern: https://poe2db.tw/us/{ItemClass}
  - Armour: Gloves_int, Body_Armours_str_dex, Helmets_dex_int, etc.
  - Weapons: One_Hand_Swords, Bows, Crossbows, Daggers, etc.
  - Jewellery: Amulets, Rings, Belts
  - Off-hand: Shields_str, Bucklers, Foci, Quivers
  - Jewels: Ruby, Emerald, Sapphire, Diamond
  - Flasks: Life_Flasks, Mana_Flasks
  - Charms: Charms

Data is inside `new ModsView({...})` — the DropChance field is the spawn weight.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from typing import Iterator

log = logging.getLogger(__name__)

POE2DB_BASE = "https://poe2db.tw/us"
_UA = "poe2-crafting-mcp/1.0 (educational/personal use)"

# ── PoB tag → poe2db URL suffix mapping ──────────────────────────────────────

_ATTR_TAG_TO_SUFFIX: dict[str, str] = {
    "int_armour": "_int",
    "str_armour": "_str",
    "dex_armour": "_dex",
    "str_dex_armour": "_str_dex",
    "str_int_armour": "_str_int",
    "dex_int_armour": "_dex_int",
    "str_dex_int_armour": "_str_dex_int",
}

_SLOT_TO_POE2DB: dict[str, str] = {
    "Gloves": "Gloves",
    "Boots": "Boots",
    "Helmet": "Helmets",
    "Body Armour": "Body_Armours",
    "Shield": "Shields",
    "Focus": "Foci",
    "Buckler": "Bucklers",
    "Bow": "Bows",
    "Crossbow": "Crossbows",
    "Claw": "Claws",
    "Dagger": "Daggers",
    "Wand": "Wands",
    "One Hand Sword": "One_Hand_Swords",
    "One Hand Axe": "One_Hand_Axes",
    "One Hand Mace": "One_Hand_Maces",
    "Sceptre": "Sceptres",
    "Spear": "Spears",
    "Flail": "Flails",
    "Staff": "Staves",
    "Two Hand Sword": "Two_Hand_Swords",
    "Two Hand Axe": "Two_Hand_Axes",
    "Two Hand Mace": "Two_Hand_Maces",
    "Quarterstaff": "Quarterstaves",  # PoB may use different name
    "Ring": "Rings",
    "Amulet": "Amulets",
    "Belt": "Belts",
    "Quiver": "Quivers",
    "Talisman": "Talismans",
    "Charm": "Charms",
    "Jewel": None,  # Jewels use gem type: Ruby, Emerald, Sapphire, Diamond
    "Flask": None,  # Life_Flasks, Mana_Flasks
}

# Complete list of all item classes on poe2db (for full seed)
ALL_ITEM_CLASSES: list[str] = [
    # Weapons
    "Claws", "Daggers", "Wands", "One_Hand_Swords", "One_Hand_Axes",
    "One_Hand_Maces", "Sceptres", "Spears", "Flails",
    "Bows", "Staves", "Two_Hand_Swords", "Two_Hand_Axes",
    "Two_Hand_Maces", "Quarterstaves", "Crossbows", "Traps", "Talismans",
    # Jewellery
    "Amulets", "Rings", "Belts",
    # Gloves
    "Gloves_str", "Gloves_dex", "Gloves_int",
    "Gloves_str_dex", "Gloves_str_int", "Gloves_dex_int",
    # Boots
    "Boots_str", "Boots_dex", "Boots_int",
    "Boots_str_dex", "Boots_str_int", "Boots_dex_int",
    # Body Armours
    "Body_Armours_str", "Body_Armours_dex", "Body_Armours_int",
    "Body_Armours_str_dex", "Body_Armours_str_int", "Body_Armours_dex_int",
    "Body_Armours_str_dex_int",
    # Helmets
    "Helmets_str", "Helmets_dex", "Helmets_int",
    "Helmets_str_dex", "Helmets_str_int", "Helmets_dex_int",
    # Off-hand
    "Quivers", "Shields_str", "Shields_str_dex", "Shields_str_int",
    "Bucklers", "Foci",
    # Jewels
    "Ruby", "Emerald", "Sapphire", "Diamond",
    "Time-Lost_Ruby", "Time-Lost_Emerald", "Time-Lost_Sapphire", "Time-Lost_Diamond",
    # Flasks
    "Life_Flasks", "Mana_Flasks",
    # Charms
    "Charms",
]


def base_tags_to_item_class(slot: str, tags: list[str]) -> str | None:
    """Convert PoB base item slot + tags to poe2db item class slug.

    Args:
        slot: PoB slot name (e.g. "Gloves", "Body Armour", "Ring")
        tags: PoB base tags list (e.g. ['default', 'armour', 'int_armour', 'gloves'])

    Returns:
        poe2db item class slug (e.g. "Gloves_int", "Amulets") or None if unmapped.
    """
    base_slug = _SLOT_TO_POE2DB.get(slot)
    if base_slug is None:
        return None

    # Find the attribute tag
    attr_suffix = ""
    for tag in tags:
        if tag in _ATTR_TAG_TO_SUFFIX:
            attr_suffix = _ATTR_TAG_TO_SUFFIX[tag]
            break

    return base_slug + attr_suffix


def _strip_html_tags(text: str) -> str:
    """Strip HTML tags from stat text, preserving content."""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize dashes
    text = text.replace('—', '-').replace('&ndash;', '-')
    # Collapse whitespace
    return ' '.join(text.split()).strip()


class Poe2DbClient:
    """Scrape modifier spawn weights from poe2db.tw item class pages."""

    def __init__(self) -> None:
        self._session_start = time.time()
        self._request_count = 0

    def _get_html(self, item_class: str, _retries: int = 5) -> str:
        """Fetch raw HTML for an item class page."""
        url = f"{POE2DB_BASE}/{item_class}"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        for attempt in range(_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self._request_count += 1
                    return resp.read().decode('utf-8')
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < _retries - 1:
                    wait = 30 * (attempt + 1)
                    log.warning('rate limited (429) on %s, waiting %ds…',
                                item_class, wait)
                    time.sleep(wait)
                elif e.code >= 500 and attempt < _retries - 1:
                    wait = 15 * (attempt + 1)
                    log.warning('server error (%d) on %s, retrying in %ds…',
                                e.code, item_class, wait)
                    time.sleep(wait)
                else:
                    raise
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < _retries - 1:
                    wait = 15 * (attempt + 1)
                    log.warning('connection error on %s (%s), retrying in %ds…',
                                item_class, e, wait)
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError('unreachable')

    def _extract_mods_json(self, html: str) -> dict | None:
        """Extract the ModsView JSON data from page HTML.

        The data is in: new ModsView({...})
        It's a single massive JSON object passed to the constructor.
        """
        match = re.search(r'new\s+ModsView\((\{.*?\})\);\s*$', html, re.MULTILINE | re.DOTALL)
        if not match:
            # Try without the trailing semicolon/newline
            match = re.search(r'new\s+ModsView\((\{.+)\);\s*<', html, re.DOTALL)
        if not match:
            return None

        raw = match.group(1)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning('JSON parse failed: %s (first 200 chars: %s)', e, raw[:200])
            return None

    def _parse_mod_entry(self, entry: dict, pool: str) -> dict | None:
        """Parse a single mod entry from the ModsView data.

        Returns a normalized dict or None if the entry should be skipped.
        """
        drop_chance = entry.get('DropChance')

        # Convert DropChance to int (it may be a string or int)
        if drop_chance is None:
            return None
        try:
            weight = int(drop_chance)
        except (ValueError, TypeError):
            try:
                weight = int(float(drop_chance))
            except (ValueError, TypeError):
                return None

        # For the "normal" pool, skip 0-weight mods (not rollable).
        # For special pools (essence, desecrated, corrupted, etc.), keep
        # 0-weight entries — they represent guaranteed/selectable mods.
        if weight <= 0 and pool == "normal":
            return None

        # Determine prefix/suffix from ModGenerationTypeID
        gen_type = entry.get('ModGenerationTypeID', '')
        if str(gen_type) == '1':
            affix_type = 'prefix'
        elif str(gen_type) == '2':
            affix_type = 'suffix'
        else:
            affix_type = 'unknown'

        # Extract mod family
        families = entry.get('ModFamilyList', [])
        mod_family = families[0] if families else ''

        # Build a mod identifier: Code if available, else Name+Level+Family
        code = entry.get('Code') or ''
        name = entry.get('Name', '')
        level = entry.get('Level', '0')
        if code:
            mod_id = code
        else:
            mod_id = f"{name}@{level}@{mod_family}"

        # Clean stat text
        stat_html = entry.get('str', '')
        stat_text = _strip_html_tags(stat_html)

        # Required level — 'Level' is the ilvl required to roll this tier
        req_level = 0
        lvl_raw = entry.get('Level')
        if lvl_raw:
            try:
                req_level = int(lvl_raw)
            except (ValueError, TypeError):
                pass

        # Tags from the fossil_no field (crafting tag categories)
        tags = entry.get('fossil_no', [])

        return {
            'mod_code': mod_id,
            'pool': pool,
            'affix_type': affix_type,
            'mod_family': mod_family,
            'stat_text': stat_text,
            'weight': weight,
            'req_level': req_level,
            'tags': tags,
            'name': name,
        }

    def fetch_item_class(self, item_class: str) -> list[dict]:
        """Fetch all mods with weights for a given item class.

        Returns a list of mod dicts ready for DB insertion:
        [{item_class, pool, mod_code, affix_type, mod_family, stat_text,
          weight, req_level, tags, name}]
        """
        log.info('Fetching mod weights for %s…', item_class)
        html = self._get_html(item_class)
        data = self._extract_mods_json(html)
        if data is None:
            log.warning('No ModsView data found for %s', item_class)
            return []

        results: list[dict] = []

        # The "config" dict lists all available pools
        config = data.get('config', {})
        pools_to_scrape = list(config.keys())

        for pool in pools_to_scrape:
            entries = data.get(pool)
            if not entries or not isinstance(entries, list):
                continue
            for entry in entries:
                parsed = self._parse_mod_entry(entry, pool)
                if parsed:
                    parsed['item_class'] = item_class
                    results.append(parsed)

        log.info('  %s: %d mods across %d pools', item_class, len(results),
                 len(set(r['pool'] for r in results)))
        return results

    def fetch_all(self, classes: list[str] | None = None,
                  delay: float = 3.0) -> list[dict]:
        """Fetch mod weights for all (or specified) item classes.

        Args:
            classes: list of item class slugs, or None for ALL_ITEM_CLASSES
            delay: seconds between requests (be polite)

        Returns:
            Combined list of all mod dicts.
        """
        targets = classes or ALL_ITEM_CLASSES
        all_mods: list[dict] = []

        for i, item_class in enumerate(targets):
            if i > 0:
                time.sleep(delay)
            try:
                mods = self.fetch_item_class(item_class)
                all_mods.extend(mods)
            except Exception as exc:
                log.warning('Failed to fetch %s: %s', item_class, exc)

        log.info('Total: %d mods from %d item classes (%d requests)',
                 len(all_mods), len(targets), self._request_count)
        return all_mods
