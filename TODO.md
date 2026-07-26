# TODO: Next Steps

## ✅ COMPLETED

- [x] Generate uv.lock
- [x] Enter nix shell (nix develop works)
- [x] lupa + LuaJIT working
- [x] PoB headless boots via lupa
- [x] Load real build (960K DPS Whirling Trinity Martial Artist)
- [x] PoBEngine class with full Python API
- [x] Item swap + DPS delta comparison working
- [x] Pytest test suite for PoBEngine — 41 tests, all passing
- [x] get_combat_profile() — charges, rage, ailments, defence, damage type %, dynamic config
- [x] get_condition_sources() — decodes why each condition matters (passive names, gem names)
- [x] setup_realistic_scenario() — generic auto-config for any build (6 heuristics)
- [x] Full MCP server (43 tools via FastMCP)
- [x] ETL pipeline — SQLite DB with 1755 bases, 9365 mods, 966 gems, 441 uniques, 4912 nodes, 135 currencies
- [x] poe2-lookup CLI — unified search across all data types
- [x] concepts.py — 146 PoE2 keyword definitions with formulas, cross-links to PoB vars
- [x] Concepts DB table (SQLite, FTS5, staleness tracking, runtime upsert/delete)
- [x] MCP: search_concepts, get_concept, update_concept, refresh_concepts, get_data_status (concepts)
- [x] CLI: poe2-price concept-status/list/search/get/add/delete/refresh (to move to poe2-lookup)

---

## ✅ Sprint 4: Pricing & Economy

Goal: let the agent answer "what does this upgrade cost?" and plan efficient upgrade paths.

- [x] poe.ninja client (NinjaClient) — currencies, fragments, uniques, bases, gems
- [x] League auto-detection from poe.ninja API
- [x] Economy cache in SQLite (prices + economy_meta tables, TTL-based refresh)
- [x] PriceDatabase — upsert, search, bulk read, divine value back-fill, staleness detection
- [x] MCP tools: get_data_status, set_active_league, refresh_prices, refresh_etl,
      get_item_price, get_currency_rate, get_bulk_prices
- [x] 33 unit tests (mocked HTTP + in-memory SQLite), all passing

---

## ✅ Sprint 4b: Trade Search

Goal: search the live GGG trade2 API for items with specific mods.

- [x] TradeClient — search_trade(), estimate_trade_price(), fetch_listings()
- [x] Trade stat ID cache (refresh_trade_stats, search_trade_stats MCP tools)
- [x] Full filter support: slot/category, rarity, ilvl, corrupted, fractured, identified,
      quality, rune sockets, ar/ev/es/dps, gem level, map tier, indexed, price cap, account
- [x] Tier auto-lookup from game DB (_lookup_tier_min) — handles 2-range mods correctly
- [x] Multi-stat: extra_stats + stats_type (and/if/count/not/weight) + stats_min_count
- [x] Multiple independent stat groups (stat_groups param)
- [x] Keyword resolution in extra_stats/stat_groups — agent passes {keyword, min} not raw IDs
- [x] search_trade_stats MCP tool — pure cache lookup, no HTTP, for ID discovery
- [x] SLOT_TO_CATEGORY — complete map (spear, focus, buckler, flail, gem/map/currency subtypes)
- [x] poe2-price trade CLI with all filter flags + --stat-filter/--stat-group/--stats-type

---

## 🎯 NEXT SESSION — Start here

### Step 0 — Move concept commands from poe2-price → poe2-lookup ✅ DONE

### Sprint 5h — Wiki Concept Seeder ✅ DONE

`poe2-price` is the economy/trade CLI. `poe2-lookup` is the knowledge CLI.
Concept commands belong in poe2-lookup.

- [x] Add concept-* subcommands to poe2-lookup (status/list/search/get/add/delete/refresh)
- [x] Remove concept-* from poe2-price (keep poe2-price clean for economy/trade only)

---

## 🎯 Sprint 5: Crafting Advisor

Goal: given a base item and budget, the agent can plan a complete crafting path —
what mods can roll, what method to use, and what it will cost.

### 5a. Craftable Mod Pool ⚠️ HIGHEST PRIORITY — blocks all crafting planning

