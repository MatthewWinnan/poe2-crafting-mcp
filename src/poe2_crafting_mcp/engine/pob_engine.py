"""
PoB Calculation Engine — embeds PoB-PoE2 via lupa (LuaJIT).

This module wraps the Path of Building PoE2 calculation engine,
providing a clean Python API to load builds, swap items, and read
back DPS/defence statistics.

Critical notes:
- Must set sys.setdlopenflags(RTLD_NOW | RTLD_GLOBAL) BEFORE importing lupa
- PoB methods must be called via lua.execute() (Lua context), not Python attribute access
- Working directory must be src/ when PoB boots (relative path resolution)
- See docs/pob-engine-boot.md for full details
"""

import base64
import os
import sys
import zlib
from pathlib import Path

from .models import (
    AilmentInfo,
    BuildInfo,
    BuildStats,
    ChargeInfo,
    CombatProfile,
    ConfigOptionInfo,
    DPSDelta,
    EquippedItem,
    GemInstance,
    SocketGroup,
    TreeJewel,
)

# CRITICAL: Set dlopen flags before any lupa import
# Allows native Lua C modules (lua-utf8) to resolve LuaJIT symbols
sys.setdlopenflags(0x2 | 0x100)  # RTLD_NOW | RTLD_GLOBAL

import lupa.luajit21 as lupa  # noqa: E402


