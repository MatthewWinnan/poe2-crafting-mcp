"""
Read-only query interface for the PoE2 SQLite database.

All methods return plain Python dicts/lists — no SQLite types leak out.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "poe2_craft.db"


class PoBDatabase:
    """Thin read-only wrapper around the ETL-populated SQLite database."""

    def __init__(self, db_path: Path | str | None = None):
        path = db_path or os.environ.get("POE2_DB", _DEFAULT_DB)
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(
                f"Database not found at {self._path}. Run: python -m poe2_crafting_mcp.data.etl"
            )
        self._conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True,
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    # ── Item Bases ────────────────────────────────────────────────────────────

    def search_bases(
        self,
        slot: str = "",
        sub_type: str = "",
        min_level: int = 0,
        max_level: int = 100,
        limit: int = 50,
    ) -> list[dict]:
        """
        Find item bases by slot, sub-type, and level range.

        Args:
            slot:      e.g. "Gloves", "Ring", "Body Armour", "Weapon"
            sub_type:  e.g. "Armour", "Evasion", "ES", "Hybrid"
            min_level: minimum required level (inclusive)
            max_level: maximum required level (inclusive)
            limit:     max rows returned

        Returns:
            List of dicts with keys: name, slot, sub_type, req_level,
            req_str, req_dex, req_int, socket_limit, tags,
            armour, evasion, energy_shield, ward.
        """
        q = "SELECT * FROM item_bases WHERE req_level BETWEEN ? AND ?"
        params: list = [min_level, max_level]
        if slot:
            q += " AND slot LIKE ?"
            params.append(f"%{slot}%")
        if sub_type:
            q += " AND sub_type LIKE ?"
            params.append(f"%{sub_type}%")
        q += " ORDER BY req_level, name LIMIT ?"
        params.append(limit)
        return [_row_to_dict(r) for r in self._conn.execute(q, params)]

    # ── Item Mods ─────────────────────────────────────────────────────────────

    def search_mods(
        self,
        keyword: str = "",
        item_tag: str = "",
        category: str = "Item",
        mod_type: str = "",
        min_level: int = 0,
        max_level: int = 100,
        limit: int = 30,
    ) -> list[dict]:
        """
        Search explicit mods by stat keyword, item tag, and category.

        Args:
            keyword:   Full-text search term in stat_text / affix
                       (e.g. "lightning damage", "critical", "life").
            item_tag:  Filter mods by weight_keys containing this tag
                       (e.g. "gloves", "ring", "staff", "str_armour").
            category:  "Item" (default), "Jewel", "Runes", "Corruption",
                       "Desecrated", "Flask", "Charm".
            mod_type:  "Prefix" or "Suffix" (blank = both).
            min_level: minimum ilvl to consider (req_level).
            max_level: maximum ilvl.
            limit:     max rows returned.

        Returns:
            List of dicts with keys: id, category, mod_type, affix,
            stat_text, stat_min, stat_max, req_level, group_name,
            mod_tags, weight_keys, weight_vals.
        """
        if keyword:
            # FTS search
            fts_q = """
                SELECT m.* FROM item_mods m
                JOIN item_mods_fts f ON m.rowid = f.rowid
                WHERE item_mods_fts MATCH ?
                  AND m.category = ?
                  AND m.req_level BETWEEN ? AND ?
            """
            params: list = [keyword, category, min_level, max_level]
        else:
            fts_q = """
                SELECT * FROM item_mods
                WHERE category = ? AND req_level BETWEEN ? AND ?
            """
            params = [category, min_level, max_level]

        if mod_type:
            fts_q += " AND mod_type = ?"
            params.append(mod_type)
        if item_tag:
            fts_q += " AND weight_keys LIKE ?"
            params.append(f"%{item_tag}%")
        fts_q += " ORDER BY req_level DESC LIMIT ?"
        params.append(limit)

        rows = [_row_to_dict(r) for r in self._conn.execute(fts_q, params)]

        # Post-filter: only mods with non-zero weight for the requested tag
        if item_tag:
            rows = _filter_by_tag_weight(rows, item_tag)

        return rows

    def get_mod(self, mod_id: str, category: str = "Item") -> dict | None:
        """Fetch a single mod by its PoB ID."""
        row = self._conn.execute(
            "SELECT * FROM item_mods WHERE id = ? AND category = ?",
            (mod_id, category),
        ).fetchone()
        return _row_to_dict(row) if row else None

    # ── Gems ──────────────────────────────────────────────────────────────────

    def search_gems(
        self,
        keyword: str = "",
        gem_type: str = "",
        is_support: bool | None = None,
        tag: str = "",
        limit: int = 30,
    ) -> list[dict]:
        """
        Search gems by name, type, or tag.

        Args:
            keyword:    FTS keyword in name/tags (e.g. "lightning", "strike").
            gem_type:   "Attack", "Spell", "Support", "" (any).
            is_support: True/False/None (any).
            tag:        Filter by tag string (e.g. "cold", "aoe", "channelling").
            limit:      max rows.
        """
        if keyword:
            q = """
                SELECT g.* FROM gems g
                JOIN gems_fts f ON g.rowid = f.rowid
                WHERE gems_fts MATCH ?
            """
            params: list = [keyword]
        else:
            q = "SELECT * FROM gems WHERE 1=1"
            params = []

        if gem_type:
            q += " AND gem_type = ?"
            params.append(gem_type)
        if is_support is not None:
            q += " AND is_support = ?"
            params.append(1 if is_support else 0)
        if tag:
            q += " AND (tags LIKE ? OR tag_string LIKE ?)"
            params.extend([f"%{tag}%", f"%{tag}%"])
        q += " ORDER BY name LIMIT ?"
        params.append(limit)

        return [_row_to_dict(r) for r in self._conn.execute(q, params)]

    def get_gem(self, name: str) -> dict | None:
        """Fetch a gem by exact name."""
        row = self._conn.execute(
            "SELECT * FROM gems WHERE name = ?", (name,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    # ── Uniques ───────────────────────────────────────────────────────────────

    def search_uniques(
        self,
        slot: str = "",
        keyword: str = "",
        base_type: str = "",
        limit: int = 30,
    ) -> list[dict]:
        """
        Search unique items.

        Args:
            slot:      PoB slot key (e.g. "gloves", "ring", "weapon1").
            keyword:   FTS search in name/raw_text (e.g. "lightning", "rage").
            base_type: Filter by base type name.
            limit:     max rows.
        """
        if keyword:
            q = """
                SELECT u.* FROM uniques u
                JOIN uniques_fts f ON u.rowid = f.rowid
                WHERE uniques_fts MATCH ?
            """
            params: list = [keyword]
        else:
            q = "SELECT * FROM uniques WHERE 1=1"
            params = []

        if slot:
            q += " AND slot LIKE ?"
            params.append(f"%{slot}%")
        if base_type:
            q += " AND base_type LIKE ?"
            params.append(f"%{base_type}%")
        q += " ORDER BY name LIMIT ?"
        params.append(limit)

        return [_row_to_dict(r) for r in self._conn.execute(q, params)]

    # ── Passive Nodes ─────────────────────────────────────────────────────────

    def search_passive_nodes(
        self,
        keyword: str = "",
        node_type: str = "",
        ascendancy: str = "",
        class_start: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Search passive tree nodes.

        Args:
            keyword:     FTS search in name/stats (e.g. "critical", "lightning damage").
            node_type:   "Notable", "Keystone", "Normal", "JewelSocket", "ClassStart".
            ascendancy:  Ascendancy name filter (e.g. "Invoker", "Warbringer").
            class_start: Class start index (0=Warrior, 1=Ranger, 2=Witch, 3=Duelist,
                         4=Templar, 5=Shadow, 6=Scion, or PoE2 equivalents).
            limit:       max rows.

        Returns:
            List of dicts with keys: node_id, name, display_name, node_type,
            ascendancy, class_start_index, is_jewel_socket, stats, x, y, group_id.
        """
        if keyword:
            q = """
                SELECT n.* FROM passive_nodes n
                JOIN passive_nodes_fts f ON n.rowid = f.rowid
                WHERE passive_nodes_fts MATCH ?
            """
            params: list = [keyword]
        else:
            q = "SELECT * FROM passive_nodes WHERE 1=1"
            params = []

        if node_type:
            q += " AND node_type = ?"
            params.append(node_type)
        if ascendancy:
            q += " AND ascendancy LIKE ?"
            params.append(f"%{ascendancy}%")
        if class_start is not None:
            q += " AND class_start_index = ?"
            params.append(class_start)
        q += " ORDER BY node_type, name LIMIT ?"
        params.append(limit)

        return [_row_to_dict(r) for r in self._conn.execute(q, params)]

    def get_passive_node(self, node_id: int) -> dict | None:
        """Fetch a single passive node by ID."""
        row = self._conn.execute(
            "SELECT * FROM passive_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    # ── Currencies ────────────────────────────────────────────────────────────

    def search_currencies(
        self,
        category: str = "",
        keyword: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """
        List currencies, optionally filtered by category or keyword.

        Args:
            category: "Orb", "Essence", "Rune", "SoulCore", "Distilled",
                      "Fragment", "Catalyst", "Quality", "Other".
            keyword:  substring search in name/effect.
            limit:    max rows.
        """
        q = "SELECT * FROM currencies WHERE 1=1"
        params: list = []
        if category:
            q += " AND category = ?"
            params.append(category)
        if keyword:
            q += " AND (name LIKE ? OR effect LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        q += " ORDER BY category, name LIMIT ?"
        params.append(limit)
        return [_row_to_dict(r) for r in self._conn.execute(q, params)]

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, int]:
        """Return row counts for all tables."""
        tables = ["item_bases", "item_mods", "gems", "uniques", "passive_nodes", "currencies"]
        return {t: self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row | None) -> dict:
    if row is None:
        return {}
    d = dict(row)
    # Deserialise JSON columns
    for k in ("tags", "implicit_mod_types", "mod_tags", "weight_keys", "weight_vals", "stats", "variants"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _filter_by_tag_weight(rows: list[dict], tag: str) -> list[dict]:
    """Keep only rows where the given tag has a non-zero weight."""
    filtered = []
    for row in rows:
        keys = row.get("weight_keys") or []
        vals = row.get("weight_vals") or []
        try:
            idx = keys.index(tag)
            if idx < len(vals) and int(float(vals[idx])) > 0:
                filtered.append(row)
        except (ValueError, IndexError, TypeError):
            # Tag not in weight_keys — include by default (may be broadly applicable)
            filtered.append(row)
    return filtered