The agent needs to know what modifiers are *eligible* on a specific base at a given ilvl.
The data exists in the DB (item_mods.weight_keys tags + req_level), just needs a tool.

**Design decisions (finalised):**
- `--tag` is a leaky abstraction — users don't know PoB internal tags. Tags are resolved
  *internally* from the base name. `--tag` stays as a power-user cross-base filter only.
- `--craftable` on a base lookup is the natural bridge: resolves tags → shows eligible mods.
- Intended workflow:
  ```
  poe2-lookup "Gold Gloves"                   # base stats + slot + tags (shown) + mod count hint
  poe2-lookup "Gold Gloves" --craftable       # all mods eligible on this base, grouped by affix type
  poe2-lookup "Gold Gloves" --craftable --ilvl 80  # further filtered by item level
  poe2-price trade "energy shield" --slot gloves --tier 1 --rarity magic  # find it on trade
  ```

- [ ] `get_craftable_mods(base_name, ilvl=100, slot=None)` MCP tool
  - Look up base item tags from item_bases
  - Filter item_mods: any weight_key in base tags AND weight > 0 AND req_level ≤ ilvl
  - Group into prefixes / suffixes; show all tiers with stat ranges + weights
  - Return weights (needed for Sprint 5c probability calculations)
- [ ] `poe2-lookup "Gold Gloves" --craftable [--ilvl N]` CLI flag
  - Enhances existing base lookup: shows base stats first, then craftable mods below
- [ ] `poe2-lookup <keyword> --type mods --tag <tag>` — keep as power-user cross-base filter
- [ ] search_bases() result: add hint "N craftable mods available — use --craftable to list"

### 5a+. Trade Filter Extensions (same session as 5a)

Real GGG trade2 API filters not yet exposed in search_trade_listings:

- [ ] `--stat-id <id>` — pass a raw stat ID directly (bypass keyword resolution)
- [ ] `--affix-count-min N / --affix-count-max N` — filter by total affix count on the item
- [ ] `--stats-min-count N` — minimum number of the listed stats that must match
  (maps to `count` filter type in trade2 API — useful for "at least 2 of these 3 stats")

These let the agent do compound queries like:
```
poe2-price trade "energy shield" --slot gloves --tier 1 --rarity magic \
  --stats-min-count 2 --affix-count-min 1 --affix-count-max 4
```

### 5b. Trade Item → PoB Simulation ✅

The agent finds a real listing and simulates it directly in PoB before buying.
Closes the loop between "what's on trade" and "how much does this actually help me".

- [x] `fetch_listings()` preserve full item JSON from trade2 API
- [x] `_trade_item_to_pob_text(item_json)` — converts trade API item → PoE clipboard format
  - Handles properties, requirements, implicits, explicits, fractured, crafted, rune mods, corrupted
- [x] `search_trade_listings()` returns `item_text` + `mods` + `pob_slot` per listing
- [x] `simulate_trade_item(item_text, slot, price_amount, price_currency)` MCP tool
  - equips → measures DPS/ES/life/evasion/armour delta → unequips (restores state)
  - Returns: dps_delta_pct, es_delta, life_delta, verdict, dps_gain_per_chaos
- [x] `CATEGORY_TO_POB_SLOT` map — trade category → PoB slot name
- [x] Agent workflow: search trade → simulate top 5 listings → rank by dps_gain_per_chaos

### 5c. Crafting Cost Estimation

- [ ] `estimate_craft_cost(base_name, target_mods, ilvl, method?)` MCP tool
  - Uses mod weights from get_craftable_mods() + live currency prices
  - Estimates expected currency cost for alteration spam, essence, regal+augment paths
- [ ] Currency cost formulas encoded as structured data (not prose)

### 5f. Desecrated Mods Data Pipeline (Abyss Jewel mechanic)

All 9 PoE2 mod sources catalogued in memory/crafting_mod_sources.md.
Desecrated mods are NOT in PoB — separate scraping pipeline needed.

