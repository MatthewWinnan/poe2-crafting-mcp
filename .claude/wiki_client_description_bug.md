# Wiki Client: Item Description Fallback Bug

## Problem Statement

When `item-desc-seed` runs, items like **Breach Tablet** that have no `description`
or `augment_stat_text` in their `{{Item}}` wiki template end up with the wrong
description in the DB — currently "Breach Tablet is a precursor tablet base type."

**Desired behaviour** (priority order):
1. `augment_stat_text` / `description` from `{{Item}}` template — already works for most currencies
2. `==Mechanics==` section from the page body — e.g. for Breach Tablet:
   > Using multiple Breach Tablets will add additional Unstable Breaches to the map.
   >
   > This will not add additional Unstable Breaches to Breach Hives... [Likely due to a bug]
3. First prose paragraph as last resort ("Breach Tablet is a precursor tablet base type.")

**Future nice-to-have**: resolve `implicit1 = TowerAddBreachToMapsImplicit` to the
actual modifier text ("Adds an Otherworldy Breach to a Map / 10 uses remaining") —
would need a separate wiki page fetch per implicit ID.

---

## What Was Done This Session

### Fix 1 — External link stripping (`_strip_wiki`) — COMMITTED (69b07c8)

The `drop_text` field on some wiki pages contained `[https://poe2db.tw/... display text]`
external links. The display text was a raw poe2db item transcription (item name, class,
implicit text, help text concatenated), which leaked into `drop_notes`.

Fix added to `_strip_wiki()`:
```python
# [https://... display text] or [https://...] — strip entirely
text = re.sub(r'\[https?://[^\]]*\]', '', text, flags=re.DOTALL)
```

### Fix 2 — `_extract_section` + `{{bug}}` + generic template stripping — NOT COMMITTED

Added to `_strip_wiki()`:
```python
text = re.sub(r'\{\{bug\}\}', '[Likely due to a bug]', text, flags=re.IGNORECASE)
text = re.sub(r'\{\{[^{}]*\}\}', '', text)   # strip remaining single-level templates
```

Added `_extract_section(wikitext, section)` helper — finds `==section==`, extracts
lines until the next `==` heading, strips markup.

Updated `fetch_items()` fallback:
```python
if not item['description']:
    item['description'] = (
        _extract_section(wikitext, 'Mechanics')
        or _first_prose(wikitext)
    )
```

**Verified correct** when calling `fetch_item("Breach Tablet")` directly:
```
description: 'Using multiple Breach Tablets will add additional Unstable Breaches to
the map.\n\nThis will not add additional Unstable Breaches to Breach Hives... [Likely due to a bug]'
```

**Also verified correct** in a small batch (`fetch_items(["Orb of Transmutation", "Breach Tablet", "Divine Orb"])`):
```
Breach Tablet → 'Using multiple Breach Tablets will add additional Unstable Breaches...'
```

---

## The Unresolved Bug

Despite the fix working in isolation, after running `item-desc-seed` (1059 items, ~40
batches of 50), the DB still shows the OLD description with an OLD timestamp:

```
description: 'Breach Tablet is a precursor tablet base type.'
updated_at:  2026-07-26T20:57:53.411576+00:00   <- from a previous manual upsert
```

The timestamp did NOT update, meaning the seed is not writing the Breach Tablet row at
all during the full run, even though it reports "Seeded 1059 items".

**Hypothesis**: An exception is thrown somewhere in the batch containing Breach Tablet
and silently swallowed by the broad `except Exception` in `fetch_items`. The small
batch test worked because no error occurred. Something about Breach Tablet in a 50-item
batch triggers a failure (encoding, template parse, API response shape, or name collision).

---

## Next Session: Debugging Steps

1. Add temporary logging in the `except` block to surface the actual error:
   ```python
   except Exception as exc:
       import traceback; traceback.print_exc()
       log.warning('wiki fetch error (batch starting %s): %s', batch[0], exc)
   ```
2. Run `item-desc-seed` and observe which batch fails and why.
3. Also verify: does `{{bug}}` + generic template stripping break any items that use
   `{{c|colour|text}}`? Check a few coloured-text currencies still render correctly.
4. Check `_parse_template` — it uses a simple line-by-line `k=v` parser. Multi-line
   field values in a batch response might be parsed differently than in a single-item
   response (possible source of the discrepancy).
