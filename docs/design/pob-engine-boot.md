# PoB Engine Boot Findings

## Requirements to Boot PoB-PoE2 Headless via Lupa

### 1. Set dlopen flags BEFORE importing lupa

```python
import sys
RTLD_GLOBAL = 0x100
RTLD_NOW = 0x2
sys.setdlopenflags(RTLD_NOW | RTLD_GLOBAL)
```

This is required so that native Lua C modules (like `lua-utf8`) can resolve LuaJIT symbols (`lua_gettop`, etc.) from the process. Without this, `.so` loading fails with "undefined symbol" errors.

### 2. Nix packages required

```nix
pkgs.luajit
pkgs.lua51Packages.luasocket
pkgs.lua51Packages.luautf8
```

### 3. Set Lua package paths

```lua
package.path = "./?.lua;../runtime/lua/?.lua;../runtime/lua/?/init.lua;" .. package.path
package.cpath = "./?.so;../runtime/?.so;" .. package.cpath
```

### 4. Set `arg` table (PoB's Main.lua expects it)

```lua
arg = {}
```

### 5. Working directory must be `src/`

PoB uses relative paths throughout. `os.chdir('vendor/PathOfBuilding-PoE2/src')` before boot.

### 6. Boot sequence

```python
lua.execute('dofile("HeadlessWrapper.lua")')
```

After this:
- `globals().build` → the build object
- `globals().newBuild` → function to reset to empty build
- `globals().loadBuildFromXML` → function to load a PoB XML
- `globals().loadBuildFromJSON` → function to load from GGG API JSON

## Accessing Stats

```python
g = lua.globals()
g.newBuild()

# Stats live here:
output = g.build.calcsTab.mainOutput
output.TotalDPS       # Total DPS
output.CritChance     # Crit %
output.Speed          # Attack/cast speed
output.Life           # Total life
output.EnergyShield   # Total ES
```

## Console Output

PoB prints to stdout during boot:
- "Loading main script..." 
- "Unicode support detected"
- "Loading passive tree data for version '0_5'..."
- "missing node XXXXX" (cosmetic — some tree nodes not mapped, doesn't affect calcs)
- "Uniques loaded"
- "Rares loaded"
- "Startup time: 0 ms"

## Critical: Call PoB Methods via lua.execute(), NOT Python Attribute Access

PoB uses Lua's `:` method syntax extensively. When calling from Python via lupa's attribute
access (`g.build.itemsTab.CreateDisplayItemFromRaw(items_tab, text)`), the `self` passing
doesn't always work correctly.

**The correct pattern: wrap PoB calls in `lua.execute()`:**

```python
# WRONG — may not work due to self/method resolution:
g.build.itemsTab.CreateDisplayItemFromRaw(g.build.itemsTab, item_text)

# CORRECT — execute in Lua where : syntax works natively:
lua.execute('''
    build.itemsTab:CreateDisplayItemFromRaw([[
New Item
Razor Quarterstaff
+100% increased Physical Damage
    ]])
    build.itemsTab:AddDisplayItem()
    runCallback("OnFrame")
''')

# Read values back in Python:
dps = lua.execute('return build.calcsTab.mainOutput.TotalDPS')
```

**Tested and confirmed working:**
```
TotalDPS: 7.76 (with a +100% phys quarterstaff)
CritChance: 2.5
```

## Known Issues

- `mainObject` is `False/nil` when accessed from Python, but `build` works directly via lua.execute
- "missing node" warnings are harmless
- First boot takes ~2-3 seconds (loading tree data, uniques, rares)
- Must call PoB methods from Lua context (lua.execute), not Python attribute access
