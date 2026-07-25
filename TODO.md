# TODO: Next Steps

## ✅ COMPLETED

- [x] Generate uv.lock
- [x] Enter nix shell (nix develop works)
- [x] lupa + LuaJIT working
- [x] PoB headless boots via lupa
- [x] Load real build (960K DPS Whirling Trinity Martial Artist)
- [x] PoBEngine class with full Python API
- [x] Item swap + DPS delta comparison working

---

## Next Session: Local Setup & Real Build

### 1. Get your actual PoE2 build into the system

- Install **PoB-PoE2** on your NixOS machine (add to nix_repo)
- Import your character in PoB-PoE2 (account name → select character)
- Export share code → save to `data/builds/my_build.txt`
- Test: `engine.load_build_from_file("data/builds/my_build.txt")`

### 2. Install community tools on NixOS (nix_repo additions)

- **Path of Building PoE2** — desktop app for build planning
- **Craft of Exile** — browser tool (no install needed, just bookmark)
- **Exiled Exchange 2** — in-game price check overlay

### 3. Fix PoE2 Linux client

- Currently opens in controller mode only (no keyboard/mouse support)
- Investigate: might be a Steam Input issue or Proton config
- Check: `~/.local/share/Steam/steamapps/common/Path of Exile 2/` for config files
- Common fix: disable Steam Input for the game, or set `SDL_GAMECONTROLLERCONFIG`

### 4. Write pytest tests for PoBEngine

```bash
cd ~/DEV/poe2-crafting-mcp
nix develop
PYTHONPATH=src pytest tests/
```

Tests to write:
- `test_engine_boots` — PoBEngine initializes without error
- `test_load_build` — loads fixture, stats are non-zero
- `test_equip_item` — swapping gloves changes DPS
- `test_get_build_info` — returns correct class/ascendancy
- `test_get_keystones` — returns Chaos Inoculation for fixture build

---

## Sprint 2 Remaining

- [x] Pytest test suite for PoBEngine — 32 tests, all passing
- [ ] SQLite schema + database module

## Sprint 3: Pricing

- [ ] poe.show client (currency prices)
- [ ] poe.ninja client (base/unique prices)
- [ ] Economy cache in SQLite
- [ ] League auto-detection

## Reference

- Planning docs: ~/MATTHEW/obsidian_vault/PoE2 Crafting MCP Server/
- MVP plan: doc 10 - MVP Implementation Plan.md
- PoB engine docs: ./docs/pob-engine-boot.md
- Override docs: ./docs/uv2nix-overrides.md
