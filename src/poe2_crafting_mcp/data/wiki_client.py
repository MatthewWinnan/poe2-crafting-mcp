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
import time
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

    def _get(self, params: dict, _retries: int = 3) -> dict:
        url = WIKI_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        for attempt in range(_retries):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < _retries - 1:
                    wait = 10 * (attempt + 1)  # 10s, 20s
                    log.warning('rate limited (429), waiting %ds…', wait)
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError('unreachable')

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
                    'redirects': '1',
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

    def _parse_status_infobox(self, wikitext: str) -> tuple[str, str]:
        """Extract category and description from {{status}} infobox (ailments/buffs).

        Returns (category, description) or ("", "") if not a status page.
        """
        start = wikitext.lower().find('{{status')
        if start == -1:
            return "", ""
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
            return "", ""

        body = wikitext[start + 8:body_end]  # skip '{{status'
        fields: dict[str, str] = {}
        for line in body.split('\n'):
            line = line.strip().lstrip('|')
            if '=' in line:
                k, _, v = line.partition('=')
                fields[k.strip().lower()] = v.strip()

        # type field → concept category
        status_type = fields.get('type', '').lower()
        _STATUS_CAT = {
            'ailment': 'ailment',
            'buff': 'buff',
            'debuff': 'debuff',
            'keyword': 'keyword',
        }
        category = _STATUS_CAT.get(status_type, 'mechanic')
        description = _strip_wiki(fields.get('description', ''))
        return category, description

    def _extract_body_prose(self, wikitext: str) -> list[str]:
        """Strip all templates and markup, return body paragraphs."""
        # Preserve text from {{c|colour|text}} before general template removal
        wikitext = re.sub(r'\{\{c\|[^\|]+\|([^}]+)\}\}', r'\1', wikitext)
        # Remove all {{...}} templates (depth-aware)
        result = []
        pos = 0
        while pos < len(wikitext):
            if wikitext[pos:pos + 2] == '{{':
                depth = 1
                pos += 2
                while pos < len(wikitext) - 1 and depth > 0:
                    if wikitext[pos:pos + 2] == '{{':
                        depth += 1
                        pos += 2
                    elif wikitext[pos:pos + 2] == '}}':
                        depth -= 1
                        pos += 2
                    else:
                        pos += 1
            else:
                result.append(wikitext[pos])
                pos += 1
        clean = ''.join(result)

        # Remove wiki section headers (==Foo==)
        clean = re.sub(r'==+[^=]+=+\n?', '', clean)
        # Strip remaining wiki markup
        clean = _strip_wiki(clean)
        # Split into paragraphs
        paras = [p.strip() for p in re.split(r'\n{2,}', clean) if p.strip()]
        # Filter out very short fragments and reference-like lines
        return [p for p in paras if len(p) > 20]

    def fetch_concept(self, name: str) -> dict | None:
        """Fetch a wiki keyword/mechanic/ailment page as a concept dict.

        Handles three page types:
        - {{status}} pages (ailments: Shock, Freeze, Ignite…) — structured fields
        - {{keyword infobox}} pages (mechanics) — body prose only
        - General mechanic pages — body prose only

        Returns a concepts-table dict or None if the page doesn't exist or has
        no extractable content.
        """
        items = self._get_pages([name])
        page = next(iter(items.values()), None)
        if page is None or page.get('missing'):
            return None
        revisions = page.get('revisions', [])
        if not revisions:
            return None
        wikitext = revisions[0].get('content', '')
        if not wikitext:
            return None

        # Extract {{status}} fields for ailments/buffs
        category, status_desc = self._parse_status_infobox(wikitext)

        # Extract body prose (templates stripped)
        paras = self._extract_body_prose(wikitext)
        summary = paras[0] if paras else status_desc
        mechanics = '\n'.join(paras[1:3]) if len(paras) > 1 else ''

        # If status gave us a description but body prose is thin, use status desc
        if status_desc and (not summary or len(summary) < 30):
            summary = status_desc

        # Category fallback
        if not category:
            category = 'mechanic'

        if not summary:
            return None

        return {
            'name': name,
            'category': category,
            'summary': summary,
            'mechanics': mechanics,
            'formula': '',
            'see_also': [],
            'source': 'poe2wiki',
            'league_version': None,
        }

    def _get_pages(self, names: list[str]) -> dict:
        """Fetch raw page data for a list of names. Returns page dict keyed by title.

        Follows redirects automatically (redirects=1). Page dict is keyed by the
        ORIGINAL requested title so callers can match results back to input names.
        """
        titles = '|'.join(n.replace(' ', '_') for n in names)
        data = self._get({
            'action': 'query',
            'titles': titles,
            'prop': 'revisions',
            'rvprop': 'content',
            'redirects': '1',
            'format': 'json',
            'formatversion': '2',
        })
        query = data.get('query', {})
        pages = {p.get('title', ''): p for p in query.get('pages', [])}

        # Build reverse redirect map: resolved_title → [original_title, ...]
        # MediaWiki returns a 'redirects' list: [{from: original, to: resolved}]
        redirect_map: dict[str, str] = {}
        for redir in query.get('redirects', []):
            redirect_map[redir.get('to', '')] = redir.get('from', '')

        # Re-key pages by original requested name where possible
        result: dict[str, dict] = {}
        for title, page in pages.items():
            original = redirect_map.get(title, title)
            result[original] = page
            result[title] = page  # also keep by resolved title
        return result

    def fetch_concepts(self, names: list[str]) -> list[dict]:
        """Fetch concept data for a batch of names (batched, 50/request, with rate-limit delay).

        Pages not on the wiki or without extractable content are silently skipped.
        Returns list of concept dicts ready for upsert_concept().
        """
        results: list[dict] = []
        for batch in self._batches(names):
            try:
                pages = self._get_pages(batch)
                for name in batch:
                    # MediaWiki normalises titles (spaces→underscores), try both
                    page = pages.get(name) or pages.get(name.replace(' ', '_'))
                    if page is None:
                        # Also try by iterating values (title may differ in case)
                        page = next(
                            (p for p in pages.values()
                             if p.get('title', '').replace('_', ' ').lower() == name.lower()),
                            None,
                        )
                    if page is None or page.get('missing'):
                        continue
                    revisions = page.get('revisions', [])
                    if not revisions:
                        continue
                    wikitext = revisions[0].get('content', '')
                    if not wikitext:
                        continue
                    category, status_desc = self._parse_status_infobox(wikitext)
                    paras = self._extract_body_prose(wikitext)
                    summary = paras[0] if paras else status_desc
                    mechanics = '\n'.join(paras[1:3]) if len(paras) > 1 else ''
                    if status_desc and (not summary or len(summary) < 30):
                        summary = status_desc
                    if not category:
                        category = 'mechanic'
                    if not summary:
                        continue
                    # Use the wiki page title as name (may differ by capitalisation)
                    results.append({
                        'name': name,  # keep the DB name, not wiki title
                        'category': category,
                        'summary': summary,
                        'mechanics': mechanics,
                        'formula': '',
                        'see_also': [],
                        'source': 'poe2wiki',
                        'league_version': None,
                    })
            except Exception as exc:
                log.warning('concept batch error (starting %s): %s', batch[0], exc)
            time.sleep(1.5)  # be polite to the wiki
        return results

    def seed_concepts_from_db(self, pdb) -> tuple[int, int]:
        """Bulk-seed concepts table from wiki using names already in the concepts DB.

        Fetches all concept names in batches, upserts those found on the wiki.
        Concepts not found on the wiki are left unchanged.

        Returns:
            (fetched, skipped) counts
        """
        rows = pdb.search_concepts(keyword='', limit=10000)
        names = [r['name'] for r in rows]
        log.info('concept seed: %d names to look up', len(names))

        concepts = self.fetch_concepts(names)
        for concept in concepts:
            pdb.upsert_concept(**concept)
        fetched = len(concepts)
        skipped = len(names) - fetched
        return fetched, skipped

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
