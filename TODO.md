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
- [x] Full MCP server (32 tools via FastMCP)
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

## Sprint 5: Crafting Advisor

Goal: given a base item, tell the agent what mods can roll on it, what
crafting materials are needed, and what it would cost.

- [ ] `get_craftable_mods(base, slot, tags)` — returns all mods that can roll
  on a given base with their weight, ilvl requirements, and category
- [ ] `estimate_craft_cost(base, target_mods)` — estimate currency cost to hit
  target mods (uses mod weights + currency prices)
- [ ] Crafting method guide: when to use Orb of Alteration vs Essence vs
  Rune vs explicit slam — encode as structured data, not just prose
- [ ] MCP tools: get_craftable_mods, estimate_craft_cost, get_crafting_methods

---

## Sprint 6: Build Comparison

Goal: find top ladder/community builds using the same skills and compare.

- [ ] poe.ninja ladder scraper — fetch top builds for a given skill gem
- [ ] Parse PoB share codes from ladder entries
- [ ] `compare_builds(my_build, reference_builds)` — diff gear, passives, gems
- [ ] Identify what high-end builds have that ours lacks (gear gaps)
- [ ] MCP tools: find_top_builds, compare_with_ladder

---

## Sprint 3 (deferred — part of agent wiring sprint)

- [ ] `@mcp.prompt()` — standard build optimisation workflow for agent
- [ ] `@mcp.resource("poe2://scenario-rules")` — rules for realistic scenario setup
- [ ] `@mcp.resource("poe2://crafting-guide")` — currency usage and crafting method guide

---

## Reference

- Planning docs: ~/OBSIDIAN_VAULT/PoE2 Crafting MCP Server/
- MVP plan: doc 10 - MVP Implementation Plan.md
- PoB engine docs: ./docs/pob-engine-boot.md
- Override docs: ./docs/uv2nix-overrides.md