**Data source:** poe2db.tw HTML (no JSON API)
**URL pattern:** `poe2db.tw/us/{JewelName}` — sections per item class
**Known jewels (Breach league versions):**
- `Altered_Collarbone` → Amulet (4 mods) + Ring (16) + Belt (16) ✅ confirmed
- `Altered_Cranium` → Helmets (unconfirmed URL)
- `Altered_Vertebra` → Body Armour (unconfirmed URL)
- `Altered_Jawbone` → Weapons/Quivers (404 on Abyssal_ prefix, try Altered_)
- `Altered_Rib` → Armour (gloves/boots) (404 on Abyssal_ prefix, try Altered_)

**Implementation:**
- [ ] `Poe2DbScraper` in `poe2db_client.py` — HTML fetch + table parse per section anchor
- [ ] `desecrated_mods` table in schema.sql:
  `(jewel_name, item_class, mod_name, affix_type, stat_text, stat_min, stat_max, source_url, updated_at)`
- [ ] `price_db.py`: `upsert_desecrated_mods()`, `get_desecrated_mods(jewel_name, item_class)`
- [ ] `poe2-lookup item-desc-seed` extended to also seed desecrated mods from poe2db
- [ ] MCP: `get_desecrated_mods(jewel_type, item_slot)` tool
- [ ] CLI: `poe2-lookup desecrated --jewel "Altered Collarbone" --slot amulet`

**Also blocked on: verify URL patterns for non-Collarbone jewel types**

### 5g. Essence Mod Data Pipeline

Essences guarantee one specific mod per item class — this is NOT the standard explicit pool.
- [ ] `essence_mods` table: `(essence_name, item_class, mod_text, stat_min, stat_max)`
- [ ] Seed from wiki description text parsing (Essence of X pages have mod text inline)
- [ ] MCP: `get_essence_mods(essence_name, item_class)` tool
- [ ] `estimate_craft_cost` needs essence path: cost = essence_price + (N tries until rest fills in)

### 5h. Wiki Concept Seeder ✅ DONE

- [x] `fetch_concept(name)` in wiki_client.py — parses `{{status}}` infobox (ailments) and body prose (mechanics)
- [x] `fetch_concepts(names)` — batched version with 1.5s inter-batch delay + 429 retry
- [x] `seed_concepts_from_db(pdb)` — bulk updates all concepts from wiki (skips wiki-not-found)
- [x] `_get_pages()` now uses `redirects=1` — Lightning Damage → Lightning page, etc.
- [x] `concept-seed` CLI command (with `--dry-run`)
- [x] `_fmt_concept()` now shows source badge (`poe2wiki`/`PoB:*`)
- [x] `upsert_concepts_bulk(overwrite=False)` — refresh preserves wiki-sourced entries
- Result: 124/153 concepts now `source='poe2wiki'`; 29 remain manual (custom craft concepts, PoB tags)

### 5d. Item Descriptions + Crafting Knowledge Base ✅ DONE

**Item Descriptions pipeline** (same pattern as concepts — static seed → SQLite → updatable at runtime):
- 69 seed entries: orbs, essences, bases by slot, jewels, runes, catalysts, distilled emotions,
  fragments, focus/foci, shields, quivers, jewellery, rings, amulets, charms, idols
- `item_descriptions` table + FTS5 in schema.sql
- `item_descriptions.py` seed file
- ETL: seed item_descriptions, added to _clear_tables + _rebuild_fts
- price_db.py: upsert_item_desc, get_item_desc, search_item_descs, delete_item_desc, item_desc_status
- poe2-lookup: item-desc-status/list/get/add/delete/refresh subcommands
- MCP: get_item_description(), update_item_description(), refresh_item_descriptions()
- poe2-lookup base output: appends description block if available
- Type aliases: "foci"→descriptions, "jewellery"→descriptions, "focus"→descriptions, etc.
- Exchange dedup: items already shown in Currencies not shown again in Exchange Items
- Spurious mod filter: mods with empty stat_text (idols as Rune mods) suppressed

**Crafting Knowledge Base (MCP Resources):**

