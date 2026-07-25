"""
Tests for Sprint 4: NinjaClient + PriceDatabase.

NinjaClient tests mock urllib so no real HTTP calls are made.
PriceDatabase tests use an in-memory SQLite database.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poe2_crafting_mcp.data.economy import EconomyError, NinjaClient
from poe2_crafting_mcp.data.price_db import PriceDatabase


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path: Path) -> PriceDatabase:
    """PriceDatabase backed by a fresh temporary SQLite file."""
    db_path = tmp_path / "test_prices.db"
    # Create a minimal DB with the etl_runs table so etl_status() doesn't crash
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS etl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ran_at TEXT DEFAULT (datetime('now')),
            pob_version TEXT,
            row_counts TEXT
        )
    """)
    conn.commit()
    conn.close()
    db = PriceDatabase(db_path)
    yield db
    db.close()


def _mock_response(data: dict | list) -> MagicMock:
    """Build a mock urllib response that returns JSON."""
    body = json.dumps(data).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── NinjaClient: get_leagues ──────────────────────────────────────────────────

class TestGetLeagues:
    _index_state = {
        "economyLeagues": [
            {"name": "Runes of Aldur", "url": "runesofaldur", "hardcore": False, "indexed": True},
            {"name": "Standard", "url": "standard", "hardcore": False, "indexed": False},
            {"name": "SSF Runes of Aldur", "url": "runesofaldurssf", "hardcore": False, "indexed": False},
        ]
    }

    def test_returns_league_list(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(self._index_state)):
            result = NinjaClient().get_leagues()
        assert len(result) == 3
        assert result[0]["name"] == "Runes of Aldur"

    def test_raises_on_http_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            None, 429, "Too Many Requests", {}, None
        )):
            with pytest.raises(EconomyError, match="HTTP 429"):
                NinjaClient().get_leagues()

    def test_raises_on_unexpected_shape(self):
        with patch("urllib.request.urlopen", return_value=_mock_response([])):
            with pytest.raises(EconomyError, match="Unexpected index-state shape"):
                NinjaClient().get_leagues()


# ── NinjaClient: get_current_league ──────────────────────────────────────────

class TestGetCurrentLeague:
    def _index(self, leagues):
        return {"economyLeagues": leagues}

    def test_picks_indexed_challenge_league(self):
        state = self._index([
            {"name": "Runes of Aldur", "indexed": True, "hardcore": False},
            {"name": "HC Runes of Aldur", "indexed": False, "hardcore": True},
            {"name": "Standard", "indexed": False, "hardcore": False},
        ])
        with patch("urllib.request.urlopen", return_value=_mock_response(state)):
            result = NinjaClient().get_current_league()
        assert result == "Runes of Aldur"

    def test_falls_back_to_non_indexed_challenge(self):
        state = self._index([
            {"name": "Runes of Aldur", "indexed": False, "hardcore": False},
            {"name": "Standard", "indexed": False, "hardcore": False},
        ])
        with patch("urllib.request.urlopen", return_value=_mock_response(state)):
            result = NinjaClient().get_current_league()
        assert result == "Runes of Aldur"

    def test_raises_on_empty_list(self):
        state = {"economyLeagues": []}
        with patch("urllib.request.urlopen", return_value=_mock_response(state)):
            with pytest.raises(EconomyError, match="No leagues"):
                NinjaClient().get_current_league()


# ── NinjaClient: fetch_currency_rates ─────────────────────────────────────────

_EXCHANGE_CHAOS = {
    "item": {"id": "chaos", "name": "Chaos Orb"},
    "pairs": [{"id": "divine", "rate": 0.1129, "volumePrimaryValue": 58000}],
}
_EXCHANGE_DIVINE = {
    "item": {"id": "divine", "name": "Divine Orb"},
    "pairs": [{"id": "exalted", "rate": 460, "volumePrimaryValue": 6000}],
}
_EXCHANGE_ALT = {
    "item": {"id": "orb-of-alteration", "name": "Orb of Alteration"},
    "pairs": [{"id": "divine", "rate": 0.05, "volumePrimaryValue": 2000}],
}


