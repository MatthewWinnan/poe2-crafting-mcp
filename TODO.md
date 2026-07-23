# TODO: Next Steps (Resume When on Clean Network)

## Immediate (Day 2 continuation)

1. **Generate lockfile:**
   ```bash
   cd /home/matthew/DEV/poe2-crafting-mcp
   uv lock
   ```

2. **Enter nix shell:**
   ```bash
   nix develop
   ```

3. **Fix build failures (expected: lupa needs LuaJIT headers):**
   - Edit `nix/overrides.nix` — see `docs/uv2nix-overrides.md` for patterns
   - Retry `nix develop` until clean

4. **Verify Python + lupa:**
   ```bash
   python -c "import lupa; print('lupa OK')"
   ```

5. **Boot PoB headless via lupa (Day 3-4 milestone — critical proof of concept):**
   ```bash
   python -c "
   import lupa.luajit21 as lupa
   import os

   lua = lupa.LuaRuntime(unpack_returned_tuples=True)
   os.chdir('vendor/PathOfBuilding-PoE2/src')
   lua.execute('dofile(\"HeadlessWrapper.lua\")')
   g = lua.globals()
   print(f'PoB booted: {g.mainObject is not None}')
   print(f'Build object: {g.build is not None}')
   "
   ```
   If this works, the entire architecture is validated.

6. **Commit lockfile + any override fixes, push.**

## After PoB Boots (Day 4-8)

- Load a real build from PoB share code (decode base64+zlib → XML → loadBuildFromXML)
- Read stats back (TotalDPS, Life, Resistances)
- Implement `compare_item()` (equip item, read delta)
- Write tests against real build fixtures

## Reference

- Planning docs: ~/MATTHEW/obsidian_vault/PoE2 Crafting MCP Server/
- MVP plan: doc 10 - MVP Implementation Plan.md
- Override docs: ./docs/uv2nix-overrides.md
