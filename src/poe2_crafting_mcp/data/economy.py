"""
poe.ninja HTTP client for PoE2 price data.

Uses the PoE2-specific API endpoints discovered from HAR analysis:
  League list:  GET /poe2/api/data/index-state
  Currency:     GET /poe2/api/economy/exchange/current/details?league=...&type=Currency&id=<slug>

The bulk itemoverview endpoint (/poe2/api/data/itemoverview) returns empty
for PoE2 — item prices are not available via the public API at this time.

No external dependencies — stdlib urllib only.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_BASE_URL = "https://poe.ninja/poe2/api"
_TIMEOUT  = 15      # seconds per request
_INTER_REQUEST_DELAY = 0.05   # 50ms between exchange calls to be polite

# Substrings that exclude a league from challenge-league auto-detection
_NON_CHALLENGE = ("HC ", "Hardcore", "SSF", "Solo Self", "Standard")


class EconomyError(Exception):
    """Raised when a poe.ninja API call fails or returns unexpected data."""


class NinjaClient:
    """
    Thin wrapper around the poe.ninja PoE2 API.

    All methods return plain Python dicts/lists — no HTTP types leak out.
    """

    def __init__(self) -> None:
        pass

    # ── Internal ─────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        qs = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{_BASE_URL}/{path}{qs}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "poe2-crafting-mcp/1.0 (github: poe2-crafting-mcp)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise EconomyError(f"HTTP {e.code} from poe.ninja ({url})") from e
        except urllib.error.URLError as e:
            raise EconomyError(f"Network error: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise EconomyError(f"Bad JSON from poe.ninja: {e}") from e

    # ── Leagues ───────────────────────────────────────────────────────────────

    def get_leagues(self) -> list[dict]:
        """
        Return all active PoE2 leagues from poe.ninja.

        Each entry: {name, url, displayName, hardcore, indexed}
        """
        data = self._get("data/index-state")
        if not isinstance(data, dict):
            raise EconomyError(f"Unexpected index-state shape: {type(data)}")
        return data.get("economyLeagues", [])

    def get_current_league(self) -> str:
        """
        Auto-detect the current challenge trade league.

        Returns the first non-HC, non-SSF, non-Standard league that is
        indexed (has price data) on poe.ninja.
        """
        leagues = self.get_leagues()
        # Prefer indexed leagues (have data) that aren't HC/SSF/Standard
        for league in leagues:
            name = league.get("name", "")
            if league.get("indexed") and not any(s in name for s in _NON_CHALLENGE):
                return name
        # Fall back to any non-HC/SSF/Standard
        for league in leagues:
            name = league.get("name", "")
            if not any(s in name for s in _NON_CHALLENGE):
                return name
        # Last resort — first league
        if leagues:
            return leagues[0]["name"]
        raise EconomyError("No leagues found from poe.ninja")

    # ── Currency Prices ───────────────────────────────────────────────────────

    def fetch_currency_rate(self, league: str, trade_id: str) -> dict | None:
        """
        Fetch the exchange rate for a single currency by its trade_id slug.

        Returns:
            {trade_id, divine_value, volume} or None if not found / no pairs.

        The divine_value is how many divine orbs this currency is worth.
        For Chaos Orb: divine_value ≈ 0.113 (1 chaos = 0.113 divine).
        For Divine Orb: divine_value = 1.0 (by definition).
        """
        try:
            data = self._get("economy/exchange/current/details", {
                "league": league,
                "type": "Currency",
                "id": trade_id,
            })
        except EconomyError:
            return None

        if not data or not isinstance(data, dict):
            return None

        pairs = data.get("pairs", [])
        if not pairs:
            return None

        # Find the divine pair — expresses value in divine orbs
        divine_pair = next((p for p in pairs if p.get("id") == "divine"), None)

        # For Divine Orb itself, look at chaos pair to derive the inverse
        if divine_pair is None and trade_id == "divine-orb":
            return {
                "trade_id": trade_id,
                "divine_value": 1.0,
                "volume": pairs[0].get("volumePrimaryValue", 0) if pairs else 0,
            }

        if divine_pair is None:
            # Try first pair as fallback
            divine_pair = pairs[0]

        return {
            "trade_id": trade_id,
            "divine_value": float(divine_pair.get("rate", 0)),
            "volume": int(divine_pair.get("volumePrimaryValue", 0)),
        }

    def fetch_currency_rates(
        self,
        league: str,
        trade_ids: list[str],
        progress_cb: Any = None,
    ) -> list[dict]:
        """
        Fetch exchange rates for a list of currency trade_ids.

        Makes one HTTP call per currency (poe.ninja has no batch endpoint).
        progress_cb(current, total, name) is called after each fetch if provided.

        Returns:
            List of {name, category, trade_id, chaos_value, divine_value,
                     listing_count} ready for PriceDatabase.upsert_prices().
        """
        results: list[dict] = []
        total = len(trade_ids)
        divine_rate: float | None = None  # chaos per divine, filled after chaos-orb fetch

        for i, trade_id in enumerate(trade_ids):
            if progress_cb:
                progress_cb(i + 1, total, trade_id)

            rate_data = self.fetch_currency_rate(league, trade_id)
            if rate_data is None:
                time.sleep(_INTER_REQUEST_DELAY)
                continue

            divine_value = rate_data["divine_value"]

            results.append({
                "name": _slug_to_name(trade_id),
                "category": "currency",
                "trade_id": trade_id,
                "divine_value": divine_value,
                "chaos_value": None,       # filled in after we know chaos rate
                "listing_count": rate_data["volume"],
            })

            time.sleep(_INTER_REQUEST_DELAY)

        # Calculate chaos values using the chaos-orb divine rate
        chaos_row = next((r for r in results if r["trade_id"] == "chaos-orb"), None)
        if chaos_row and chaos_row["divine_value"] and chaos_row["divine_value"] > 0:
            # chaos-orb divine_value = divine per chaos (e.g. 0.1129)
            # → chaos_per_divine = 1 / 0.1129 ≈ 8.85
            chaos_per_divine = 1.0 / chaos_row["divine_value"]
            for r in results:
                if r["divine_value"] is not None:
                    r["chaos_value"] = round(r["divine_value"] * chaos_per_divine, 4)
            # Divine Orb itself
            divine_row = next((r for r in results if r["trade_id"] == "divine-orb"), None)
            if divine_row:
                divine_row["chaos_value"] = round(chaos_per_divine, 2)

        return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug_to_name(slug: str) -> str:
    """Convert a poe.ninja slug back to a display name. e.g. 'chaos-orb' → 'Chaos Orb'."""
    return slug.replace("-", " ").title()