class TestFetchCurrencyRates:
    def test_returns_rows_with_divine_and_chaos_values(self):
        responses = [_EXCHANGE_CHAOS, _EXCHANGE_DIVINE, _EXCHANGE_ALT]
        with patch.object(NinjaClient, "fetch_currency_rate", side_effect=[
            {"trade_id": "chaos-orb",         "divine_value": 0.1129, "volume": 58000},
            {"trade_id": "divine-orb",         "divine_value": 1.0,   "volume": 6000},
            {"trade_id": "orb-of-alteration",  "divine_value": 0.05,  "volume": 2000},
        ]):
            result = NinjaClient().fetch_currency_rates(
                "Runes of Aldur",
                ["chaos-orb", "divine-orb", "orb-of-alteration"],
            )

        assert len(result) == 3
        chaos_row = next(r for r in result if r["trade_id"] == "chaos-orb")
        divine_row = next(r for r in result if r["trade_id"] == "divine-orb")
        alt_row    = next(r for r in result if r["trade_id"] == "orb-of-alteration")

        # chaos_value for divine orb = 1 / chaos_divine_rate = 1 / 0.1129 ≈ 8.85
        assert divine_row["chaos_value"] == pytest.approx(1 / 0.1129, rel=0.01)
        # alt divine_value = 0.05 → chaos = 0.05 / 0.1129 ≈ 0.443
        assert alt_row["chaos_value"] == pytest.approx(0.05 / 0.1129, rel=0.01)
        assert chaos_row["category"] == "currency"

    def test_skips_none_returns(self):
        with patch.object(NinjaClient, "fetch_currency_rate", return_value=None):
            result = NinjaClient().fetch_currency_rates("Runes of Aldur", ["chaos-orb"])
        assert result == []

    def test_progress_callback_called(self):
        calls = []
        with patch.object(NinjaClient, "fetch_currency_rate", return_value={
            "trade_id": "chaos-orb", "divine_value": 0.1129, "volume": 1000
        }):
            NinjaClient().fetch_currency_rates(
                "Runes of Aldur", ["chaos-orb"],
                progress_cb=lambda cur, tot, name: calls.append((cur, tot, name))
            )
        assert len(calls) == 1
        assert calls[0] == (1, 1, "chaos-orb")


# ── PriceDatabase: meta ───────────────────────────────────────────────────────

class TestPriceDatabaseMeta:
    def test_get_set_meta(self, tmp_db: PriceDatabase):
        assert tmp_db.get_meta("nonexistent") is None
        tmp_db.set_meta("my_key", "my_value")
        assert tmp_db.get_meta("my_key") == "my_value"

    def test_set_active_league(self, tmp_db: PriceDatabase):
        assert tmp_db.get_active_league() is None
        tmp_db.set_active_league("Dawn of the Hunt")
        assert tmp_db.get_active_league() == "Dawn of the Hunt"

    def test_overwrite_meta(self, tmp_db: PriceDatabase):
        tmp_db.set_meta("k", "v1")
        tmp_db.set_meta("k", "v2")
        assert tmp_db.get_meta("k") == "v2"


# ── PriceDatabase: upsert + reads ─────────────────────────────────────────────

SAMPLE_ROWS = [
    {"name": "Divine Orb",         "category": "currency", "chaos_value": 200.0,  "divine_value": None, "listing_count": 5000},
    {"name": "Orb of Alteration",  "category": "currency", "chaos_value": 0.5,    "divine_value": None, "listing_count": 3000},
    {"name": "Kaom's Heart",        "category": "unique",   "chaos_value": 500.0,  "divine_value": 2.5,  "listing_count": 50},
    {"name": "Titan Greaves",       "category": "base",     "chaos_value": 30.0,   "divine_value": None, "listing_count": 200},
    {"name": "Ice Nova",            "category": "gem",      "chaos_value": 5.0,    "divine_value": None, "listing_count": 300},
]


