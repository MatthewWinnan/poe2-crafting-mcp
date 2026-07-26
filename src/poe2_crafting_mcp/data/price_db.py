"""
SQLite price cache — read/write access to the prices and economy_meta tables.

Uses a separate read-write connection to poe2_craft.db alongside the existing
read-only PoBDatabase connection.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "poe2_craft.db"
_DEFAULT_TTL = 3600        # 1 hour in seconds
_ETL_STALE_DAYS = 7        # warn if ETL is older than this


class PriceDatabase:
    """
    Read-write cache for poe.ninja prices stored in poe2_craft.db.

    The prices and economy_meta tables are created lazily on first use —
    no ETL run required. The main ETL tables are never modified here.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        path = db_path or os.environ.get("POE2_DB", _DEFAULT_DB)
        self._path = Path(path)
        self._ttl = int(os.environ.get("POE2_PRICE_TTL", _DEFAULT_TTL))
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create prices + economy_meta + trade_stats if missing (idempotent)."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS prices (
                name          TEXT NOT NULL,
                category      TEXT NOT NULL,
                league        TEXT NOT NULL,
                chaos_value   REAL,
                divine_value  REAL,
                listing_count INTEGER,
                fetched_at    TEXT NOT NULL,
                PRIMARY KEY (name, category, league)
            );
            CREATE INDEX IF NOT EXISTS idx_prices_league
                ON prices(league);
            CREATE INDEX IF NOT EXISTS idx_prices_category
                ON prices(category);
            CREATE TABLE IF NOT EXISTS economy_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS trade_stats (
                stat_id    TEXT PRIMARY KEY,
                stat_text  TEXT NOT NULL,
                stat_type  TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trade_stats_type
                ON trade_stats(stat_type);
            CREATE VIRTUAL TABLE IF NOT EXISTS trade_stats_fts USING fts5(
                stat_id, stat_text,
                content='trade_stats',
                tokenize='unicode61'
            );
            CREATE TABLE IF NOT EXISTS concepts (
                name            TEXT PRIMARY KEY,
                category        TEXT NOT NULL,
                summary         TEXT NOT NULL DEFAULT '',
                mechanics       TEXT NOT NULL DEFAULT '',
                formula         TEXT NOT NULL DEFAULT '',
                see_also        TEXT NOT NULL DEFAULT '[]',
                source          TEXT NOT NULL DEFAULT 'manual',
                league_version  TEXT,
                updated_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_concepts_category ON concepts(category);
            CREATE INDEX IF NOT EXISTS idx_concepts_source   ON concepts(source);
            CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts USING fts5(
                name, category, summary, mechanics,
                content='concepts',
                tokenize='unicode61'
            );
            CREATE TABLE IF NOT EXISTS item_descriptions (
                name            TEXT PRIMARY KEY,
                category        TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                crafting_notes  TEXT NOT NULL DEFAULT '',
                drop_notes      TEXT NOT NULL DEFAULT '',
                see_also        TEXT NOT NULL DEFAULT '[]',
                source          TEXT NOT NULL DEFAULT 'manual',
                league_version  TEXT,
                updated_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_item_desc_category
                ON item_descriptions(category);
            CREATE INDEX IF NOT EXISTS idx_item_desc_source
                ON item_descriptions(source);
            CREATE VIRTUAL TABLE IF NOT EXISTS item_descriptions_fts USING fts5(
                name, category, description, crafting_notes,
                content='item_descriptions',
                tokenize='unicode61'
            );
        """)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _age_seconds(iso: str) -> float:
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds()
        except Exception:
            return float("inf")

    # ── Economy Meta ──────────────────────────────────────────────────────────

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM economy_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO economy_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def get_active_league(self) -> str | None:
        return self.get_meta("active_league")

    def set_active_league(self, league: str) -> None:
        self.set_meta("active_league", league)

    # ── Price Cache Reads ─────────────────────────────────────────────────────

    def get_price(self, name: str, league: str, category: str = "") -> dict | None:
        """
        Return a single cached price row, or None if not in cache.

        If category is omitted, returns the highest-listing-count match.
        """
        if category:
            row = self._conn.execute(
                "SELECT * FROM prices WHERE name = ? AND league = ? AND category = ?",
                (name, league, category),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM prices WHERE name = ? AND league = ?"
                " ORDER BY listing_count DESC LIMIT 1",
                (name, league),
            ).fetchone()
        return dict(row) if row else None

    def search_prices(
        self,
        keyword: str,
        league: str,
        category: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """Return price rows whose name contains keyword (case-insensitive)."""
        pattern = f"%{keyword}%"
        if category:
            rows = self._conn.execute(
                "SELECT * FROM prices WHERE name LIKE ? AND league = ? AND category = ?"
                " ORDER BY listing_count DESC LIMIT ?",
                (pattern, league, category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM prices WHERE name LIKE ? AND league = ?"
                " ORDER BY listing_count DESC LIMIT ?",
                (pattern, league, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_bulk_prices(self, category: str, league: str) -> list[dict]:
        """Return all cached prices for a category, sorted by listing count."""
        rows = self._conn.execute(
            "SELECT * FROM prices WHERE category = ? AND league = ?"
            " ORDER BY listing_count DESC",
            (category, league),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Price Cache Writes ────────────────────────────────────────────────────

    def upsert_prices(self, rows: list[dict], league: str) -> int:
        """
        Bulk insert/replace price rows.

        Each row must have: name, category, chaos_value, divine_value, listing_count.
        Returns the number of rows written.
        """
        now = self._now_iso()
        self._conn.executemany(
            """INSERT OR REPLACE INTO prices
               (name, category, league, chaos_value, divine_value, listing_count, fetched_at)
               VALUES (:name, :category, :league, :chaos_value, :divine_value,
                       :listing_count, :fetched_at)""",
            [{**r, "league": league, "fetched_at": now} for r in rows],
        )
        self._conn.commit()
        self.set_meta("prices_fetched_at", now)
        return len(rows)

    def fill_chaos_from_divine(self, league: str) -> int:
        """
        Fill chaos_value for rows that have divine_value but not chaos_value.

        Uses the stored Divine Orb chaos value (1 divine = N chaos) as the
        conversion rate. Called after upserting exchange items whose prices are
        expressed in divine orbs (Runes, Essences, Soul Cores, etc.).

        Returns number of rows updated.
        """
        row = self._conn.execute(
            "SELECT chaos_value FROM prices"
            " WHERE name = 'Divine Orb' AND league = ? AND category = 'currency'",
            (league,),
        ).fetchone()
        if not row or not row["chaos_value"]:
            return 0
        chaos_per_divine = row["chaos_value"]
        cur = self._conn.execute(
            "UPDATE prices SET chaos_value = ROUND(divine_value * ?, 4)"
            " WHERE league = ? AND chaos_value IS NULL AND divine_value IS NOT NULL",
            (chaos_per_divine, league),
        )
        self._conn.commit()
        return cur.rowcount

    def fill_divine_values(self, league: str) -> None:
        """
        Back-fill divine_value for currency rows that have None.

        Uses the Divine Orb chaos value as the conversion rate.
        Called after upsert_prices() for currency rows.
        """
        row = self._conn.execute(
            "SELECT chaos_value FROM prices"
            " WHERE name = 'Divine Orb' AND league = ? AND category = 'currency'",
            (league,),
        ).fetchone()
        if not row or not row["chaos_value"]:
            return
        divine_rate = row["chaos_value"]
        self._conn.execute(
            "UPDATE prices SET divine_value = ROUND(chaos_value / ?, 2)"
            " WHERE league = ? AND divine_value IS NULL AND chaos_value IS NOT NULL",
            (divine_rate, league),
        )
        self._conn.commit()

    # ── Staleness / Status ────────────────────────────────────────────────────

    def _prices_snapshot(self) -> tuple[str | None, float]:
        """Return (league, age_seconds) of the most recent price entry."""
        row = self._conn.execute(
            "SELECT league, fetched_at FROM prices ORDER BY fetched_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None, float("inf")
        return row["league"], self._age_seconds(row["fetched_at"])

    def price_cache_status(self, active_league: str) -> dict:
        """
        Return a status dict for the price cache.

        status values: "fresh" | "stale_ttl" | "stale_league" | "missing"
        """
        prices_league, age_s = self._prices_snapshot()
        age_min = age_s / 60 if age_s < float("inf") else None

        if prices_league is None:
            status = "missing"
        elif prices_league != active_league:
            status = "stale_league"
        elif age_s > self._ttl:
            status = "stale_ttl"
        else:
            status = "fresh"

        return {
            "league": prices_league,
            "age_minutes": round(age_min, 1) if age_min is not None else None,
            "status": status,
        }

    def etl_status(self, active_league: str) -> dict:
        """
        Return a status dict for the ETL game-data freshness.

        status values: "fresh" | "stale_age" | "stale_league" | "never_run"
        """
        etl_league = self.get_meta("etl_league")
        etl_ran_at = self.get_meta("etl_ran_at")

        # Fall back to the etl_runs table if economy_meta hasn't been populated
        if not etl_ran_at:
            row = self._conn.execute(
                "SELECT ran_at FROM etl_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                etl_ran_at = row["ran_at"]

        age_days: float | None = None
        if etl_ran_at:
            age_days = round(self._age_seconds(etl_ran_at) / 86400, 1)

        if etl_ran_at is None:
            status = "never_run"
        elif etl_league and etl_league != active_league:
            status = "stale_league"
        elif age_days is not None and age_days > _ETL_STALE_DAYS:
            status = "stale_age"
        else:
            status = "fresh"

        return {
            "league": etl_league,
            "age_days": age_days,
            "status": status,
        }

    # ── Trade Stat Cache ───────────────────────────────────────────────────────

    def upsert_trade_stats(self, rows: list[dict]) -> int:
        """
        Bulk insert/replace trade stat entries.

        Each row: {stat_id, stat_text, stat_type}.
        Also rebuilds the FTS index after upsert.
        Returns number of rows written.
        """
        now = self._now_iso()
        self._conn.executemany(
            "INSERT OR REPLACE INTO trade_stats (stat_id, stat_text, stat_type, fetched_at)"
            " VALUES (:stat_id, :stat_text, :stat_type, :fetched_at)",
            [{**r, "fetched_at": now} for r in rows],
        )
        # Rebuild FTS content table
        self._conn.execute("INSERT INTO trade_stats_fts(trade_stats_fts) VALUES('rebuild')")
        self._conn.commit()
        self.set_meta("trade_stats_fetched_at", now)
        return len(rows)

    def search_trade_stats(
        self,
        keyword: str,
        stat_type: str = "",
        limit: int = 10,
        prefer_local: bool = False,
    ) -> list[dict]:
        """
        FTS search for trade stat IDs matching a keyword.

        stat_type: filter by type — "explicit", "implicit", "pseudo", etc.
        prefer_local: if True, sort results so "(Local)" stat variants rank first.
            Use this when searching for armour/weapon stats (e.g. flat ES on gloves).
        Returns [{stat_id, stat_text, stat_type}] ordered by relevance.
        """
        safe_kw = keyword.replace('"', '""')
        if stat_type:
            rows = self._conn.execute(
                "SELECT t.stat_id, t.stat_text, t.stat_type"
                " FROM trade_stats_fts f"
                " JOIN trade_stats t ON t.stat_id = f.stat_id"
                " WHERE f.stat_text MATCH ? AND t.stat_type = ?"
                " ORDER BY rank LIMIT ?",
                (safe_kw, stat_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT t.stat_id, t.stat_text, t.stat_type"
                " FROM trade_stats_fts f"
                " JOIN trade_stats t ON t.stat_id = f.stat_id"
                " WHERE f.stat_text MATCH ?"
                " ORDER BY rank LIMIT ?",
                (safe_kw, limit),
            ).fetchall()
        results = [dict(r) for r in rows]
        if prefer_local:
            # Also do a targeted search for the "(Local)" variant of this stat —
            # it's often ranked lower by FTS but is the correct one for armour pieces.
            local_kw = f"{safe_kw} Local"
            local_rows = self._conn.execute(
                "SELECT t.stat_id, t.stat_text, t.stat_type"
                " FROM trade_stats_fts f"
                " JOIN trade_stats t ON t.stat_id = f.stat_id"
                " WHERE f.stat_text MATCH ? AND t.stat_type = 'explicit'"
                " ORDER BY rank LIMIT ?",
                (local_kw, limit),
            ).fetchall()
            local_results = [dict(r) for r in local_rows]
            # Merge: put (Local) explicit hits first, then deduplicate
            seen_ids = {r["stat_id"] for r in local_results}
            merged = local_results + [r for r in results if r["stat_id"] not in seen_ids]
            return merged[:limit]
        return results

    def get_trade_stat(self, stat_id: str) -> dict | None:
        """Exact lookup by stat_id."""
        row = self._conn.execute(
            "SELECT stat_id, stat_text, stat_type FROM trade_stats WHERE stat_id = ?",
            (stat_id,),
        ).fetchone()
        return dict(row) if row else None

    def trade_stats_count(self) -> int:
        """Return number of cached trade stat entries."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM trade_stats").fetchone()
        return row["n"] if row else 0

    def trade_stats_fetched_at(self) -> str | None:
        """Return ISO datetime of last trade stats fetch, or None."""
        return self.get_meta("trade_stats_fetched_at")

    # ── Concepts ───────────────────────────────────────────────────────────────

    def upsert_concept(
        self,
        name: str,
        category: str,
        summary: str,
        mechanics: str,
        formula: str = "",
        see_also: list[str] | None = None,
        source: str = "manual",
        league_version: str | None = None,
    ) -> None:
        """Insert or replace a single concept entry and rebuild FTS."""
        import json as _json
        now = self._now_iso()
        self._conn.execute(
            """INSERT OR REPLACE INTO concepts
               (name, category, summary, mechanics, formula, see_also,
                source, league_version, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, summary, mechanics, formula,
             _json.dumps(see_also or []), source, league_version, now),
        )
        self._conn.execute("INSERT INTO concepts_fts(concepts_fts) VALUES('rebuild')")
        self._conn.commit()

    def upsert_concepts_bulk(self, concepts: list[dict], overwrite: bool = True) -> int:
        """
        Bulk insert/replace concept entries from a list of dicts.

        Each dict must have: name, category, summary, mechanics.
        Optional: formula, see_also (list), source, league_version.
        Also records concepts_seeded_at in economy_meta.

        Args:
            concepts: list of concept dicts
            overwrite: if True (default for ETL), replaces all rows including
                       wiki-sourced ones. If False (used by concept-refresh CLI),
                       only inserts missing rows — wiki-sourced data is preserved.
        Returns number of rows written.
        """
        import json as _json
        now = self._now_iso()
        rows = [
            (
                c["name"], c["category"],
                c.get("summary", ""), c.get("mechanics", ""),
                c.get("formula", ""),
                _json.dumps(c.get("see_also", [])),
                c.get("source", "manual"),
                c.get("league_version"),
                now,
            )
            for c in concepts
        ]
        if overwrite:
            sql = """INSERT OR REPLACE INTO concepts
                     (name, category, summary, mechanics, formula, see_also,
                      source, league_version, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        else:
            # Preserve wiki-sourced rows; only overwrite manual/PoB-sourced ones
            sql = """INSERT INTO concepts
                     (name, category, summary, mechanics, formula, see_also,
                      source, league_version, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT(name) DO UPDATE SET
                       category=excluded.category, summary=excluded.summary,
                       mechanics=excluded.mechanics, formula=excluded.formula,
                       see_also=excluded.see_also, source=excluded.source,
                       league_version=excluded.league_version, updated_at=excluded.updated_at
                     WHERE source != 'poe2wiki'"""
        self._conn.executemany(sql, rows)
        self._conn.execute("INSERT INTO concepts_fts(concepts_fts) VALUES('rebuild')")
        self._conn.commit()
        self.set_meta("concepts_seeded_at", now)
        self.set_meta("concepts_seed_count", str(len(rows)))
        return len(rows)

    def search_concepts(
        self,
        keyword: str = "",
        category: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """
        FTS search across concept name, category, summary, mechanics.

        Falls back to LIKE scan if FTS index is empty or keyword is blank.
        Returns list of concept dicts.
        """
        import json as _json

        def _row_to_dict(row) -> dict:
            d = dict(row)
            try:
                d["see_also"] = _json.loads(d.get("see_also") or "[]")
            except Exception:
                d["see_also"] = []
            return d

        # Blank keyword → return by category (or all)
        if not keyword:
            if category:
                rows = self._conn.execute(
                    "SELECT * FROM concepts WHERE category = ? ORDER BY name LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM concepts ORDER BY name LIMIT ?", (limit,)
                ).fetchall()
            return [_row_to_dict(r) for r in rows]

        # FTS5 with prefix matching — "desecrat*" finds "desecrated", "desecrates" etc.
        # We try exact phrase first, then prefix, then LIKE stem fallback.
        safe_kw = keyword.replace('"', '""')
        fts_kw = safe_kw + "*"  # prefix match

        def _like_fallback() -> list:
            # Truncate to a common stem (drop up to 3 trailing chars) for LIKE
            stem = keyword[:max(4, len(keyword) - 2)] if len(keyword) > 4 else keyword
            pat = f"%{stem}%"
            if category:
                return self._conn.execute(
                    "SELECT * FROM concepts"
                    " WHERE (name LIKE ? OR summary LIKE ? OR mechanics LIKE ?)"
                    " AND category = ? LIMIT ?",
                    (pat, pat, pat, category, limit),
                ).fetchall()
            return self._conn.execute(
                "SELECT * FROM concepts"
                " WHERE name LIKE ? OR summary LIKE ? OR mechanics LIKE ?"
                " LIMIT ?",
                (pat, pat, pat, limit),
            ).fetchall()

        try:
            if category:
                rows = self._conn.execute(
                    "SELECT c.* FROM concepts_fts f"
                    " JOIN concepts c ON c.name = f.name"
                    " WHERE f.concepts_fts MATCH ? AND c.category = ?"
                    " ORDER BY rank LIMIT ?",
                    (fts_kw, category, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT c.* FROM concepts_fts f"
                    " JOIN concepts c ON c.name = f.name"
                    " WHERE f.concepts_fts MATCH ?"
                    " ORDER BY rank LIMIT ?",
                    (fts_kw, limit),
                ).fetchall()
        except Exception:
            rows = []

        if not rows:
            rows = _like_fallback()

        return [_row_to_dict(r) for r in rows]

    def get_concept(self, name: str) -> dict | None:
        """Exact concept lookup by name (case-insensitive)."""
        import json as _json
        row = self._conn.execute(
            "SELECT * FROM concepts WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["see_also"] = _json.loads(d.get("see_also") or "[]")
        except Exception:
            d["see_also"] = []
        return d

    def delete_concept(self, name: str) -> bool:
        """Delete a concept by exact name. Returns True if a row was deleted."""
        cur = self._conn.execute(
            "DELETE FROM concepts WHERE lower(name) = lower(?)", (name,)
        )
        self._conn.execute("INSERT INTO concepts_fts(concepts_fts) VALUES('rebuild')")
        self._conn.commit()
        return cur.rowcount > 0

    def concept_status(self) -> dict:
        """
        Return freshness info for the concepts table.

        status values:
          "never_seeded" — ETL has never seeded concepts
          "stale"        — seeded more than 30 days ago
          "fresh"        — seeded within 30 days
        """
        _CONCEPT_STALE_DAYS = 30
        seeded_at = self.get_meta("concepts_seeded_at")
        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM concepts"
            ).fetchone()[0]
            manual = self._conn.execute(
                "SELECT COUNT(*) FROM concepts WHERE source = 'manual'"
            ).fetchone()[0]
        except Exception:
            total = 0
            manual = 0

        age_days: float | None = None
        if seeded_at:
            age_days = round(self._age_seconds(seeded_at) / 86400, 1)

        if not seeded_at or total == 0:
            status = "never_seeded"
        elif age_days is not None and age_days > _CONCEPT_STALE_DAYS:
            status = "stale"
        else:
            status = "fresh"

        return {
            "status":      status,
            "seeded_at":   seeded_at,
            "total":       total,
            "manual":      manual,
            "age_days":    age_days,
        }

    # ── Item Descriptions ──────────────────────────────────────────────────────

    def upsert_item_desc(
        self,
        name: str,
        category: str,
        description: str = "",
        crafting_notes: str = "",
        drop_notes: str = "",
        see_also: list[str] | None = None,
        source: str = "manual",
        league_version: str | None = None,
    ) -> None:
        """Insert or replace a single item description and rebuild FTS."""
        import json as _json
        now = self._now_iso()
        self._conn.execute(
            """INSERT OR REPLACE INTO item_descriptions
               (name, category, description, crafting_notes, drop_notes,
                see_also, source, league_version, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, description, crafting_notes, drop_notes,
             _json.dumps(see_also or []), source, league_version, now),
        )
        self._conn.execute(
            "INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES('rebuild')"
        )
        self._conn.commit()

    def upsert_item_descs_bulk(self, items: list[dict]) -> int:
        """
        Bulk insert/replace item description entries from a list of dicts.

        Each dict must have: name, category.
        Optional: description, crafting_notes, drop_notes, see_also (list),
                  source, league_version.
        Records item_descs_seeded_at in economy_meta.
        Returns number of rows written.
        """
        import json as _json
        now = self._now_iso()
        rows = [
            (
                item["name"], item["category"],
                item.get("description", ""),
                item.get("crafting_notes", ""),
                item.get("drop_notes", ""),
                _json.dumps(item.get("see_also", [])),
                item.get("source", "manual"),
                item.get("league_version"),
                now,
            )
            for item in items
        ]
        self._conn.executemany(
            """INSERT OR REPLACE INTO item_descriptions
               (name, category, description, crafting_notes, drop_notes,
                see_also, source, league_version, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.execute(
            "INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES('rebuild')"
        )
        self._conn.commit()
        self.set_meta("item_descs_seeded_at", now)
        self.set_meta("item_descs_seed_count", str(len(rows)))
        return len(rows)

    def search_item_descs(
        self,
        keyword: str = "",
        category: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """FTS search across item description name, category, description, crafting_notes."""
        import json as _json

        def _row_to_dict(row) -> dict:
            d = dict(row)
            try:
                d["see_also"] = _json.loads(d.get("see_also") or "[]")
            except Exception:
                d["see_also"] = []
            return d

        if not keyword:
            if category:
                rows = self._conn.execute(
                    "SELECT * FROM item_descriptions WHERE category = ? ORDER BY name LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM item_descriptions ORDER BY name LIMIT ?", (limit,)
                ).fetchall()
            return [_row_to_dict(r) for r in rows]

        safe_kw = keyword.replace('"', '""')
        fts_kw = safe_kw + "*"  # prefix match handles verb forms (desecrates→desecrated)

        def _like_fallback() -> list:
            stem = keyword[:max(4, len(keyword) - 2)] if len(keyword) > 4 else keyword
            pat = f"%{stem}%"
            if category:
                return self._conn.execute(
                    "SELECT * FROM item_descriptions"
                    " WHERE (name LIKE ? OR description LIKE ? OR crafting_notes LIKE ?)"
                    " AND category = ? LIMIT ?",
                    (pat, pat, pat, category, limit),
                ).fetchall()
            return self._conn.execute(
                "SELECT * FROM item_descriptions"
                " WHERE name LIKE ? OR description LIKE ? OR crafting_notes LIKE ?"
                " LIMIT ?",
                (pat, pat, pat, limit),
            ).fetchall()

        try:
            if category:
                rows = self._conn.execute(
                    "SELECT d.* FROM item_descriptions_fts f"
                    " JOIN item_descriptions d ON d.name = f.name"
                    " WHERE f.item_descriptions_fts MATCH ? AND d.category = ?"
                    " ORDER BY rank LIMIT ?",
                    (fts_kw, category, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT d.* FROM item_descriptions_fts f"
                    " JOIN item_descriptions d ON d.name = f.name"
                    " WHERE f.item_descriptions_fts MATCH ?"
                    " ORDER BY rank LIMIT ?",
                    (fts_kw, limit),
                ).fetchall()
        except Exception:
            rows = []

        if not rows:
            rows = _like_fallback()

        return [_row_to_dict(r) for r in rows]

    def get_item_desc(self, name: str) -> dict | None:
        """Exact item description lookup by name (case-insensitive)."""
        import json as _json
        row = self._conn.execute(
            "SELECT * FROM item_descriptions WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["see_also"] = _json.loads(d.get("see_also") or "[]")
        except Exception:
            d["see_also"] = []
        return d

    def get_item_desc_or_fetch(self, name: str, wiki_client=None) -> dict | None:
        """Return cached item description, or fetch from wiki on cache miss.

        Args:
            name:        Item name to look up.
            wiki_client: Optional Poe2WikiClient. When provided, a cache miss
                         triggers a live wiki fetch which is then cached.
        """
        result = self.get_item_desc(name)
        if result is not None:
            return result
        if wiki_client is None:
            return None
        item = wiki_client.fetch_item(name)
        if item:
            self.upsert_item_desc(**item)
            # Rebuild FTS so the new entry is searchable
            try:
                self._conn.execute(
                    "INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES('rebuild')"
                )
                self._conn.commit()
            except Exception:
                pass
            return self.get_item_desc(name)
        return None

    def delete_item_desc(self, name: str) -> bool:
        """Delete an item description by exact name. Returns True if deleted."""
        cur = self._conn.execute(
            "DELETE FROM item_descriptions WHERE lower(name) = lower(?)", (name,)
        )
        self._conn.execute(
            "INSERT INTO item_descriptions_fts(item_descriptions_fts) VALUES('rebuild')"
        )
        self._conn.commit()
        return cur.rowcount > 0

    def item_desc_status(self) -> dict:
        """
        Return freshness info for the item_descriptions table.

        status values: "never_seeded" | "stale" (>30 days) | "fresh"
        """
        _STALE_DAYS = 30
        seeded_at = self.get_meta("item_descs_seeded_at")
        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM item_descriptions"
            ).fetchone()[0]
            manual = self._conn.execute(
                "SELECT COUNT(*) FROM item_descriptions WHERE source = 'manual'"
            ).fetchone()[0]
        except Exception:
            total = 0
            manual = 0

        age_days: float | None = None
        if seeded_at:
            age_days = round(self._age_seconds(seeded_at) / 86400, 1)

        if not seeded_at or total == 0:
            status = "never_seeded"
        elif age_days is not None and age_days > _STALE_DAYS:
            status = "stale"
        else:
            status = "fresh"

        return {
            "status":    status,
            "seeded_at": seeded_at,
            "total":     total,
            "manual":    manual,
            "age_days":  age_days,
        }
