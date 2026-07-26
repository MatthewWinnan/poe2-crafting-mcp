"""
ETL pipeline — populate SQLite from PoB vendor data.

Usage (one-time setup, re-run after PoB submodule updates):
    nix develop
    PYTHONPATH=src python -m poe2_crafting_mcp.data.etl

The database path defaults to data/poe2_craft.db (relative to repo root),
overridden by the POE2_DB environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "poe2_craft.db"
_DEFAULT_POB = _REPO_ROOT / "vendor" / "PathOfBuilding-PoE2"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_stat_range(text: str) -> tuple[float | None, float | None]:
    """Extract (min, max) numeric values from a stat string like '+(13-16) to Strength'."""
    m = re.search(r"\((-?[\d.]+)-(-?[\d.]+)\)", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(-?[\d.]+)", text)
    if m:
        v = float(m.group(1))
        return v, v
    return None, None


def _lua_table_to_list(tbl) -> list:
    """Convert a lupa Lua array table to a Python list."""
    if tbl is None:
        return []
    result = []
    i = 1
    while True:
        try:
            v = tbl[i]
        except Exception:
            break
        if v is None:
            break
        result.append(v)
        i += 1
    return result


def _lua_keys(tbl) -> list[str]:
    """Iterate all keys from a Lua hash table."""
    if tbl is None:
        return []
    keys = []
    for k in tbl:
        keys.append(k)
    return keys


# ── Schema ────────────────────────────────────────────────────────────────────

def _init_db(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    conn.executescript(schema_path.read_text())
    conn.commit()


def _clear_tables(conn: sqlite3.Connection) -> None:
    for tbl in ("item_bases", "item_mods", "gems", "uniques", "passive_nodes",
                "currencies", "concepts", "item_descriptions"):
        conn.execute(f"DELETE FROM {tbl}")
    # FTS tables need rebuilding
    for fts in ("item_mods_fts", "gems_fts", "uniques_fts", "passive_nodes_fts",
                "concepts_fts", "item_descriptions_fts"):
        conn.execute(f"DELETE FROM {fts}")
    conn.commit()


# ── Item Bases ────────────────────────────────────────────────────────────────

_LUA_EXTRACT_BASES = r"""
local rows = {}
for name, b in pairs(data.itemBases) do
    local tags = {}
    if b.tags then
        for tag, _ in pairs(b.tags) do
            if type(tag) == "string" then tags[#tags+1] = tag end
        end
    end
    local implicits = {}
    if b.implicitModTypes then
        for _, t in ipairs(b.implicitModTypes) do
            if type(t) == "string" then implicits[#implicits+1] = t end
        end
    end
    local req = b.req or {}
    local arm = b.armour or {}
    rows[#rows+1] = {
        tostring(name),
        b.type or "",
        b.subType or "",
        req.level or 0,
        req.str or 0,
        req.dex or 0,
        req["int"] or 0,
        b.socketLimit or 0,
        table.concat(tags, ","),
        table.concat(implicits, ","),
        arm.Armour or arm.armour or 0,
        arm.Evasion or arm.evasion or 0,
        arm.EnergyShield or arm.energyShield or 0,
        arm.Ward or arm.ward or 0,
    }
end
return rows
"""


def _load_bases(conn: sqlite3.Connection, lua) -> int:
    rows_lua = lua.execute(_LUA_EXTRACT_BASES)
    rows = []
    for row_lua in rows_lua.values():
        row = _lua_table_to_list(row_lua)
        if not row:
            continue
        name, slot, sub_type, req_lv, req_str, req_dex, req_int, sock, tags_str, implicits_str, ar, ev, es, ward = row[:14]
        tags_json = json.dumps(tags_str.split(",")) if tags_str else "[]"
        implicits_json = json.dumps(implicits_str.split(",")) if implicits_str else "[]"
        rows.append((str(name), str(slot), str(sub_type) if sub_type else None,
                     int(req_lv), int(req_str), int(req_dex), int(req_int),
                     int(sock), tags_json, implicits_json,
                     int(ar), int(ev), int(es), int(ward)))

    conn.executemany(
        "INSERT OR REPLACE INTO item_bases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Item Mods ─────────────────────────────────────────────────────────────────

_LUA_EXTRACT_MODS = r"""
local rows = {}
for cat, mods in pairs(data.itemMods) do
    if type(mods) == "table" then
        for modId, mod in pairs(mods) do
            if type(mod) == "table" then
                local stat = type(mod[1]) == "string" and mod[1] or ""
                local wkeys = {}
                if mod.weightKey then
                    for _, k in ipairs(mod.weightKey) do
                        if type(k) == "string" then wkeys[#wkeys+1] = k end
                    end
                end
                local wvals = {}
                if mod.weightVal then
                    for _, v in ipairs(mod.weightVal) do
                        wvals[#wvals+1] = tostring(v)
                    end
                end
                local modTags = {}
                if mod.modTags then
                    for _, t in ipairs(mod.modTags) do
                        if type(t) == "string" then modTags[#modTags+1] = t end
                    end
                end
                rows[#rows+1] = {
                    tostring(modId),
                    cat,
                    mod.type or "",
                    mod.affix or "",
                    stat,
                    mod.level or 0,
                    mod.group or "",
                    table.concat(modTags, ","),
                    table.concat(wkeys, ","),
                    table.concat(wvals, ","),
                }
            end
        end
    end
end
return rows
"""


def _load_mods(conn: sqlite3.Connection, lua) -> int:
    rows_lua = lua.execute(_LUA_EXTRACT_MODS)
    rows = []
    for row_lua in rows_lua.values():
        row = _lua_table_to_list(row_lua)
        if not row or len(row) < 10:
            continue
        mod_id, cat, mod_type, affix, stat_text, req_lv, group_name, mod_tags_str, wkeys_str, wvals_str = row[:10]
        stat_min, stat_max = _parse_stat_range(str(stat_text))
        rows.append((
            str(mod_id), str(cat), str(mod_type) or None, str(affix) or None,
            str(stat_text),
            stat_min, stat_max,
            int(req_lv),
            str(group_name) or None,
            json.dumps(mod_tags_str.split(",")) if mod_tags_str else "[]",
            json.dumps(wkeys_str.split(",")) if wkeys_str else "[]",
            json.dumps(wvals_str.split(",")) if wvals_str else "[]",
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO item_mods VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Gems ──────────────────────────────────────────────────────────────────────

_LUA_EXTRACT_GEMS = r"""
local rows = {}
for gemId, gem in pairs(data.gems) do
    if type(gem) == "table" then
        local tags = {}
        if gem.tags then
            for tag, _ in pairs(gem.tags) do
                if type(tag) == "string" then tags[#tags+1] = tag end
            end
        end
        local isSupport = 0
        if gem.tags and (gem.tags.support or gem.tags.grants_support_skill) then
            isSupport = 1
        end
        rows[#rows+1] = {
            tostring(gemId),
            gem.name or "",
            gem.gemType or "",
            isSupport,
            gem.Tier or 0,
            gem.reqStr or 0,
            gem.reqDex or 0,
            gem.reqInt or 0,
            gem.naturalMaxLevel or 20,
            table.concat(tags, ","),
            gem.tagString or "",
            gem.weaponRequirements or "",
        }
    end
end
return rows
"""


def _load_gems(conn: sqlite3.Connection, lua) -> int:
    rows_lua = lua.execute(_LUA_EXTRACT_GEMS)
    rows = []
    for row_lua in rows_lua.values():
        row = _lua_table_to_list(row_lua)
        if not row or len(row) < 12:
            continue
        gem_id, name, gem_type, is_support, tier, req_str, req_dex, req_int, max_lv, tags_str, tag_string, weap_req = row[:12]
        tags_json = json.dumps(tags_str.split(",")) if tags_str else "[]"
        rows.append((
            str(gem_id), str(name), str(gem_type) or None,
            int(is_support), int(tier),
            int(req_str), int(req_dex), int(req_int),
            int(max_lv),
            tags_json, str(tag_string) or None, str(weap_req) or None,
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO gems VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Uniques ───────────────────────────────────────────────────────────────────

_LUA_EXTRACT_UNIQUES = r"""
local rows = {}
for slot, items in pairs(data.uniques) do
    if type(items) == "table" then
        for _, raw in ipairs(items) do
            if type(raw) == "string" then
                rows[#rows+1] = { slot, raw }
            end
        end
    end
end
return rows
"""


def _parse_unique_text(raw: str) -> tuple[str, str, str, str]:
    """Parse name, base_type, source, variants from raw unique text block."""
    lines = raw.strip().splitlines()
    name = lines[0].strip() if lines else "Unknown"
    base_type = lines[1].strip() if len(lines) > 1 else ""
    source = ""
    variants: list[str] = []
    for line in lines[2:]:
        line = line.strip()
        if line.startswith("Source:"):
            source = line[7:].strip()
        elif line.startswith("Variant:"):
            variants.append(line[8:].strip())
    return name, base_type, source, json.dumps(variants) if variants else "[]"


def _load_uniques(conn: sqlite3.Connection, lua) -> int:
    rows_lua = lua.execute(_LUA_EXTRACT_UNIQUES)
    rows = []
    for row_lua in rows_lua.values():
        row = _lua_table_to_list(row_lua)
        if not row or len(row) < 2:
            continue
        slot, raw_text = str(row[0]), str(row[1])
        name, base_type, source, variants = _parse_unique_text(raw_text)
        rows.append((name, slot, base_type or None, source or None, variants, raw_text))

    conn.executemany(
        "INSERT OR REPLACE INTO uniques VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Passive Nodes ─────────────────────────────────────────────────────────────

_LUA_EXTRACT_NODES = r"""
local rows = {}
for nid, node in pairs(build.spec.tree.nodes) do
    local stats = {}
    if node.sd then
        for _, s in ipairs(node.sd) do stats[#stats+1] = s end
    end
    local nodeType = node.type or "Normal"
    if node.isJewelSocket then nodeType = "JewelSocket" end
    if node.classStartIndex then nodeType = "ClassStart" end
    rows[#rows+1] = {
        nid,
        node.name or node.dn or "",
        node.dn or node.name or "",
        nodeType,
        node.ascendancyName or "",
        node.classStartIndex or -1,
        node.isJewelSocket and 1 or 0,
        table.concat(stats, "\n"),
        node.x or 0,
        node.y or 0,
        node.g or 0,
    }
end
return rows
"""


def _load_passive_nodes(conn: sqlite3.Connection, lua) -> int:
    rows_lua = lua.execute(_LUA_EXTRACT_NODES)
    rows = []
    for row_lua in rows_lua.values():
        row = _lua_table_to_list(row_lua)
        if not row or len(row) < 11:
            continue
        nid, name, dn, node_type, asc, class_idx, is_jewel, stats_str, x, y, gid = row[:11]
        stats_list = [s for s in str(stats_str).split("\n") if s.strip()]
        rows.append((
            int(nid),
            str(name) or None,
            str(dn) or None,
            str(node_type),
            str(asc) if asc else None,
            int(class_idx) if int(class_idx) >= 0 else None,
            int(is_jewel),
            json.dumps(stats_list),
            float(x), float(y), int(gid),
        ))

    conn.executemany(
        "INSERT OR REPLACE INTO passive_nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


# ── Currencies ────────────────────────────────────────────────────────────────

def _load_currencies(conn: sqlite3.Connection) -> int:
    from .currencies import CURRENCIES
    conn.executemany(
        "INSERT OR REPLACE INTO currencies VALUES (?,?,?,?,?)",
        CURRENCIES,
    )
    conn.commit()
    return len(CURRENCIES)


# ── Concepts ──────────────────────────────────────────────────────────────────

def _load_concepts(conn: sqlite3.Connection) -> int:
    from .concepts import CONCEPTS
    from .price_db import PriceDatabase
    pdb = PriceDatabase(conn)
    return pdb.upsert_concepts_bulk(CONCEPTS)


# ── Item Descriptions ──────────────────────────────────────────────────────────

def _load_item_descriptions(conn: sqlite3.Connection) -> int:
    from .item_descriptions import ITEM_DESCRIPTIONS
    from .price_db import PriceDatabase
    pdb = PriceDatabase(conn)
    return pdb.upsert_item_descs_bulk(ITEM_DESCRIPTIONS)


# ── FTS Rebuild ───────────────────────────────────────────────────────────────

def _rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO item_mods_fts(item_mods_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO gems_fts(gems_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO uniques_fts(uniques_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO passive_nodes_fts(passive_nodes_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO concepts_fts(concepts_fts) VALUES ('rebuild')")
    conn.execute("INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES ('rebuild')")
    conn.commit()


# ── Main entry point ──────────────────────────────────────────────────────────

def run(pob_path: Path | None = None, db_path: Path | None = None,
        build_fixture: Path | None = None) -> dict[str, int]:
    """
    Run the full ETL.

    Args:
        pob_path:      Path to PoB-PoE2 repo. Defaults to vendor/PathOfBuilding-PoE2.
        db_path:       SQLite file path. Defaults to data/poe2_craft.db.
        build_fixture: Build file to load (needed for passive tree). Defaults to
                       data/builds/martial_artist.txt.

    Returns:
        Row counts by table name.
    """
    from poe2_crafting_mcp.engine.pob_engine import PoBEngine

    pob_path = pob_path or Path(os.environ.get("POB_PATH", _DEFAULT_POB))
    db_path = db_path or Path(os.environ.get("POE2_DB", _DEFAULT_DB))
    build_fixture = build_fixture or (_REPO_ROOT / "data" / "builds" / "martial_artist.txt")

    log.info("Booting PoB engine from %s", pob_path)
    engine = PoBEngine(pob_path)

    log.info("Loading build fixture for passive tree access: %s", build_fixture)
    engine.load_build_from_file(build_fixture)

    lua = engine._lua

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    log.info("Initialising schema in %s", db_path)
    _init_db(conn)
    _clear_tables(conn)

    counts: dict[str, int] = {}

    log.info("Loading item bases…")
    counts["item_bases"] = _load_bases(conn, lua)
    log.info("  %d rows", counts["item_bases"])

    log.info("Loading item mods…")
    counts["item_mods"] = _load_mods(conn, lua)
    log.info("  %d rows", counts["item_mods"])

    log.info("Loading gems…")
    counts["gems"] = _load_gems(conn, lua)
    log.info("  %d rows", counts["gems"])

    log.info("Loading uniques…")
    counts["uniques"] = _load_uniques(conn, lua)
    log.info("  %d rows", counts["uniques"])

    log.info("Loading passive nodes…")
    counts["passive_nodes"] = _load_passive_nodes(conn, lua)
    log.info("  %d rows", counts["passive_nodes"])

    log.info("Loading currencies…")
    counts["currencies"] = _load_currencies(conn)
    log.info("  %d rows", counts["currencies"])

    log.info("Loading concepts…")
    counts["concepts"] = _load_concepts(conn)
    log.info("  %d rows", counts["concepts"])

    log.info("Loading item descriptions…")
    counts["item_descriptions"] = _load_item_descriptions(conn)
    log.info("  %d rows", counts["item_descriptions"])

    log.info("Rebuilding FTS indexes…")
    _rebuild_fts(conn)

    # Record the run
    conn.execute(
        "INSERT INTO etl_runs (pob_version, row_counts) VALUES (?, ?)",
        (str(getattr(lua.eval("launch"), "versionNumber", "unknown")),
         json.dumps(counts)),
    )
    conn.commit()
    conn.close()

    log.info("ETL complete: %s", counts)
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