- [ ] `@mcp.resource("poe2://crafting-guide/methods")` — orb usage guide:
  - Alteration spam → regal: cheap, good for 1 target mod
  - Essence: guarantees one mod, fill rest with alts
  - Fracture + craft: buy fractured T1 base, fill remaining affixes
  - Bench craft: always fill last prefix/suffix with a useful bench mod
- [ ] `@mcp.resource("poe2://crafting-guide/blocking")` — mod blocking strategy
- [ ] `@mcp.resource("poe2://crafting-guide/priorities")` — per-slot mod priority tiers
  (e.g. gloves: ES > life > res > attack speed)
- [ ] `@mcp.resource("poe2://scenario-rules")` — realistic scenario setup rules (from Sprint 3 deferred)

### 5e. Mechanic / Tag Cross-Search

`poe2-lookup --mechanic breach` groups all breach-related items, concepts, and mods.
Requires tagging concepts + item_descriptions entries with mechanic keywords.

- [ ] Add `mechanic_tags` JSON field to both concepts and item_descriptions tables
- [ ] `poe2-lookup --mechanic <keyword>` — cross-table grouped results:
  concepts matching the mechanic + items tagged with it + mods related to it
- [ ] MCP: `search_by_mechanic(mechanic)` — returns grouped dict

---

## 🔭 Sprint 6: Build Comparison

Goal: compare our build against top ladder builds using the same primary skill —
find gear gaps, passive tree differences, and DPS ceiling.

- [ ] poe.ninja builds API client — fetch top N builds for a skill gem
  - Endpoint: poe.ninja/api/data/builds?limit=N&skill=<gem>
  - Returns PoB share codes + ladder stats (level, DPS, account)
- [ ] Parse PoB share codes from ladder entries → load into PoBEngine
- [ ] `find_top_builds(skill_name, limit=20)` MCP tool
  - Returns: [{account, level, dps, pob_code, gear_summary, passive_summary}]
- [ ] `compare_with_ladder(my_build_code, reference_builds)` MCP tool
  - Diff: passive tree (what keystones/notables they have that we don't)
  - Diff: gear (what unique items / mod tiers they run)
  - Diff: skill gems (levels, supports, links)
  - Identify top 3 "gaps" — what changes would move us closest to their numbers
- [ ] MCP tools: find_top_builds, compare_with_ladder

---

## 🔭 Sprint 7: Agent Workflow Prompts & Full Loop

Goal: wire everything into a coherent agent experience with guided prompts.

- [ ] `@mcp.prompt("optimise-build")` — full optimisation workflow:
  1. load_build + setup_realistic_scenario
  2. get_combat_profile → identify weak stats
  3. get_craftable_mods for each slot → find best upgrade target
  4. search_trade_listings → find cheapest item that improves build
  5. simulate_trade_item → confirm DPS/EHP delta before buying
  6. estimate_craft_cost → compare buy vs craft
  7. Output: ranked upgrade path with costs + expected gains
- [ ] `@mcp.prompt("craft-item")` — crafting advisor workflow:
  1. get_craftable_mods for chosen base
  2. Recommend method based on target mods + budget
  3. estimate_craft_cost for each method
  4. Output: step-by-step crafting plan
- [ ] `@mcp.prompt("ladder-check")` — build comparison workflow:
  1. find_top_builds for primary skill
  2. compare_with_ladder
  3. Output: top 3 actionable improvements with cost estimates

---

## 🔧 Backlog / Nice-to-Have

- [ ] `poe2-price item <anything>` — support all item types (runes, gems, fragments, div cards)
- [ ] CLI validation — spot-check poe2-price output against poe.ninja + Exile Exchange in browser
- [ ] Pseudo stat support in trade search (pseudo.pseudo_total_resistance etc.)
- [ ] Corrupted implicit / desecrated stat search (extra sockets, +gem levels)
- [ ] Fractured base search via fractured stat type
- [ ] `@mcp.prompt()` — standard build optimisation workflow (from Sprint 3 deferred)

---

## Reference

- Planning docs: ~/OBSIDIAN_VAULT/PoE2 Crafting MCP Server/
- MVP plan: doc 10 - MVP Implementation Plan.md
- PoB engine docs: ./docs/pob-engine-boot.md
- Override docs: ./docs/uv2nix-overrides.md
