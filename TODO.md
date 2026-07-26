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
- [x] Full MCP server (39 tools via FastMCP)
- [x] ETL pipeline — SQLite DB with 1755 bases, 9365 mods, 966 gems, 441 uniques, 4912 nodes, 99 currencies
- [x] poe2-lookup CLI — unified search across all data types
- [x] concepts.py — 180 PoE2 keyword definitions with formulas, cross-links to PoB vars

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

## 🎯 NEXT SESSION — Start here: Sprint 5a

---

## 🎯 Sprint 5: Crafting Advisor

Goal: given a base item and budget, the agent can plan a complete crafting path —
what mods can roll, what method to use, and what it will cost.

### 5a. Craftable Mod Pool ⚠️ HIGHEST PRIORITY — blocks all crafting planning

The agent needs to know what modifiers are *eligible* on a specific base at a given ilvl.
The data exists in the DB (item_mods.weight_keys tags + req_level), just needs a tool.

- [ ] `get_craftable_mods(base_name, ilvl, slot?)` MCP tool
  - Look up base item tags from item_bases
  - Filter item_mods where weight_keys overlaps base tags AND req_level ≤ ilvl
  - Group into prefixes / suffixes, show all tiers with value ranges
  - Return mod weights (for probability calculations)
- [ ] `poe2-lookup craftable <base> [--ilvl N]` CLI command
- [ ] Include in search_bases() result: hint "call get_craftable_mods() for mod pool"

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

### 5d. Crafting Knowledge Base (MCP Resources)

Agent needs expert crafting strategy — when to use which method, what fractured bases
are worth buying, how to block mods, etc.

- [ ] `@mcp.resource("poe2://crafting-guide/methods")` — orb usage guide:
  - Alteration spam → regal: cheap, good for 1 target mod
  - Essence: guarantees one mod, fill rest with alts
  - Fracture + craft: buy fractured T1 base, fill remaining affixes
  - Bench craft: always fill last prefix/suffix with a useful bench mod
- [ ] `@mcp.resource("poe2://crafting-guide/blocking")` — mod blocking strategy
- [ ] `@mcp.resource("poe2://crafting-guide/priorities")` — per-slot mod priority tiers
  (e.g. gloves: ES > life > res > attack speed)
- [ ] `@mcp.resource("poe2://scenario-rules")` — realistic scenario setup rules (from Sprint 3 deferred)

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
