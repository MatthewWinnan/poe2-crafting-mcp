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
- [x] Full MCP server (47+ tools via FastMCP)
- [x] ETL pipeline — SQLite DB with 1755 bases, 9365 mods, 966 gems, 443 uniques, 4912 nodes, 135 currencies
- [x] poe2-lookup CLI — unified search across all data types
- [x] concepts.py — 167 PoE2 keyword definitions with formulas, cross-links to PoB vars
- [x] Concepts DB table (SQLite, FTS5, staleness tracking, runtime upsert/delete)
- [x] MCP: search_concepts, get_concept, update_concept, refresh_concepts, get_data_status (concepts)
- [x] CLI: poe2-lookup concept-status/list/search/get/add/delete/refresh/seed
- [x] poe2-lookup status — central view of all DB health
- [x] poe2-lookup seed-all — ETL + concepts + item-desc in correct order

---

## ✅ Sprint 4: Pricing & Economy

- [x] poe.ninja client (NinjaClient) — currencies, fragments, uniques, bases, gems
- [x] League auto-detection from poe.ninja API
- [x] Economy cache in SQLite (prices + economy_meta tables, TTL-based refresh)
- [x] PriceDatabase — upsert, search, bulk read, divine value back-fill, staleness detection
- [x] MCP tools: get_data_status, set_active_league, refresh_prices, refresh_etl,
      get_item_price, get_currency_rate, get_bulk_prices
- [x] 33 unit tests (mocked HTTP + in-memory SQLite), all passing

---

## ✅ Sprint 4b: Trade Search

- [x] TradeClient — search_trade(), estimate_trade_price(), fetch_listings()
- [x] Trade stat ID cache (refresh_trade_stats, search_trade_stats MCP tools)
- [x] Full filter support: slot/category, rarity, ilvl, corrupted, fractured, etc.
- [x] Tier auto-lookup, multi-stat, stat groups
- [x] search_trade_listings MCP tool with keyword resolution
- [x] simulate_trade_item — equips trade item in PoB, measures DPS delta

---

## ✅ Sprint 5a: Craftable Mod Pools

- [x] poe2db scraper (Poe2DbClient) — extracts real spawn weights from inline HTML JSON
- [x] mod_weights table in SQLite with item_class/pool/mod_code/weight/req_level
- [x] get_craftable_mods() — returns grouped mods with correct per-tier probabilities
- [x] Each tier competes independently in the pool (confirmed via Craft of Exile)
- [x] Currency-specific min_mod_level filtering (Greater/Perfect orbs)
- [x] All pools: normal, essence, perfect_essence, desecrated, marksman, decay, etc.
- [x] CLI: mod-pool, mod-pool-seed, mod-pool-status, essence-mods, desecrated-mods, influence-mods
- [x] MCP: get_craftable_mods, get_essence_mods, get_desecrated_mods, get_influence_mods
- [x] --tiers flag, --mod filter, --currency filter, both prefix% and all% display

---

## ✅ Sprint 5c: Crafting Cost Estimation

- [x] CraftingSimulator class with ItemState tracking
- [x] get_available_pool() with dynamic exclusions (family blocking, slot limits, omen targeting)
- [x] probability_of() — exact analytical probability
- [x] estimate_cost() — expected attempts × live currency price
- [x] compare_methods() — ranks all currencies by cost-efficiency with live prices
- [x] craft-item — analyze found item mods, identify families, show crafting options
- [x] craft-sim — Monte Carlo simulation (basic, needs perf improvement)
- [x] Live economy prices wired in from poe.ninja cache
- [x] --existing-mods flag for blocked-pool calculations
- [x] MCP: estimate_craft_cost, compare_craft_methods

---

## ✅ Sprint 5d: Knowledge Base

- [x] Item descriptions pipeline (wiki-seeded, 1000+ items)
- [x] Wiki implicit resolution (Breach Tablet etc. via action=parse)
- [x] Rate-limited wiki client (5 retries, 30s backoff, 3s inter-batch)
- [x] MCP Resources: crafting-guide/methods, modifiers, corruption, defences
- [x] Full crafting state machine design doc (.claude/crafting_simulator_design.md)

---

## 🎯 Sprint 5e: Advanced Crafting Simulator

### Phase 1: Performance (Rust or Numpy)
- [ ] Rewrite Monte Carlo inner loop in Rust (via PyO3/maturin) or numpy vectorized
- [ ] Target: 10k simulations with --all in <2s (currently ~30s in pure Python)
- [ ] Expose as `craft-sim` with same CLI interface

### Phase 2: Tier Identification
- [ ] `craft-item` output shows T1/T2/T3 next to each identified mod
- [ ] Match mod value against tier ranges from the pool data
- [ ] Works for trade items and manual input

### Phase 3: Crafting Strategy Research
- [ ] Scrape/index advanced crafting guides (SSF strategies, fracture workflows)
- [ ] Document all PoE2-specific crafting paths:
  - Transmute spam → Aug → Regal → Exalt fill
  - Essence guaranteed → Annul bad mods → Exalt
  - Fracture a T1 → Chaos spam the rest
  - Omen-targeted prefix/suffix crafting
  - Desecration + annul for abyss mods
  - Genesis Tree birthing strategies
- [ ] Encode as heuristic rules for the state machine

### Phase 4: Evolutionary Crafting Optimizer
- [ ] Start N items (10,000 identical blank bases)
- [ ] Apply crafting step to all items in batch
- [ ] Evaluate: categorize by current state, prune impossible paths
- [ ] State machine decides next action per category:
  - Heuristic rules (from Phase 3) as initial guidance
  - Learns optimal paths from simulation results
- [ ] Track cost per item through the pipeline
- [ ] Output: success rate, avg cost, optimal path, cost distribution
- [ ] Compare discovered path vs known strategies
- [ ] CLI: `craft-optimize "Gold Gloves" --target "T1 ES, T1 Life, T1 Res"`
- [ ] MCP: `optimize_craft_path(base, targets, budget)`

### Phase 5: Multi-step Flowchart Recipes
- [ ] Define crafting recipes as step sequences with conditions
- [ ] "If prefix is X, proceed; else scour/annul and retry"
- [ ] Factor base cost into retry calculations
- [ ] CLI: `craft-recipe` with YAML/JSON recipe definition
- [ ] Simulate recipe and report cost distribution

---

## 🔭 Sprint 6: Build Comparison

- [ ] poe.ninja builds API client — fetch top N builds for a skill gem
- [ ] Parse PoB share codes from ladder entries → load into PoBEngine
- [ ] `find_top_builds(skill_name, limit=20)` MCP tool
- [ ] `compare_with_ladder(my_build_code, reference_builds)` MCP tool
- [ ] Identify top 3 gear/passive/gem gaps

---

## 🔭 Sprint 7: Agent Workflow Prompts

- [ ] `@mcp.prompt("optimise-build")` — full optimisation workflow
- [ ] `@mcp.prompt("craft-item")` — crafting advisor workflow
- [ ] `@mcp.prompt("ladder-check")` — build comparison workflow

---

## 🔧 Backlog

- [ ] Pseudo stat support in trade search
- [ ] CLI validation vs live sites
- [ ] Base cost tracking in craft simulations
- [ ] Mechanic/tag cross-search (poe2-lookup --mechanic breach)
- [ ] Fracturing Orb simulation (lock random mod, chaos the rest)
- [ ] MCP resources: crafting blocking strategy, per-slot mod priorities
