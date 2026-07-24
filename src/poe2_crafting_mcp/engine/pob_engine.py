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

from .models import BuildInfo, BuildStats, DPSDelta, EquippedItem

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
                Life = o.Life or 0,
                EnergyShield = o.EnergyShield or 0,
                Mana = o.Mana or 0,
                Evasion = o.Evasion or 0,
                Armour = o.Armour or 0,
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
            life=raw["Life"],
            energy_shield=raw["EnergyShield"],
            mana=raw["Mana"],
            evasion=raw["Evasion"],
            armour=raw["Armour"],
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
            return {
                className = b.spec.curClassName or "",
                ascendancy = b.spec.curAscendClassName or "",
                level = b.characterLevel or 0,
                mainSkill = mainSkill,
            }
        ''')

        return BuildInfo(
            class_name=raw["className"],
            ascendancy=raw["ascendancy"],
            level=raw["level"],
            main_skill=raw["mainSkill"],
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
                    explicit_mods=list(raw["explicits"].values()) if raw["explicits"] else [],
                    implicit_mods=list(raw["implicits"].values()) if raw["implicits"] else [],
                    raw_text=raw["raw"],
                )
            else:
                items[slot] = None

        return items

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