class TestUpsertAndRead:
    def test_upsert_returns_count(self, tmp_db: PriceDatabase):
        n = tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        assert n == len(SAMPLE_ROWS)

    def test_get_price_exact(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        result = tmp_db.get_price("Divine Orb", "Dawn of the Hunt", "currency")
        assert result is not None
        assert result["chaos_value"] == 200.0
        assert result["league"] == "Dawn of the Hunt"

    def test_get_price_no_category(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        result = tmp_db.get_price("Kaom's Heart", "Dawn of the Hunt")
        assert result is not None
        assert result["category"] == "unique"

    def test_get_price_missing(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        assert tmp_db.get_price("Nonexistent Item", "Dawn of the Hunt") is None

    def test_search_prices_substring(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        results = tmp_db.search_prices("Orb", "Dawn of the Hunt")
        names = [r["name"] for r in results]
        assert "Divine Orb" in names
        assert "Orb of Alteration" in names

    def test_search_prices_with_category(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        results = tmp_db.search_prices("Orb", "Dawn of the Hunt", category="gem")
        assert results == []  # "Orb" not in gems

    def test_get_bulk_prices(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        results = tmp_db.get_bulk_prices("currency", "Dawn of the Hunt")
        assert len(results) == 2
        # sorted by listing_count desc: Divine Orb (5000) > Orb of Alteration (3000)
        assert results[0]["name"] == "Divine Orb"

    def test_upsert_updates_existing(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        updated = [{"name": "Divine Orb", "category": "currency",
                    "chaos_value": 250.0, "divine_value": None, "listing_count": 6000}]
        tmp_db.upsert_prices(updated, "Dawn of the Hunt")
        result = tmp_db.get_price("Divine Orb", "Dawn of the Hunt", "currency")
        assert result["chaos_value"] == 250.0

    def test_league_isolation(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        result = tmp_db.get_price("Divine Orb", "Standard")
        assert result is None


# ── PriceDatabase: fill_divine_values ─────────────────────────────────────────

class TestFillDivineValues:
    def test_fills_currency_divine_values(self, tmp_db: PriceDatabase):
        rows = [
            {"name": "Divine Orb",        "category": "currency", "chaos_value": 200.0, "divine_value": None, "listing_count": 100},
            {"name": "Orb of Alteration", "category": "currency", "chaos_value": 1.0,   "divine_value": None, "listing_count": 50},
        ]
        tmp_db.upsert_prices(rows, "Dawn of the Hunt")
        tmp_db.fill_divine_values("Dawn of the Hunt")

        alt = tmp_db.get_price("Orb of Alteration", "Dawn of the Hunt", "currency")
        # SQLite ROUND(1.0/200.0, 2) = 0.01 (rounds half away from zero)
        assert alt["divine_value"] == pytest.approx(0.01, rel=0.01)

    def test_no_crash_if_divine_orb_missing(self, tmp_db: PriceDatabase):
        rows = [{"name": "Chaos Orb", "category": "currency", "chaos_value": 1.0,
                 "divine_value": None, "listing_count": 100}]
        tmp_db.upsert_prices(rows, "Dawn of the Hunt")
        tmp_db.fill_divine_values("Dawn of the Hunt")  # should not raise


# ── PriceDatabase: cache_status ───────────────────────────────────────────────

class TestCacheStatus:
    def test_missing_when_no_prices(self, tmp_db: PriceDatabase):
        status = tmp_db.price_cache_status("Dawn of the Hunt")
        assert status["status"] == "missing"

    def test_fresh_after_upsert(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        status = tmp_db.price_cache_status("Dawn of the Hunt")
        assert status["status"] == "fresh"
        assert status["age_minutes"] is not None
        assert status["age_minutes"] < 1

    def test_stale_league(self, tmp_db: PriceDatabase):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        status = tmp_db.price_cache_status("OtherLeague")
        assert status["status"] == "stale_league"

    def test_stale_ttl(self, tmp_db: PriceDatabase, monkeypatch):
        tmp_db.upsert_prices(SAMPLE_ROWS, "Dawn of the Hunt")
        # Mock age to exceed TTL
        monkeypatch.setattr(tmp_db, "_age_seconds", lambda iso: 7200.0)
        status = tmp_db.price_cache_status("Dawn of the Hunt")
        assert status["status"] == "stale_ttl"


# ── PriceDatabase: etl_status ─────────────────────────────────────────────────

class TestEtlStatus:
    def test_never_run_when_no_etl_rows(self, tmp_db: PriceDatabase):
        status = tmp_db.etl_status("Dawn of the Hunt")
        assert status["status"] == "never_run"

    def test_fresh_after_recent_etl(self, tmp_db: PriceDatabase):
        tmp_db.set_meta("etl_ran_at", tmp_db._now_iso())
        tmp_db.set_meta("etl_league", "Dawn of the Hunt")
        status = tmp_db.etl_status("Dawn of the Hunt")
        assert status["status"] == "fresh"

    def test_stale_league(self, tmp_db: PriceDatabase):
        tmp_db.set_meta("etl_ran_at", tmp_db._now_iso())
        tmp_db.set_meta("etl_league", "OldLeague")
        status = tmp_db.etl_status("Dawn of the Hunt")
        assert status["status"] == "stale_league"

    def test_stale_age(self, tmp_db: PriceDatabase, monkeypatch):
        tmp_db.set_meta("etl_ran_at", tmp_db._now_iso())
        tmp_db.set_meta("etl_league", "Dawn of the Hunt")
        # Mock age to > 7 days
        monkeypatch.setattr(tmp_db, "_age_seconds", lambda iso: 8 * 86400.0)
        status = tmp_db.etl_status("Dawn of the Hunt")
        assert status["status"] == "stale_age"
