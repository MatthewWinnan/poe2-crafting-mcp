# Research Index — Sources Consulted

Track what we've fetched to avoid duplicate research.

## Fetched Successfully (July 2026)

| Source | URL | Date | Key Data Extracted |
|--------|-----|------|--------------------|
| Maxroll | maxroll.gg/poe2/resources/reforging-bench-guide | 2026-07-27 | Reforging bench: same base+rarity required, lowest ilvl output, all recipes (gear/waystone/rune/essence/catalyst/soul core/distilled emotion/relic), no corrupted items |
| Timesaver | timesaver.gg/blog/poe2-omens-guide | 2026-07-27 | Complete omen list (25+): Whittling, Greater/Sinistral/Dextral Exaltation, Crystallisation, Erasure, Annulment, Coronation, Alchemy, Blessed, Corruption, Chance, Ancients, Homogenising, Amelioration, Resurgence, Refreshment, Waystone omens (4), Desecration omens (3: Ulaman/Amanamu/Kurgal), Expedition Sagas (5) |
| Timesaver | timesaver.gg/blog/poe2-essence-guide | 2026-07-27 | Essence tiers (Lesser/Normal/Greater/Perfect), Greater = Magic→Rare with guaranteed mod, Perfect = remove-1-add-1 on Rare, one essence mod per item (0.5.0+), no complete essence→mod mapping table |
| Fextralife | pathofexile2.wiki.fextralife.com/Essences | 2026-07-27 | Confirmed Perfect Essence mechanics, partial essence list |
| Fextralife | pathofexile2.wiki.fextralife.com/Omen+of+Greater+Exaltation | 2026-07-27 | Greater Exaltation adds 2 mods, stacks with sinistral/dextral AND greater/perfect exalt tiers |
| PoECurrency | poecurrency.com (0.5.0 crafting meta) | 2026-07-27 | Crystallisation omen specifics, slot-forcing mechanic (full suffix → essence forced to remove suffix) |
| Game8 | game8.co/games/Path-of-Exile-2/archives/490017 | 2026-07-27 | Reforging bench unlock (Act 3 Drowned City), recipe list |
| Fextralife | pathofexile2.wiki.fextralife.com/Reforging+Bench | 2026-07-27 | (via search snippet) Basic reforging rules |

## Blocked / 403 (could not fetch full content)

| Source | URL | Notes |
|--------|-----|-------|
| Mobalytics | mobalytics.gg/poe-2/guides/ssf-crafting | Got search snippets only. SSF crafting flow: transmute→aug→essence→exalt→desecrate. Reforging 3-to-1 for recycling. Alchemy for bad transmute results. |
| Mobalytics | mobalytics.gg/poe-2/guides/vaal-corrupting | Got search snippets only. Vaal outcomes already documented in docs/crafting-guide-corruption.md |
| Mobalytics | mobalytics.gg/poe-2/guides/paintmasters-essence-farm | 403 error. Essence farming guide. |
| Mobalytics | mobalytics.gg/poe-2/guides/omen-crafting | Not fetched. Omen crafting guide. |
| Mobalytics | mobalytics.gg/poe-2/guides/essences | Not fetched. Essence guide. |
| Mobalytics | mobalytics.gg/poe-2/guides/0-3-essence-update | Not fetched. Patch 0.3 essence changes. |

## Search Results Only (snippets, not full pages)

| Query | Key findings from snippets |
|-------|---------------------------|
| "PoE2 reforging bench mechanics" | Same base type, same rarity, lowest ilvl, no corrupted |
| "PoE2 perfect essence mechanics" | Remove 1 random mod + add 1 guaranteed, crystallisation omen control |
| "PoE2 omen of greater exaltation" | Adds 2 mods, stacks with targeting omens, bug report on perfect exalt interaction |
| "PoE2 omen crystallisation whittling" | Whittling = remove lowest item level mod (deterministic), Crystallisation = control prefix/suffix removal on essence |

## Previously Scraped (earlier sessions, already in docs/)

| Source | File | Content |
|--------|------|---------|
| Mobalytics (paraphrased) | docs/crafting-guide-methods.md | Currency flow, Greater/Perfect tiers, corruption overview, strategy summary |
| Mobalytics (paraphrased) | docs/crafting-guide-modifiers.md | Prefix/suffix, tiers, local/global, hybrid mods, tags, rune sockets |
| Mobalytics (paraphrased) | docs/crafting-guide-corruption.md | Full Vaal Orb outcomes by item type, Omen of Corruption, strategy |
| Mobalytics (paraphrased) | docs/crafting-guide-defences.md | Defence layers, attribute→defence mapping, slot priorities |
| poe2wiki.net (API) | wiki_client.py cache | 974 item descriptions, 124 concepts, all via MediaWiki API |
| poe2db.tw (scraper) | mod_weights table | Real spawn weights for all mod pools (normal/essence/desecrated/influence) |

## Not Yet Researched (identified gaps)

| Gap | Potential Sources | Priority |
|-----|-------------------|----------|
| Essence→mod mapping table (which essence gives what on which slot) | poe2wiki.net API (individual essence pages), poe2db.tw | CRITICAL — blocks essence seeds |
| Omen stacking rules (which omens can combine) | poe2db.tw, community testing, pathofexile.com forums | HIGH — blocks double exalt seed |
| Fracture + essence interaction | Community guides, Reddit, pathofexile.com forums | HIGH — blocks seed 8 with essence |
| Flux orb exact mechanics | poe2wiki.net, poe2db.tw | MEDIUM |
| Chaos orb mod count behavior | Community testing | LOW — assumed count-neutral |
| Alchemy exact mod count (always 4?) | Game testing, wiki | LOW — assumed 4 |
| Bench craft mod list per slot | PoB data (already in DB as crafted. prefix) | LOW — terminal action |
| Omen prices on trade | poe.ninja / trade API at runtime | Deferred to PriceCache pre-flight |
