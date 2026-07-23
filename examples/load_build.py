"""
Example: Load a PoB build, print stats, inspect passives, swap items.

Usage:
    cd /home/matthew/DEV/poe2-crafting-mcp
    nix develop --command python examples/load_build.py
"""

import sys
import os
import base64
import zlib

# CRITICAL: Set dlopen flags before importing lupa
# This allows native Lua modules (lua-utf8) to resolve LuaJIT symbols
sys.setdlopenflags(0x2 | 0x100)  # RTLD_NOW | RTLD_GLOBAL

import lupa.luajit21 as lupa


def decode_pob_code(code: str) -> str:
    """Decode a PoB share code (base64url + zlib) into XML."""
    code = code.strip()
    padding = 4 - len(code) % 4
    if padding != 4:
        code += "=" * padding
    raw = base64.urlsafe_b64decode(code)
    return zlib.decompress(raw).decode("utf-8")


def boot_pob(pob_path: str) -> lupa.LuaRuntime:
    """Boot PoB-PoE2 headless and return the Lua runtime."""
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    os.chdir(os.path.join(pob_path, "src"))
    lua.execute('''
        package.path = "./?.lua;../runtime/lua/?.lua;../runtime/lua/?/init.lua;" .. package.path
        package.cpath = "./?.so;../runtime/?.so;" .. package.cpath
        arg = {}
    ''')
    lua.execute('dofile("HeadlessWrapper.lua")')
    return lua


def load_build(lua: lupa.LuaRuntime, build_file: str):
    """Load a build from a file containing a PoB share code."""
    with open(build_file, "r") as f:
        code = f.read().strip()
    xml = decode_pob_code(code)
    lua.globals().loadBuildFromXML(xml, "Loaded Build")
    lua.execute('runCallback("OnFrame")')


def print_build_summary(lua: lupa.LuaRuntime):
    """Print key build stats."""
    summary = lua.execute('''
        local o = build.calcsTab.mainOutput
        local b = build
        local lines = {}
        lines[#lines+1] = "=== BUILD SUMMARY ==="
        lines[#lines+1] = string.format("Class: %s (%s)", b.spec.curClassName or "?", b.spec.curAscendClassName or "?")
        lines[#lines+1] = string.format("Level: %d", b.characterLevel or 0)
        lines[#lines+1] = ""
        lines[#lines+1] = "--- OFFENCE ---"
        lines[#lines+1] = string.format("Total DPS:      %.0f", o.TotalDPS or 0)
        lines[#lines+1] = string.format("Crit Chance:    %.2f%%", o.CritChance or 0)
        lines[#lines+1] = string.format("Crit Multi:     %.2fx", o.CritMultiplier or 0)
        lines[#lines+1] = string.format("Hit Chance:     %.1f%%", o.HitChance or 0)
        lines[#lines+1] = string.format("Attack Speed:   %.2f", o.Speed or 0)
        lines[#lines+1] = ""
        lines[#lines+1] = "--- DEFENCE ---"
        lines[#lines+1] = string.format("Life:           %.0f", o.Life or 0)
        lines[#lines+1] = string.format("Energy Shield:  %.0f", o.EnergyShield or 0)
        lines[#lines+1] = string.format("Mana:           %.0f", o.Mana or 0)
        lines[#lines+1] = string.format("Evasion:        %.0f", o.Evasion or 0)
        lines[#lines+1] = string.format("Armour:         %.0f", o.Armour or 0)
        lines[#lines+1] = ""
        lines[#lines+1] = "--- RESISTANCES ---"
        lines[#lines+1] = string.format("Fire:           %.0f%%", o.FireResist or 0)
        lines[#lines+1] = string.format("Cold:           %.0f%%", o.ColdResist or 0)
        lines[#lines+1] = string.format("Lightning:      %.0f%%", o.LightningResist or 0)
        lines[#lines+1] = string.format("Chaos:          %.0f%%", o.ChaosResist or 0)
        return table.concat(lines, "\\n")
    ''')
    print(summary)


def print_equipped_items(lua: lupa.LuaRuntime):
    """Print all equipped items with their key mods."""
    items_info = lua.execute('''
        local lines = {}
        lines[#lines+1] = ""
        lines[#lines+1] = "=== EQUIPPED ITEMS ==="
        local slotNames = {"Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots", "Amulet", "Ring 1", "Ring 2", "Belt"}
        for _, slotName in ipairs(slotNames) do
            local slot = build.itemsTab.slots[slotName]
            if slot and slot.selItemId and slot.selItemId > 0 then
                local item = build.itemsTab.items[slot.selItemId]
                if item then
                    lines[#lines+1] = string.format("  [%s] %s (%s) ilvl=%d",
                        slotName,
                        item.name or item.baseName,
                        item.rarity or "?",
                        item.itemLevel or 0
                    )
                    -- Show first 3 explicit mods
                    for i, ml in ipairs(item.explicitModLines) do
                        if i <= 3 then
                            lines[#lines+1] = "      " .. ml.line
                        end
                    end
                    if #item.explicitModLines > 3 then
                        lines[#lines+1] = string.format("      ... +%d more mods", #item.explicitModLines - 3)
                    end
                end
            else
                lines[#lines+1] = string.format("  [%s] (empty)", slotName)
            end
        end
        return table.concat(lines, "\\n")
    ''')
    print(items_info)


