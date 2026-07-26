"""
poe2wiki.net MediaWiki API client.

Fetches structured item data from the official PoE2 wiki and maps it to the
item_descriptions table schema. Used for:
  - Bulk seeding on first run (poe2-lookup item-desc-seed)
  - Cache-miss auto-fetch in CLI and MCP tools
  - Per-league refresh of drop/release data

API:
    client = Poe2WikiClient()
    item = client.fetch_item("Celestial Alloy")
    # → {name, category, description, crafting_notes, drop_notes,
    #    see_also, source, league_version}

    items = client.fetch_items(["Orb of Transmutation", "Divine Orb", ...])
    # Missing pages silently skipped.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Iterator

log = logging.getLogger(__name__)

WIKI_API = "https://www.poe2wiki.net/api.php"
_UA = "poe2-crafting-mcp/1.0 (educational/personal use)"
_BATCH = 50  # MediaWiki max titles per request

# {{Item}} class_id → item_descriptions.category
_CLASS_TO_CAT: dict[str, str] = {
    "StackableCurrency": "currency",
    "SoulCore": "currency",      # runes, idols, soul cores
    "ActiveSkillGems": "gem",
    "SupportSkillGems": "gem",
    "MetaSkillGems": "gem",
    # All armour/weapon/jewellery classes → "base"
}


def _strip_wiki(text: str) -> str:
    """Strip MediaWiki markup from text."""
    # [[page_title|display_text]] → display_text  (MediaWiki piped link)
    text = re.sub(r'\[\[([^\|\]]+)\|([^\]]+)\]\]', r'\2', text)
    # [[page_title]] → page_title
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # <br> → newline
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # {{c|colour|text}} → text  (coloured spans)
    text = re.sub(r'\{\{c\|[^\|]+\|([^}]+)\}\}', r'\1', text)
    # '''bold''' / ''italic''
    text = re.sub(r"'{2,3}([^']+)'{2,3}", r'\1', text)
    return text.strip()


class Poe2WikiClient:
    """Fetch item data from the poe2wiki.net MediaWiki API."""

    def _get(self, params: dict) -> dict:
        url = WIKI_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _parse_template(self, wikitext: str) -> dict | None:
        """Extract {{Item}} template key=value fields from raw wikitext.

        Uses brace-depth counting to handle nested templates inside field values
        (e.g. {{c|colour|text}} inside drop_text).
        """
        # Find start of {{Item
        start = wikitext.find('{{Item')
        if start == -1:
            return None
        # Skip past '{{' to begin depth counting from 1
        pos = start + 2
        depth = 1
        body_end = -1
        while pos < len(wikitext) - 1:
            if wikitext[pos:pos + 2] == '{{':
                depth += 1
                pos += 2
            elif wikitext[pos:pos + 2] == '}}':
                depth -= 1
                if depth == 0:
                    body_end = pos
                    break
                pos += 2
            else:
                pos += 1
        if body_end == -1:
            return None

        body = wikitext[start + len('{{Item'):body_end]
        fields: dict[str, str] = {}
        for line in body.split('\n'):
            line = line.strip().lstrip('|')
            if '=' in line:
                k, _, v = line.partition('=')
                fields[k.strip()] = v.strip()
        return fields if fields else None

    def _to_item_desc(self, page_title: str, fields: dict) -> dict:
        """Convert {{Item}} template fields to an item_descriptions row dict.

        Description mirrors in-game item text order:
          <item description>
          <augment slot effects>
          Bonded:
          <bonded modifier effects>

        Crafting notes contain the usage instruction and stack/limit properties.
        """
        name = fields.get('name') or page_title.replace('_', ' ')
        class_id = fields.get('class_id', '')
        category = _CLASS_TO_CAT.get(class_id, 'base')

        # --- Description: matches in-game item text order ---
        desc_parts: list[str] = []

        raw_desc = _strip_wiki(fields.get('description', ''))
        if raw_desc:
            desc_parts.append(raw_desc)

        aug = _strip_wiki(fields.get('augment_stat_text', ''))
        if aug:
            desc_parts.append(aug)

        bonded = _strip_wiki(fields.get('augment_stat_text_bonded', ''))
        if bonded:
            desc_parts.append('Bonded:\n' + bonded)

        description = '\n'.join(desc_parts)

        # --- Crafting notes: usage + item properties ---
        crafting_parts: list[str] = []

        stack = fields.get('stack_size', '')
        limit = fields.get('augment_limit', '')
        if stack:
            crafting_parts.append(f"Stack Size: {stack}")
        if limit:
            crafting_parts.append(f"Limited to: {limit}")

        help_text = _strip_wiki(fields.get('help_text', ''))
        if help_text:
            crafting_parts.append(help_text)

        crafting_notes = '\n'.join(crafting_parts)

        # --- Drop notes ---
        drop_parts: list[str] = []
        dl = fields.get('drop_level', '')
        dl_max = fields.get('drop_level_maximum', '')
        if dl:
            dl_str = f"Drop level: {dl}"
            if dl_max:
                dl_str += f"–{dl_max}"
            drop_parts.append(dl_str)
        raw_drop = _strip_wiki(fields.get('drop_text', ''))
        if raw_drop:
            drop_parts.append(raw_drop)
        if fields.get('is_drop_restricted', '').lower() not in ('', 'false'):
            drop_parts.append('Drop-restricted.')
        drop_notes = ' '.join(drop_parts)

        return {
            'name': name,
            'category': category,
            'description': description,
            'crafting_notes': crafting_notes,
            'drop_notes': drop_notes,
            'see_also': [],
            'source': 'poe2wiki',
            'league_version': fields.get('release_version'),
        }

    def _batches(self, names: list[str]) -> Iterator[list[str]]:
        for i in range(0, len(names), _BATCH):
            yield names[i:i + _BATCH]

    def fetch_items(self, names: list[str]) -> list[dict]:
        """Fetch structured data for a list of item names (batched, 50/request).

        Pages missing from the wiki are silently skipped.
        Returns list of item_desc dicts ready for upsert_item_desc().
        """
        results: list[dict] = []
        for batch in self._batches(names):
            titles = '|'.join(n.replace(' ', '_') for n in batch)
            try:
                data = self._get({
                    'action': 'query',
                    'titles': titles,
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'format': 'json',
                    'formatversion': '2',
                })
                for page in data.get('query', {}).get('pages', []):
                    if page.get('missing'):
                        continue
                    revisions = page.get('revisions', [])
                    if not revisions:
                        continue
                    wikitext = revisions[0].get('content', '')
                    fields = self._parse_template(wikitext)
                    if not fields:
                        log.debug('no {{Item}} on %s', page.get('title'))
                        continue
                    results.append(self._to_item_desc(page.get('title', ''), fields))
            except Exception as exc:
                log.warning('wiki fetch error (batch starting %s): %s', batch[0], exc)
        return results

    def fetch_item(self, name: str) -> dict | None:
        """Fetch a single item. Returns item_desc dict or None if not on wiki."""
        items = self.fetch_items([name])
        return items[0] if items else None

    def seed_from_db(self, pdb, db) -> tuple[int, int]:
        """Bulk-seed item_descriptions from wiki using names in the PoB DB.

        Fetches all currency names + base item names from the SQLite DB,
        queries the wiki in batches, and upserts results into item_descriptions.

        Args:
            pdb: PriceDatabase instance
            db:  PoBDatabase instance

        Returns:
            (fetched, skipped) counts
        """
        # Collect all known item names from the PoB DB
        currency_rows = db.search_currencies(limit=5000)
        base_rows = db.search_bases(limit=5000)
        names = (
            [r['name'] for r in currency_rows]
            + [r['name'] for r in base_rows]
        )
        # Deduplicate preserving order
        seen: set[str] = set()
        unique_names = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique_names.append(n)

        log.info('wiki seed: fetching %d items in batches of %d', len(unique_names), _BATCH)
        items = self.fetch_items(unique_names)
        fetched = 0
        for item in items:
            pdb.upsert_item_desc(**item)
            fetched += 1
        skipped = len(unique_names) - fetched
        return fetched, skipped