class PoBEngine:
    """
    Embeds the PoB-PoE2 calculation engine via lupa.

    Usage:
        engine = PoBEngine("/path/to/PathOfBuilding-PoE2")
        engine.load_build_from_code(pob_share_code)
        stats = engine.get_stats()
        delta = engine.equip_item("Gloves", item_text)
    """

    # Slot names that PoB uses internally
    SLOT_NAMES = [
        "Weapon 1",
        "Weapon 2",
        "Helmet",
        "Body Armour",
        "Gloves",
        "Boots",
        "Amulet",
        "Ring 1",
        "Ring 2",
        "Belt",
    ]

    def __init__(self, pob_path: str | Path):
        """
        Initialize the Lua runtime and boot PoB headlessly.

        Args:
            pob_path: Path to the cloned PathOfBuilding-PoE2 repo root.
        """
        self.pob_path = Path(pob_path)
        self.src_path = self.pob_path / "src"

        if not (self.src_path / "HeadlessWrapper.lua").exists():
            raise FileNotFoundError(
                f"HeadlessWrapper.lua not found at {self.src_path}. "
                "Is the PoB-PoE2 submodule initialized?"
            )

        self._original_cwd = os.getcwd()
        self._lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        self._booted = False
        self._build_loaded = False

        self._boot()

    def _boot(self) -> None:
        """Boot PoB headless engine."""
        os.chdir(self.src_path)

        self._lua.execute('''
            package.path = "./?.lua;../runtime/lua/?.lua;../runtime/lua/?/init.lua;" .. package.path
            package.cpath = "./?.so;../runtime/?.so;" .. package.cpath
            arg = {}
        ''')

        self._lua.execute('dofile("HeadlessWrapper.lua")')
        self._booted = True

    # ─── Build Loading ────────────────────────────────────────────

    def load_build_from_code(self, code: str, name: str = "Loaded Build") -> BuildStats:
        """
        Load a build from a PoB share code (base64url + zlib compressed XML).

        Args:
            code: The PoB share/pastebin code string.
            name: Display name for the build.

        Returns:
            BuildStats after loading.
        """
        xml = self._decode_share_code(code)
        return self.load_build_from_xml(xml, name)

    def load_build_from_file(self, path: str | Path, name: str | None = None) -> BuildStats:
        """
        Load a build from a file containing a PoB share code.

        Args:
            path: Path to a text file with the share code (absolute or relative to original CWD).
            name: Display name (defaults to filename).
        """
        path = Path(path)
        # Resolve relative paths against the original working directory (before PoB changed it)
        if not path.is_absolute():
            path = Path(self._original_cwd) / path
        path = path.resolve()

        if name is None:
            name = path.stem.replace("_", " ").title()

        with open(path, "r") as f:
            code = f.read().strip()

        return self.load_build_from_code(code, name)

    def load_build_from_xml(self, xml: str, name: str = "Loaded Build") -> BuildStats:
        """
        Load a build from raw PoB XML.

        Args:
            xml: The full PoB XML string.
            name: Display name for the build.

        Returns:
            BuildStats after loading.
        """
        self._lua.globals().loadBuildFromXML(xml, name)
        self._lua.execute('runCallback("OnFrame")')
        self._build_loaded = True
        return self.get_stats()

    # ─── Stats Reading ────────────────────────────────────────────

    def get_stats(self) -> BuildStats:
        """Get current calculated build statistics."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            return {
                TotalDPS = o.TotalDPS or 0,
                CritChance = o.CritChance or 0,
                CritMultiplier = o.CritMultiplier or 0,
                HitChance = o.HitChance or 0,
                Speed = o.Speed or 0,
                PhysDPS = o.PhysicalDPS or 0,
                FireDPS = o.FireDPS or 0,
                ColdDPS = o.ColdDPS or 0,
                LightningDPS = o.LightningDPS or 0,
                ChaosDPS = o.ChaosDPS or 0,
                Life = o.Life or 0,
                EnergyShield = o.EnergyShield or 0,
                Ward = o.Ward or 0,
                Mana = o.Mana or 0,
                Evasion = o.Evasion or 0,
                Armour = o.Armour or 0,
                BlockChance = o.BlockChance or 0,
                SpellBlockChance = o.SpellBlockChance or 0,
                FireResist = o.FireResist or 0,
                ColdResist = o.ColdResist or 0,
                LightningResist = o.LightningResist or 0,
                ChaosResist = o.ChaosResist or 0,
            }
        ''')

        return BuildStats(
            total_dps=raw["TotalDPS"],
            crit_chance=raw["CritChance"],
            crit_multiplier=raw["CritMultiplier"],
            hit_chance=raw["HitChance"],
            speed=raw["Speed"],
            phys_dps=raw["PhysDPS"],
            fire_dps=raw["FireDPS"],
            cold_dps=raw["ColdDPS"],
            lightning_dps=raw["LightningDPS"],
            chaos_dps=raw["ChaosDPS"],
            life=raw["Life"],
            energy_shield=raw["EnergyShield"],
            ward=raw["Ward"],
            mana=raw["Mana"],
            evasion=raw["Evasion"],
            armour=raw["Armour"],
            block_chance=raw["BlockChance"],
            spell_block_chance=raw["SpellBlockChance"],
            fire_res=raw["FireResist"],
            cold_res=raw["ColdResist"],
            lightning_res=raw["LightningResist"],
            chaos_res=raw["ChaosResist"],
        )

    def get_build_info(self) -> BuildInfo:
        """Get build metadata (class, level, skill)."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local b = build
            local mainSkill = "Unknown"
            if b.mainSocketGroup and b.mainSocketGroup > 0 then
                local sg = b.skillsTab.socketGroupList[b.mainSocketGroup]
                if sg and sg.displayLabel then
                    mainSkill = sg.displayLabel
                end
            end
            local totalAlloc, keystones, notables = 0, 0, 0
            for _, node in pairs(b.spec.allocNodes) do
                totalAlloc = totalAlloc + 1
                if node.isKeystone then keystones = keystones + 1
                elseif node.isNotable then notables = notables + 1
                end
            end
            return {
                className = b.spec.curClassName or "",
                ascendancy = b.spec.curAscendClassName or "",
                level = b.characterLevel or 0,
                mainSkill = mainSkill,
                totalAlloc = totalAlloc,
                keystones = keystones,
                notables = notables,
            }
        ''')

        return BuildInfo(
            class_name=raw["className"],
            ascendancy=raw["ascendancy"],
            level=raw["level"],
            main_skill=raw["mainSkill"],
            total_allocated=raw["totalAlloc"],
            keystone_count=raw["keystones"],
            notable_count=raw["notables"],
        )

    # ─── Item Operations ──────────────────────────────────────────

    def equip_item(self, slot: str, item_text: str) -> DPSDelta:
        """
        Equip an item in a slot and return the stat delta.

        Args:
            slot: PoB slot name (e.g., "Gloves", "Body Armour", "Weapon 1")
            item_text: Item in PoB raw text format.

        Returns:
            DPSDelta comparing before and after.
        """
        self._ensure_build_loaded()
        self._validate_slot(slot)

        before = self.get_stats()

        # Use [=[ ]=] delimiters to avoid issues with [[ ]] inside item text
        self._lua.execute(f'''
            build.itemsTab:CreateDisplayItemFromRaw([=[{item_text}]=])
            local newItem = build.itemsTab.displayItem
            if newItem then
                build.itemsTab:AddItem(newItem, true)
                build.itemsTab.slots["{slot}"]:SetSelItemId(newItem.id)
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')

        after = self.get_stats()
        return DPSDelta(before=before, after=after)

    def unequip_slot(self, slot: str) -> DPSDelta:
        """
        Remove the item from a slot.

        Args:
            slot: PoB slot name.

        Returns:
            DPSDelta comparing before and after.
        """
        self._ensure_build_loaded()
        self._validate_slot(slot)

        before = self.get_stats()

        self._lua.execute(f'''
            build.itemsTab.slots["{slot}"]:SetSelItemId(0)
            build.buildFlag = true
            runCallback("OnFrame")
        ''')

        after = self.get_stats()
        return DPSDelta(before=before, after=after)

    def get_equipped_items(self) -> dict[str, EquippedItem | None]:
        """Get all equipped items with their mods."""
        self._ensure_build_loaded()

        items = {}
        for slot in self.SLOT_NAMES:
            raw = self._lua.execute(f'''
                local slot = build.itemsTab.slots["{slot}"]
                if slot and slot.selItemId and slot.selItemId > 0 then
                    local item = build.itemsTab.items[slot.selItemId]
                    if item then
                        local explicits = {{}}
                        for _, ml in ipairs(item.explicitModLines or {{}}) do
                            explicits[#explicits+1] = ml.line
                        end
                        local implicits = {{}}
                        for _, ml in ipairs(item.implicitModLines or {{}}) do
                            implicits[#implicits+1] = ml.line
                        end
                        return {{
                            name = item.name or "",
                            baseName = item.baseName or "",
                            rarity = item.rarity or "NORMAL",
                            itemLevel = item.itemLevel or 0,
                            quality = item.quality or 0,
                            corrupted = item.corrupted or false,
                            explicits = explicits,
                            implicits = implicits,
                            raw = item.raw or "",
                        }}
                    end
                end
                return nil
            ''')

            if raw is not None:
                items[slot] = EquippedItem(
                    slot=slot,
                    name=raw["name"],
                    base_type=raw["baseName"],
                    rarity=raw["rarity"],
                    item_level=raw["itemLevel"],
                    quality=int(raw["quality"]),
                    corrupted=bool(raw["corrupted"]),
                    explicit_mods=list(raw["explicits"].values()) if raw["explicits"] else [],
                    implicit_mods=list(raw["implicits"].values()) if raw["implicits"] else [],
                    raw_text=raw["raw"],
                )
            else:
                items[slot] = None

        return items

    def get_socket_groups(self) -> list[SocketGroup]:
        """Get all socket groups with full gem details."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local result = {}
            for i, sg in ipairs(build.skillsTab.socketGroupList) do
                local gems = {}
                for j, gem in ipairs(sg.gemList or {}) do
                    gems[j] = {
                        name = (gem.gemData and gem.gemData.name) or gem.nameSpec or "Unknown",
                        level = gem.level or 1,
                        quality = gem.quality or 0,
                        isSupport = gem.gemData and gem.gemData.grantedEffect and gem.gemData.grantedEffect.support or false,
                        corrupted = gem.corrupted or false,
                        corruptLevel = gem.corruptLevel or 0,
                        enabled = gem.enabled ~= false,
                    }
                end
                result[i] = {
                    label = sg.displayLabel or ("Group " .. i),
                    slot = sg.slot or "",
                    enabled = sg.enabled ~= false,
                    includeInFullDPS = sg.includeInFullDPS or false,
                    gems = gems,
                }
            end
            return result
        ''')

        groups = []
        for sg_raw in (raw.values() if raw else []):
            gems = []
            if sg_raw["gems"]:
                for gem_raw in sg_raw["gems"].values():
                    gems.append(GemInstance(
                        name=gem_raw["name"],
                        level=int(gem_raw["level"]),
                        quality=int(gem_raw["quality"]),
                        is_support=bool(gem_raw["isSupport"]),
                        corrupted=bool(gem_raw["corrupted"]),
                        corrupt_level=int(gem_raw["corruptLevel"]),
                        enabled=bool(gem_raw["enabled"]),
                    ))
            groups.append(SocketGroup(
                label=sg_raw["label"],
                slot=sg_raw["slot"],
                enabled=bool(sg_raw["enabled"]),
                include_in_full_dps=bool(sg_raw["includeInFullDPS"]),
                gems=gems,
            ))
        return groups

    def get_tree_jewels(self) -> list[TreeJewel]:
        """Get jewels socketed in passive tree nodes."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local result = {}
            local idx = 1
            for nodeId, itemId in pairs(build.spec.jewels) do
                local item = build.itemsTab.items[itemId]
                if item then
                    local mods = {}
                    for _, ml in ipairs(item.explicitModLines or {}) do
                        mods[#mods+1] = ml.line
                    end
                    result[idx] = {
                        nodeId = nodeId,
                        name = item.name or "",
                        baseName = item.baseName or "",
                        corrupted = item.corrupted or false,
                        mods = mods,
                    }
                    idx = idx + 1
                end
            end
            return result
        ''')

        jewels = []
        for j in (raw.values() if raw else []):
            jewels.append(TreeJewel(
                node_id=int(j["nodeId"]),
                name=j["name"],
                base_type=j["baseName"],
                corrupted=bool(j["corrupted"]),
                explicit_mods=list(j["mods"].values()) if j["mods"] else [],
            ))
        return jewels

    # ─── Passive Tree ─────────────────────────────────────────────

    def get_keystones(self) -> list[str]:
        """Get allocated keystone passives."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local result = {}
            for _, node in pairs(build.spec.allocNodes) do
                if node.isKeystone then
                    result[#result+1] = node.dn or node.name or "?"
                end
            end
            table.sort(result)
            return result
        ''')

        return list(raw.values()) if raw else []

    def get_notables(self) -> list[str]:
        """Get allocated notable passives."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local result = {}
            for _, node in pairs(build.spec.allocNodes) do
                if node.isNotable then
                    result[#result+1] = node.dn or node.name or "?"
                end
            end
            table.sort(result)
            return result
        ''')

        return list(raw.values()) if raw else []

    # ─── Generic Output ───────────────────────────────────────────

    def get_output(self) -> dict[str, float | int | bool | str]:
        """
        Return the full PoB calculation output table as a Python dict.

        Covers all ~200 offence + defence stats. Keys match PoB's internal
        names exactly (e.g. "TotalDPS", "Ward", "BlockChance").
        Values are coerced: numbers → float, booleans → bool, strings → str.
        nil values are omitted.

        Use this when you need a stat that isn't in BuildStats, or when
        iterating over all stats to find what changed.
        """
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            local result = {}
            for k, v in pairs(o) do
                local t = type(v)
                if t == "number" or t == "boolean" or t == "string" then
                    result[k] = v
                end
            end
            return result
        ''')

        return dict(raw) if raw else {}

    # ─── Generic Config ───────────────────────────────────────────

    def get_config_option(self, var: str) -> bool | int | float | str | None:
        """
        Read a single config option by its var name.

        See PoB's ConfigOptions.lua for all 542 valid var names.
        Returns None if the option is not set.
        """
        self._ensure_build_loaded()
        val = self._lua.execute(f'return build.configTab.input["{var}"]')
        return val  # type: ignore[return-value]

    def set_config_option(self, var: str, value: bool | int | float | str | None) -> BuildStats:
        """
        Set a single config option and recalculate.

        Args:
            var:   Config option var name from ConfigOptions.lua.
            value: New value. Pass None to clear the option.

        Returns:
            Updated BuildStats.

        Examples:
            engine.set_config_option("conditionFull", True)
            engine.set_config_option("enemyLevel", 85)
            engine.set_config_option("buffOnslaught", True)
        """
        self._ensure_build_loaded()

        if value is None:
            self._lua.execute(f'build.configTab.input["{var}"] = nil')
        elif isinstance(value, bool):
            lua_val = "true" if value else "false"
            self._lua.execute(f'build.configTab.input["{var}"] = {lua_val}')
        elif isinstance(value, str):
            self._lua.execute(f'build.configTab.input["{var}"] = [=[{value}]=]')
        else:
            self._lua.execute(f'build.configTab.input["{var}"] = {value}')

        self._lua.execute('build.configTab:BuildModList(); runCallback("OnFrame")')
        return self.get_stats()

    def get_all_config(self) -> dict[str, bool | int | float | str]:
        """
        Return all currently-set config options as a dict.

        Only options that have been explicitly set are returned;
        unset options use PoB's internal defaults.
        """
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local result = {}
            for k, v in pairs(build.configTab.input) do
                local t = type(v)
                if t == "number" or t == "boolean" or t == "string" then
                    result[k] = v
                end
            end
            return result
        ''')

        return dict(raw) if raw else {}

    # ─── Configuration (Buffs/Debuffs) ────────────────────────────

    def set_config(self, custom_mods: str) -> BuildStats:
        """
        Set custom configuration mods (for "what if" testing).

        Example:
            engine.set_config("+50% to critical hit chance\\nnearby enemies are shocked")

        Args:
            custom_mods: Newline-separated mod strings.

        Returns:
            Updated BuildStats.
        """
        self._ensure_build_loaded()

        self._lua.execute(f'''
            build.configTab.input.customMods = [=[{custom_mods}]=]
            build.configTab:BuildModList()
            runCallback("OnFrame")
        ''')

        return self.get_stats()

    def clear_config(self) -> BuildStats:
        """Clear all custom config mods."""
        return self.set_config("")

    # ─── Skill Selection ──────────────────────────────────────────

    def get_skill_list(self) -> list[str]:
        """Return the labels of all socket groups (skills) in the build."""
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local result = {}
            for i, sg in ipairs(build.skillsTab.socketGroupList) do
                result[i] = sg.displayLabel or ("Skill " .. i)
            end
            return result
        ''')

        return list(raw.values()) if raw else []

    def set_main_skill(self, index: int) -> BuildStats:
        """
        Set the active socket group by 1-based index.

        Args:
            index: 1-based index into the socket group list.

        Returns:
            Updated BuildStats after recalculation.
        """
        self._ensure_build_loaded()

        skill_list = self.get_skill_list()
        if not 1 <= index <= len(skill_list):
            raise ValueError(
                f"Skill index {index} out of range. "
                f"Valid range: 1-{len(skill_list)}. "
                f"Skills: {skill_list}"
            )

        self._lua.execute(f'''
            build.mainSocketGroup = {index}
            build.buildFlag = true
            runCallback("OnFrame")
        ''')

        return self.get_stats()

    # ─── Gem Setters ──────────────────────────────────────────────

    def set_gem_level(self, group: int, gem: int, level: int) -> BuildStats:
        """
        Set the level of a gem and recalculate.

        Args:
            group: 1-based socket group index.
            gem:   1-based gem index within the group.
            level: New gem level (1–40).

        Returns:
            Updated BuildStats.
        """
        self._ensure_build_loaded()
        self._lua.execute(f'''
            local sg = build.skillsTab.socketGroupList[{group}]
            if sg and sg.gemList[{gem}] then
                sg.gemList[{gem}].level = {level}
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    def set_gem_quality(self, group: int, gem: int, quality: int) -> BuildStats:
        """Set the quality of a gem (0–40) and recalculate."""
        self._ensure_build_loaded()
        self._lua.execute(f'''
            local sg = build.skillsTab.socketGroupList[{group}]
            if sg and sg.gemList[{gem}] then
                sg.gemList[{gem}].quality = {quality}
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    def set_gem_corrupted(
        self, group: int, gem: int, corrupted: bool, corrupt_level: int = 0
    ) -> BuildStats:
        """
        Set the corrupted state of a gem and recalculate.

        Args:
            group:         1-based socket group index.
            gem:           1-based gem index.
            corrupted:     Whether the gem is corrupted.
            corrupt_level: Corruption level adjustment (+1, 0, or -1).
        """
        self._ensure_build_loaded()
        lua_corrupted = "true" if corrupted else "false"
        self._lua.execute(f'''
            local sg = build.skillsTab.socketGroupList[{group}]
            if sg and sg.gemList[{gem}] then
                sg.gemList[{gem}].corrupted = {lua_corrupted}
                sg.gemList[{gem}].corruptLevel = {corrupt_level}
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    def set_gem_enabled(self, group: int, gem: int, enabled: bool) -> BuildStats:
        """Enable or disable a gem and recalculate."""
        self._ensure_build_loaded()
        lua_enabled = "true" if enabled else "false"
        self._lua.execute(f'''
            local sg = build.skillsTab.socketGroupList[{group}]
            if sg and sg.gemList[{gem}] then
                sg.gemList[{gem}].enabled = {lua_enabled}
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    def set_socket_group_enabled(self, group: int, enabled: bool) -> BuildStats:
        """Enable or disable an entire socket group and recalculate."""
        self._ensure_build_loaded()
        lua_enabled = "true" if enabled else "false"
        self._lua.execute(f'''
            local sg = build.skillsTab.socketGroupList[{group}]
            if sg then
                sg.enabled = {lua_enabled}
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    def set_socket_group_include_in_full_dps(self, group: int, include: bool) -> BuildStats:
        """Toggle whether a socket group is included in full DPS calculation."""
        self._ensure_build_loaded()
        lua_include = "true" if include else "false"
        self._lua.execute(f'''
            local sg = build.skillsTab.socketGroupList[{group}]
            if sg then
                sg.includeInFullDPS = {lua_include}
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    # ─── Tree Jewel Setters ───────────────────────────────────────

    def set_tree_jewel(self, node_id: int, item_text: str) -> BuildStats:
        """
        Socket a jewel into a passive tree node and recalculate.

        Args:
            node_id:   The passive tree node ID to socket into.
            item_text: Raw item text (same format as equip_item).

        Returns:
            Updated BuildStats.
        """
        self._ensure_build_loaded()
        self._lua.execute(f'''
            build.itemsTab:CreateDisplayItemFromRaw([=[{item_text}]=])
            local newItem = build.itemsTab.displayItem
            if newItem then
                build.itemsTab:AddItem(newItem, true)
                build.spec.jewels[{node_id}] = newItem.id
                build.spec:AddUndoState()
                build.buildFlag = true
                runCallback("OnFrame")
            end
        ''')
        return self.get_stats()

    def remove_tree_jewel(self, node_id: int) -> BuildStats:
        """
        Unsocket the jewel from a passive tree node and recalculate.

        Args:
            node_id: The passive tree node ID to clear.

        Returns:
            Updated BuildStats.
        """
        self._ensure_build_loaded()
        self._lua.execute(f'''
            build.spec.jewels[{node_id}] = nil
            build.spec:AddUndoState()
            build.buildFlag = true
            runCallback("OnFrame")
        ''')
        return self.get_stats()

    # ─── Character ────────────────────────────────────────────────

    def set_character_level(self, level: int) -> BuildStats:
        """
        Set the character level (1–100) and recalculate.

        Returns:
            Updated BuildStats.
        """
        self._ensure_build_loaded()
        level = max(1, min(100, level))
        self._lua.execute(f'''
            build.characterLevel = {level}
            build.characterLevelAutoMode = false
            build.buildFlag = true
            runCallback("OnFrame")
        ''')
        return self.get_stats()

    # ─── Export ───────────────────────────────────────────────────

    def export_xml(self) -> str:
        """Export the current build state as PoB XML."""
        self._ensure_build_loaded()
        xml = self._lua.execute('return build:SaveDB("code")')
        if xml is None:
            raise RuntimeError("SaveDB returned nil — build may not be fully loaded.")
        return str(xml)

    def export_build_code(self) -> str:
        """Export the current build as a PoB share code (base64url + zlib)."""
        xml = self.export_xml()
        compressed = zlib.compress(xml.encode("utf-8"))
        code = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        return code

    # ─── Combat Profile ───────────────────────────────────────────

    # Config option vars that are noise for the agent (quest rewards, UI toggles,
    # NPC-specific presets) — filtered out of relevant_config.
    _CONFIG_SKIP_PREFIXES = (
        "quest", "raiseSpectre", "summonCompanion", "summonElementalRelic",
        "minions", "minionBuff", "minionbuff", "minionOverride",
        "presetBossSkills", "doomBlastSource",
    )

    # Category heuristics applied to var names / labels
    _CONFIG_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
        ("charges",    ("charge", "rage", "frenzy", "power", "endurance", "blood",
                        "inspiration", "siphoning", "challenger", "blitz", "spirit")),
        ("buffs",      ("buff", "onslaught", "adrenaline", "divinity", "unholy",
                        "elusive", "empowered", "conflux", "arcane", "infused",
                        "inquisitor", "chaotic", "fortif")),
        ("enemy",      ("enemy", "boss", "pinnacle", "uber", "resistance penalty",
                        "distance", "presence", "parry", "intimidate",
                        "crushed", "unnerved", "debilitated", "sapped",
                        "exposure", "shocked ground", "cursed", "impale", "withered",
                        "corrosion", "armour broken", "isolated", "profane")),
        ("ailments",   ("shock", "ignite", "chill", "freeze", "bleed", "poison",
                        "scorch", "sap", "brittle", "ailment", "conflux")),
        ("conditions", ("condition", "moving", "stationary", "full life", "low life",
                        "full mana", "full energy", "recently", "combat",
                        "flask", "killed", "stunned", "pinned", "taunted", "blocked",
                        "hit recently", "on full")),
        ("modes",      ("mode", "calculation", "unlucky", "repeat", "cooldown",
                        "ruthless", "warcry", "armour calc", "phys mode", "random")),
    ]

    def get_combat_profile(self) -> CombatProfile:
        """
        Return a comprehensive combat profile for the current build + config.

        Covers charges, rage, ailments the build applies to enemies, defence
        per damage type, and every config option relevant to this build with
        its current value and human-readable label/tooltip.

        Use this to understand what scenario knobs exist before calling
        set_config_option() to model realistic combat conditions.
        """
        self._ensure_build_loaded()

        # ── Charges ──────────────────────────────────────────────
        charge_raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            local inp = build.configTab.input
            return {
                Power      = {cur=o.PowerCharges or 0,      max=o.PowerChargesMax or 0,
                               cfg=inp.usePowerCharges or false},
                Frenzy     = {cur=o.FrenzyCharges or 0,     max=o.FrenzyChargesMax or 0,
                               cfg=inp.useFrenzyCharges or false},
                Endurance  = {cur=o.EnduranceCharges or 0,  max=o.EnduranceChargesMax or 0,
                               cfg=inp.useEnduranceCharges or false},
                Blood      = {cur=o.BloodCharges or 0,      max=o.BloodChargesMax or 0,
                               cfg=false},
                Inspiration= {cur=o.InspirationCharges or 0,max=o.InspirationChargesMax or 0,
                               cfg=false},
                Blitz      = {cur=o.BlitzCharges or 0,      max=o.BlitzChargesMax or 0,
                               cfg=inp.useBlitzCharges or false},
                Challenger = {cur=o.ChallengerCharges or 0, max=o.ChallengerChargesMax or 0,
                               cfg=inp.useChallengerCharges or false},
                Siphoning  = {cur=o.SiphoningCharges or 0,  max=o.SiphoningChargesMax or 0,
                               cfg=inp.useSiphoningCharges or false},
                Spirit     = {cur=o.SpiritCharges or 0,     max=o.SpiritChargesMax or 0,
                               cfg=false},
            }
        ''')
        charges: dict[str, ChargeInfo] = {}
        for name, raw in charge_raw.items():
            if raw["max"] > 0:  # only include charge types this build has access to
                charges[name] = ChargeInfo(
                    current=int(raw["cur"]),
                    maximum=int(raw["max"]),
                    configured=bool(raw["cfg"]),
                )

        # ── Rage ─────────────────────────────────────────────────
        rage_raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            local inp = build.configTab.input
            -- RageEffect is total % more attack damage from current rage stacks
            -- InherentRageLoss > 0 means the build has a rage-loss mechanic (i.e. can gain rage)
            local available = (o.InherentRageLoss or 0) > 0 or (o.RageRegen or 0) > 0
            return {
                available        = available,
                max              = o.MaximumRage or 30,
                current          = inp.multiplierRage or 0,
                effectPerStack   = 1.0,  -- base: 1% more attack damage per rage
                totalEffect      = o.RageEffect or 0,
            }
        ''')
        rage_available = bool(rage_raw["available"])
        rage_max = int(rage_raw["max"])
        rage_current = int(rage_raw["current"])
        rage_effect_per_stack = float(rage_raw["effectPerStack"])

        # ── Ailments on enemy ────────────────────────────────────
        ailment_raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            local inp = build.configTab.input
            return {
                Shock   = {chance   = o.ShockChance or 0,
                           magnitude= o.MaximumShock or 100,
                           duration = o.ShockDuration or 8,
                           stackMax = 1,
                           active   = inp.conditionEnemyShocked or false},
                Ignite  = {chance   = o.IgniteChance or 0,
                           magnitude= o.IgniteDPS or 0,
                           duration = o.IgniteDuration or 4,
                           stackMax = o.IgniteStacksMax or 1,
                           active   = false},
                Chill   = {chance   = o.ChillChance or 100,
                           magnitude= o.MaximumChill or 50,
                           duration = 2,
                           stackMax = 1,
                           active   = false},
                Freeze  = {chance   = (o.FreezeBuildupAvg or 0) > 0 and 100 or 0,
                           magnitude= o.FreezeBuildupAvg or 0,
                           duration = 0,
                           stackMax = 1,
                           active   = false},
                Poison  = {chance   = o.PoisonChance or 0,
                           magnitude= o.PoisonDPS or 0,
                           duration = o.PoisonDuration or 2,
                           stackMax = o.PoisonStacksMax or 1,
                           active   = false},
                Bleed   = {chance   = o.BleedChance or 0,
                           magnitude= o.BleedDPS or 0,
                           duration = o.BleedDuration or 5,
                           stackMax = 1,
                           active   = false},
            }
        ''')
        ailments_on_enemy: list[AilmentInfo] = []
        for name, raw in ailment_raw.items():
            chance = float(raw["chance"])
            magnitude = float(raw["magnitude"])
            # Only include ailments the build can actually apply
            if chance > 0 or magnitude > 0:
                ailments_on_enemy.append(AilmentInfo(
                    ailment=name,
                    chance_percent=chance,
                    magnitude=magnitude,
                    duration_seconds=float(raw["duration"]),
                    stack_max=int(raw["stackMax"]),
                ))

        # ── Defence ──────────────────────────────────────────────
        stats = self.get_stats()
        defence_raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            return {
                physMult      = o.PhysicalTakenHitMult or 1,
                fireMult      = o.FireTakenHitMult or 1,
                coldMult      = o.ColdTakenHitMult or 1,
                lightningMult = o.LightningTakenHitMult or 1,
                chaosMult     = o.ChaosTakenHitMult or 1,
            }
        ''')
        damage_taken_mults = {
            "Physical":  round(float(defence_raw["physMult"]), 3),
            "Fire":       round(float(defence_raw["fireMult"]), 3),
            "Cold":       round(float(defence_raw["coldMult"]), 3),
            "Lightning":  round(float(defence_raw["lightningMult"]), 3),
            "Chaos":      round(float(defence_raw["chaosMult"]), 3),
        }

        # ── Relevant config options ───────────────────────────────
        # Uses dynamic gate evaluation (replicates ConfigTab's shownFuncs logic)
        # so results reflect the currently active skill, not a static UI snapshot.
        config_raw = self._lua.execute('''
            local env = build.calcsTab.mainEnv
            local player = env.player
            local mainSkill = player and player.mainSkill
            local activeEffect = mainSkill and mainSkill.activeEffect
            local skillFlags = activeEffect and activeEffect.statSet
                               and activeEffect.statSet.skillFlags or {}
            local skillModList = mainSkill and mainSkill.skillModList
            local skillName = activeEffect and activeEffect.grantedEffect
                              and activeEffect.grantedEffect.name

            local function listOrSingle(v, fn)
                if type(v) == "table" then
                    for _, item in ipairs(v) do if fn(item) then return true end end
                    return false
                end
                return fn(v) or false
            end

            local varList = LoadModule("Modules/ConfigOptions")
            local result = {}
            local i = 1
            for _, opt in ipairs(varList) do
                if not opt.var then goto continue end
                local show = true
                -- ifOption: another option must currently be set
                if show and opt.ifOption then
                    show = listOrSingle(opt.ifOption,
                        function(o) return build.configTab.input[o] end)
                end
                -- ifCond: condition must be referenced by this skill's calc
                if show and opt.ifCond then
                    show = listOrSingle(opt.ifCond,
                        function(c) return env.conditionsUsed and env.conditionsUsed[c] end)
                end
                -- ifMinionCond
                if show and opt.ifMinionCond then
                    show = listOrSingle(opt.ifMinionCond,
                        function(c) return env.minionConditionsUsed and env.minionConditionsUsed[c] end)
                end
                -- ifEnemyCond
                if show and opt.ifEnemyCond then
                    show = listOrSingle(opt.ifEnemyCond,
                        function(c) return env.enemyConditionsUsed and env.enemyConditionsUsed[c] end)
                end
                -- ifMult
                if show and opt.ifMult then
                    show = listOrSingle(opt.ifMult,
                        function(m) return env.multipliersUsed and env.multipliersUsed[m] end)
                end
                -- ifEnemyMult
                if show and opt.ifEnemyMult then
                    show = listOrSingle(opt.ifEnemyMult,
                        function(m) return env.enemyMultipliersUsed and env.enemyMultipliersUsed[m] end)
                end
                -- ifMod
                if show and opt.ifMod then
                    show = listOrSingle(opt.ifMod,
                        function(m) return env.modsUsed and env.modsUsed[m] end)
                end
                -- ifFlag: flag on the active skill
                if show and opt.ifFlag then
                    show = listOrSingle(opt.ifFlag, function(f)
                        return skillFlags[f] or
                               (skillModList and skillModList:Flag(nil, f))
                    end)
                end
                -- ifSkill: must match active skill name
                if show and opt.ifSkill then
                    show = listOrSingle(opt.ifSkill,
                        function(s) return skillName == s end)
                end
                -- ifSkillData: skill data key must be set
                if show and opt.ifSkillData then
                    local sd = mainSkill and mainSkill.skillData
                    show = listOrSingle(opt.ifSkillData,
                        function(k) return sd and sd[k] end)
                end

                if not show then goto continue end

                local listVals = nil
                if opt.list then
                    listVals = {}
                    for j, item in ipairs(opt.list) do
                        listVals[j] = tostring(item.val) .. "|"
                            .. (item.label and item.label:gsub("%^%x+","") or "")
                    end
                end
                result[i] = {
                    var      = opt.var,
                    varType  = opt.type or "check",
                    label    = opt.label and opt.label:gsub("%^%x+","") or opt.var,
                    tooltip  = type(opt.tooltip) == "string"
                               and opt.tooltip:gsub("%^%x+",""):gsub("\t","  ") or "",
                    curVal   = build.configTab.input[opt.var],
                    listVals = listVals,
                }
                i = i + 1
                ::continue::
            end
            return result
        ''')

        # Group options into categories, skip noise prefixes
        grouped: dict[str, list[ConfigOptionInfo]] = {
            "charges": [], "buffs": [], "enemy": [], "ailments": [],
            "conditions": [], "modes": [], "other": [],
        }
        for raw in config_raw.values():
            var: str = raw["var"]
            # Skip noisy / agent-irrelevant options
            if any(var.lower().startswith(p.lower()) for p in self._CONFIG_SKIP_PREFIXES):
                continue

            label: str = raw["label"]
            cur_val = raw["curVal"]
            # Coerce lupa types
            if cur_val is None:
                cur_val = None
            elif isinstance(cur_val, bool):
                cur_val = bool(cur_val)
            elif isinstance(cur_val, (int, float)):
                cur_val = float(cur_val) if isinstance(cur_val, float) else int(cur_val)
            else:
                cur_val = str(cur_val)

            list_options: list[tuple[str, str]] | None = None
            if raw["listVals"]:
                list_options = []
                for lv in raw["listVals"].values():
                    parts = str(lv).split("|", 1)
                    list_options.append((parts[0], parts[1] if len(parts) > 1 else parts[0]))

            opt = ConfigOptionInfo(
                var=var,
                var_type=raw["varType"],
                label=label,
                tooltip=raw["tooltip"],
                current_value=cur_val,
                list_options=list_options,
            )

            # Assign to category by scanning label + var name
            combined = (var + " " + label).lower()
            category = "other"
            for cat, keywords in self._CONFIG_CATEGORIES:
                if any(kw in combined for kw in keywords):
                    category = cat
                    break
            grouped[category].append(opt)

        # ── Damage type breakdown ─────────────────────────────────
        dmg_raw = self._lua.execute('''
            local o = build.calcsTab.mainOutput
            return {
                Physical  = o.PhysicalStoredCombinedAvg  or 0,
                Fire      = o.FireStoredCombinedAvg       or 0,
                Cold      = o.ColdStoredCombinedAvg       or 0,
                Lightning = o.LightningStoredCombinedAvg  or 0,
                Chaos     = o.ChaosStoredCombinedAvg      or 0,
            }
        ''')
        dmg_total = sum(float(v) for v in dmg_raw.values())
        damage_type_percent: dict[str, float] = {}
        if dmg_total > 0:
            for dtype, val in dmg_raw.items():
                pct = round(float(val) / dmg_total * 100, 1)
                if pct > 0:
                    damage_type_percent[dtype] = pct

        return CombatProfile(
            total_dps=stats.total_dps,
            charges=charges,
            rage_available=rage_available,
            rage_max=rage_max,
            rage_current=rage_current,
            rage_effect_per_stack=rage_effect_per_stack,
            ailments_on_enemy=ailments_on_enemy,
            life=stats.life,
            energy_shield=stats.energy_shield,
            evasion=stats.evasion,
            armour=stats.armour,
            fire_res=stats.fire_res,
            cold_res=stats.cold_res,
            lightning_res=stats.lightning_res,
            chaos_res=stats.chaos_res,
            damage_taken_mults=damage_taken_mults,
            damage_type_percent=damage_type_percent,
            relevant_config=grouped,
        )

    def get_condition_sources(self) -> dict[str, dict]:
        """
        Decode which passive nodes / gems use each condition in the active skill calc.

        Returns a dict keyed by condition var name (e.g. ``"conditionCritRecently"``).
        Each value is a dict with:
        - ``sources``: list of human-readable source names
        - ``auto_applicable``: True if the condition is reliably active in combat
          (e.g. conditionCritRecently when crit chance > 15 %)
        - ``current_value``: the current config value (True/False/None)

        Use this after ``get_combat_profile()`` to understand *why* a condition
        appears in relevant_config and whether toggling it models a realistic scenario.
        """
        self._ensure_build_loaded()

        raw = self._lua.execute('''
            local build = build
            local used = {}

            local env = build.calcsTab.mainEnv
            if not env or not env.conditionsUsed then
                return used
            end

            local passiveSpec = build.spec
            for condName, sources in pairs(env.conditionsUsed) do
                local srcList = {}
                if type(sources) == "table" then
                    -- Each entry is a modifier object with a .source field.
                    -- Collect unique sources to avoid duplicates.
                    local seen = {}
                    for _, mod in ipairs(sources) do
                        local srcStr = (type(mod) == "table" and mod.source) or tostring(mod)
                        if srcStr and not seen[srcStr] then
                            seen[srcStr] = true
                            local resolved = srcStr
                            -- Resolve Tree:NNNN to passive node name
                            local nodeId = srcStr:match("^Tree:(%d+)$")
                            if nodeId and passiveSpec and passiveSpec.nodes then
                                local node = passiveSpec.nodes[tonumber(nodeId)]
                                if node and node.name and node.name ~= "" then
                                    resolved = "Passive: " .. node.name
                                end
                            end
                            -- Prettify Skill: prefix
                            local skillName = srcStr:match("^Skill:(.+)$")
                            if skillName then
                                skillName = skillName:gsub("Player$", "")
                                skillName = skillName:gsub("Support", " (Support)")
                                resolved = "Gem: " .. skillName
                            end
                            -- Prettify Item: prefix  (format: "Item:slotIndex:Name")
                            local itemName = srcStr:match("^Item:%d+:(.+)$")
                            if itemName then
                                resolved = "Item: " .. itemName
                            end
                            srcList[#srcList + 1] = resolved
                        end
                    end
                elseif type(sources) == "string" then
                    srcList[#srcList + 1] = sources
                end
                used[condName] = srcList
            end
            return used
        ''')

        # Also collect multipliers used (for relevant multiplier conditions)
        mult_raw = self._lua.execute('''
            local env = build.calcsTab.mainEnv
            local used = {}
            if env and env.multipliersUsed then
                for multName, _ in pairs(env.multipliersUsed) do
                    used[#used + 1] = multName
                end
            end
            return used
        ''')

        stats = self.get_stats()

        result: dict[str, dict] = {}

        # Process conditions
        if raw is not None:
            for cond_name in raw:
                sources_lua = raw[cond_name]
                sources: list[str] = []
                if sources_lua is not None:
                    for i in range(1, len(sources_lua) + 1):
                        v = sources_lua[i]
                        if v:
                            sources.append(str(v))

                auto = self._is_auto_applicable(cond_name, stats)
                current = self.get_config_option(cond_name)

                result[cond_name] = {
                    "sources": sources,
                    "auto_applicable": auto,
                    "current_value": current,
                }

        # Add multipliers (rage, resonance, etc.) as pseudo-conditions
        if mult_raw is not None:
            for i in range(1, len(mult_raw) + 1):
                mult_name = mult_raw[i]
                if mult_name and str(mult_name) not in result:
                    mult_str = str(mult_name)
                    current = self.get_config_option(mult_str)
                    result[mult_str] = {
                        "sources": ["multiplier"],
                        "auto_applicable": False,
                        "current_value": current,
                    }

        return result

    @staticmethod
    def _is_auto_applicable(cond_name: str, stats: "BuildStats") -> bool:
        """Heuristic: is this condition reliably true in normal combat?"""
        cond = cond_name.lower()
        if "critrecently" in cond:
            # Guaranteed if crit chance > 15 % (hit multiple enemies per second)
            return stats.crit_chance > 15.0
        if "killed" in cond or "killedrecently" in cond:
            return True  # generally true in mapping
        return False

    # ─── Build Reset ──────────────────────────────────────────────

    def new_build(self) -> None:
        """Reset to a fresh empty build."""
        self._lua.execute('''
            newBuild()
        ''')
        self._build_loaded = True

    # ─── Internal Helpers ─────────────────────────────────────────

    def _ensure_build_loaded(self) -> None:
        if not self._build_loaded:
            raise RuntimeError("No build loaded. Call load_build_from_code() or load_build_from_file() first.")

    def _validate_slot(self, slot: str) -> None:
        if slot not in self.SLOT_NAMES:
            raise ValueError(f"Invalid slot '{slot}'. Valid slots: {self.SLOT_NAMES}")

    @staticmethod
    def _decode_share_code(code: str) -> str:
        """Decode a PoB share code (base64url + zlib) → XML string."""
        code = code.strip()
        padding = 4 - len(code) % 4
        if padding != 4:
            code += "=" * padding
        raw = base64.urlsafe_b64decode(code)
        return zlib.decompress(raw).decode("utf-8")