def print_notable_passives(lua: lupa.LuaRuntime):
    """Print allocated notable and keystone passives."""
    passives = lua.execute('''
        local lines = {}
        lines[#lines+1] = ""
        lines[#lines+1] = "=== NOTABLE PASSIVES ==="
        local notables = {}
        local keystones = {}
        for nodeId, node in pairs(build.spec.allocNodes) do
            if node.isKeystone then
                keystones[#keystones+1] = node.dn or node.name or tostring(nodeId)
            elseif node.isNotable then
                notables[#notables+1] = node.dn or node.name or tostring(nodeId)
            end
        end
        table.sort(keystones)
        table.sort(notables)
        lines[#lines+1] = "  Keystones:"
        for _, k in ipairs(keystones) do
            lines[#lines+1] = "    * " .. k
        end
        lines[#lines+1] = ""
        lines[#lines+1] = string.format("  Notables (%d):", #notables)
        for i, n in ipairs(notables) do
            if i <= 15 then
                lines[#lines+1] = "    - " .. n
            end
        end
        if #notables > 15 then
            lines[#lines+1] = string.format("    ... +%d more", #notables - 15)
        end
        return table.concat(lines, "\\n")
    ''')
    print(passives)


def swap_item_and_compare(lua: lupa.LuaRuntime, slot: str, new_item_text: str):
    """
    Swap an item in a slot and show the stat difference.

    Args:
        slot: PoB slot name (e.g., "Gloves", "Body Armour")
        new_item_text: PoB raw text format item
    """
    # Get stats before
    before_dps = lua.execute('return build.calcsTab.mainOutput.TotalDPS or 0')
    before_es = lua.execute('return build.calcsTab.mainOutput.EnergyShield or 0')
    before_crit = lua.execute('return build.calcsTab.mainOutput.CritChance or 0')

    # Swap the item
    # We pass the item text and slot via Lua string to avoid escaping issues
    lua.execute(f'''
        build.itemsTab:CreateDisplayItemFromRaw([[{new_item_text}]])
        local newItem = build.itemsTab.displayItem
        if newItem then
            build.itemsTab:AddItem(newItem, true)
            build.itemsTab.slots["{slot}"]:SetSelItemId(newItem.id)
            build.buildFlag = true
            runCallback("OnFrame")
        end
    ''')

    # Get stats after
    after_dps = lua.execute('return build.calcsTab.mainOutput.TotalDPS or 0')
    after_es = lua.execute('return build.calcsTab.mainOutput.EnergyShield or 0')
    after_crit = lua.execute('return build.calcsTab.mainOutput.CritChance or 0')

    # Print comparison
    print(f"\n=== ITEM SWAP: {slot} ===")
    print(f"  DPS:   {before_dps:,.0f}  →  {after_dps:,.0f}  ({after_dps - before_dps:+,.0f})")
    print(f"  ES:    {before_es:,.0f}  →  {after_es:,.0f}  ({after_es - before_es:+,.0f})")
    print(f"  Crit:  {before_crit:.2f}%  →  {after_crit:.2f}%  ({after_crit - before_crit:+.2f}%)")


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Paths
    repo_root = os.environ.get("REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pob_path = os.environ.get("POB_PATH", os.path.join(repo_root, "vendor", "PathOfBuilding-PoE2"))
    build_file = os.path.join(repo_root, "data", "builds", "whirling_trinity_martial_artist.txt")

    print(f"Loading PoB from: {pob_path}")
    print(f"Build file: {build_file}")
    print()

    # Boot PoB
    lua = boot_pob(pob_path)

    # Load the build
    load_build(lua, build_file)

    # Print everything
    print_build_summary(lua)
    print_equipped_items(lua)
    print_notable_passives(lua)

    # ─── ITEM SWAP EXAMPLES ────────────────────────────────────────
    # Uncomment any of these to test item swaps:

    # Example 1: Replace gloves with a white base (huge DPS loss)
    # swap_item_and_compare(lua, "Gloves", "New Item\nFists of Stone")

    # Example 2: Replace gloves with a crafted rare
    # swap_item_and_compare(lua, "Gloves", """Rarity: RARE
    # Crafted Gloves
    # Fists of Stone
    # Item Level: 86
    # Implicits: 2
    # Has +3 to Evasion Rating per player level
    # Has +1 to maximum Energy Shield per player level
    # +100 to maximum Energy Shield
    # +40% to Lightning Resistance
    # +2% to Critical Hit Chance
    # Attacks Gain 15% of Damage as Extra Fire Damage""")

    # Example 3: Test a unique item
    # swap_item_and_compare(lua, "Gloves", """Rarity: UNIQUE
    # Some Unique Gloves
    # Fists of Stone
    # +50% to Critical Hit Chance
    # +200 to maximum Energy Shield""")
