# TODO: Next Steps

## ✅ COMPLETED

- [x] Generate uv.lock
- [x] Enter nix shell (nix develop works)
- [x] lupa + LuaJIT working
- [x] PoB headless boots via lupa
- [x] Load real build (960K DPS Whirling Trinity Martial Artist)
- [x] PoBEngine class with full Python API
- [x] Item swap + DPS delta comparison working
- [x] Pytest test suite for PoBEngine — 38 tests, all passing
- [x] get_combat_profile() — charges, rage, ailments, defence, damage type %, dynamic config
- [x] get_condition_sources() — decodes why each condition matters (passive names, gem names)
- [x] Full MCP server (21 tools via FastMCP)

---

## Sprint 2: ETL Pipeline (Current)

Goal: populate SQLite with all PoE2 game data so the agent can reason about
crafting options, skill selection, and passive tree planning without PoB.

### Data sources (all from PoB vendor data)

| Table           | Source                                 | Count  |
|-----------------|----------------------------------------|--------|
| item_bases      | data/Bases/*.lua                       | ~1,755 |
| item_mods       | data/ModItem.lua + 8 other categories  | ~9,363 |
| gems            | data/Gems.lua                          | ~966   |
| uniques         | data/Uniques/*.lua                     | ~443   |
| passive_nodes   | build.spec.tree.nodes                  | ~4,912 |
| currencies      | static (PoE2 knowledge)                | ~80    |

### Tasks

- [ ] `src/poe2_crafting_mcp/data/schema.sql` — SQLite DDL
- [ ] `src/poe2_crafting_mcp/data/currencies.py` — static PoE2 currency list
- [ ] `src/poe2_crafting_mcp/data/etl.py` — populate DB from PoB
- [ ] `src/poe2_crafting_mcp/data/database.py` — read-only query interface
- [ ] MCP tools: search_bases, search_mods, get_gem_info, search_uniques,
      search_passive_nodes, search_currencies
- [ ] Run ETL, verify row counts, commit DB

---

## Sprint 3: MCP Prompts & Resources

- [ ] `@mcp.prompt()` — standard build optimisation workflow for agent
- [ ] `@mcp.resource("poe2://scenario-rules")` — rules for realistic scenario setup
  (e.g. "set conditionCritRecently if crit_chance > 15%")
- [ ] `@mcp.resource("poe2://crafting-guide")` — currency usage guide

---

## Sprint 4: Pricing

- [ ] poe.ninja client (base/unique/gem prices)
- [ ] poe.show client (currency exchange rates)
- [ ] Economy cache in SQLite (prices table)
- [ ] League auto-detection from poe.ninja API

---

## Reference

- Planning docs: ~/OBSIDIAN_VAULT/PoE2 Crafting MCP Server/
- MVP plan: doc 10 - MVP Implementation Plan.md
- PoB engine docs: ./docs/pob-engine-boot.md
- Override docs: ./docs/uv2nix-overrides.md
