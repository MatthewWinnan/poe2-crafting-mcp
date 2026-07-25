"""
GGG official trade2 API client for PoE2 live price lookups.

Endpoints used:
  POST /api/trade2/search/<league>  — search by name/type, returns listing IDs
  GET  /api/trade2/fetch/<ids>      — fetch listing details (price, item info)

Rate limit: ~6 requests per 5s, 45 per 60s. We enforce a 1.5s delay between
search calls. Fetch calls consume the same budget — we batch 10 IDs per fetch.

No authentication required for read-only public trade searches.
"""
from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_BASE = "https://www.pathofexile.com/api/trade2"

# Map human-readable slot names → trade2 API category filter values.
# Keys are lowercase; values are the "option" string for type_filters.category.
SLOT_TO_CATEGORY: dict[str, str] = {
    "gloves":          "armour.gloves",
    "boots":           "armour.boots",
    "helmet":          "armour.helmet",
    "helm":            "armour.helmet",
    "body armour":     "armour.chest",
    "body":            "armour.chest",
    "chest":           "armour.chest",
    "ring":            "accessory.ring",
    "amulet":          "accessory.amulet",
    "belt":            "accessory.belt",
    "shield":          "armour.shield",
    "quiver":          "armour.quiver",
    "flask":           "flask",
    # Weapons
    "sword":           "weapon.onesword",
    "one hand sword":  "weapon.onesword",
    "two hand sword":  "weapon.twosword",
    "axe":             "weapon.oneaxe",
    "one hand axe":    "weapon.oneaxe",
    "two hand axe":    "weapon.twoaxe",
    "mace":            "weapon.onemace",
    "one hand mace":   "weapon.onemace",
    "two hand mace":   "weapon.twomace",
    "bow":             "weapon.bow",
    "staff":           "weapon.staff",
    "crossbow":        "weapon.crossbow",
    "wand":            "weapon.wand",
    "sceptre":         "weapon.sceptre",
    "dagger":          "weapon.dagger",
    "claw":            "weapon.claw",
    "spear":           "weapon.warstaff",
    "focus":           "offhand.focus",
    "jewel":           "jewel",
}
_TIMEOUT         = 10    # seconds
_SEARCH_DELAY    = 1.5   # seconds between search calls (rate-limit safety)
_FETCH_BATCH     = 10    # IDs per fetch call (API max is 10)
_DEFAULT_SAMPLE  = 5     # listings to fetch for price estimation

# Map poe.ninja currency IDs → display symbols
_CURRENCY_SYMBOLS: dict[str, str] = {
    "divine":    "d",
    "exalted":   "ex",
    "chaos":     "c",
    "transmute": "t",
    "augment":   "aug",
    "alteration":"alt",
    "regal":     "regal",
    "annulment": "ann",
    "vaal":      "vaal",
}


class TradeError(Exception):
    """Raised when a GGG trade2 API call fails."""


class TradeClient:
    """
    Thin wrapper around the PoE2 trade2 API for live item price lookups.

    Respects rate limits via delays. Returns plain dicts — no HTTP types leak.
    """

    def __init__(self) -> None:
        self._last_search_at: float = 0.0

    # ── Internal ─────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent":   "poe2-crafting-mcp/1.0 (github: poe2-crafting-mcp)",
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def _post(self, path: str, body: dict) -> Any:
        url = f"{_BASE}/{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            try:
                err = json.loads(body_bytes).get("error", {})
                msg = err.get("message", str(e))
            except Exception:
                msg = str(e)
            raise TradeError(f"HTTP {e.code}: {msg}") from e
        except urllib.error.URLError as e:
            raise TradeError(f"Network error: {e.reason}") from e

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        qs = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{_BASE}/{path}{qs}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise TradeError(f"HTTP {e.code} from trade API") from e
        except urllib.error.URLError as e:
            raise TradeError(f"Network error: {e.reason}") from e

    def _rate_limit_wait(self) -> None:
        elapsed = time.monotonic() - self._last_search_at
        if elapsed < _SEARCH_DELAY:
            time.sleep(_SEARCH_DELAY - elapsed)
        self._last_search_at = time.monotonic()

    # ── Static Data ───────────────────────────────────────────────────────────

    def fetch_stats(self) -> list[dict]:
        """
        Fetch all explicit/implicit/pseudo stat entries from the trade2 API.

        Returns a list of {stat_id, stat_text, stat_type} dicts ready for
        PriceDatabase.upsert_trade_stats().

        This is a one-time setup call (~1-2s, ~6000 entries). Cache the
        result via PriceDatabase — no need to call more than once per session.
        """
        resp = self._get("data/stats")
        stats: list[dict] = []
        for group in resp.get("result", []):
            stat_type = group.get("label", "Explicit").lower()
            for entry in group.get("entries", []):
                sid  = entry.get("id", "")
                text = entry.get("text", "")
                if sid and text:
                    stats.append({
                        "stat_id":   sid,
                        "stat_text": text,
                        "stat_type": stat_type,
                    })
        return stats

    # ── Search ────────────────────────────────────────────────────────────────

    def search_unique(self, league: str, name: str) -> tuple[str, list[str]]:
        """
        Search for a unique item by name. Returns (search_id, result_ids).

        result_ids is sorted by price ascending (cheapest first).
        """
        self._rate_limit_wait()
        resp = self._post(f"search/{urllib.parse.quote(league)}", {
            "query": {
                "status": {"option": "online"},
                "name": name,
                "filters": {},
            },
            "sort": {"price": "asc"},
        })
        if "error" in resp:
            raise TradeError(resp["error"].get("message", str(resp["error"])))
        return resp["id"], resp.get("result", [])

    def search_base(
        self,
        league: str,
        base_name: str,
        ilvl_min: int = 80,
        rarity: str = "nonunique",
    ) -> tuple[str, list[str]]:
        """
        Search for a base item by exact type name + minimum item level.

        rarity: "nonunique" (default) | "normal" | "magic" | "rare" | "any"
        Returns (search_id, result_ids) sorted by price ascending.
        """
        self._rate_limit_wait()
        filters: dict[str, Any] = {
            "equipment_filters": {
                "filters": {
                    "ilvl": {"min": ilvl_min},
                }
            }
        }
        if rarity and rarity != "any":
            filters["type_filters"] = {
                "filters": {
                    "rarity": {"option": rarity},
                }
            }

        resp = self._post(f"search/{urllib.parse.quote(league)}", {
            "query": {
                "status": {"option": "online"},
                "type": base_name,
                "filters": filters,
                "stats": [],
            },
            "sort": {"price": "asc"},
        })
        if "error" in resp:
            raise TradeError(resp["error"].get("message", str(resp["error"])))
        return resp["id"], resp.get("result", [])

    def search_trade(
        self,
        league: str,
        stat_filters: list[dict],
        category: str | None = None,
        rarity: str = "magic",
        ilvl_min: int = 80,
    ) -> tuple[str, list[str]]:
        """
        Search the trade site by stat filters (e.g. T1 energy shield on gloves).

        stat_filters: list of {"id": "explicit.stat_XXXXXXX", "min": float, "max": float}
            - "id" is required; "min" and "max" are optional bounds.
        category: trade category string, e.g. "armour.gloves". Use SLOT_TO_CATEGORY
            to convert a slot name. If None, searches all items.
        rarity: "magic" | "rare" | "normal" | "nonunique" | "any"
        ilvl_min: minimum item level (default 80).

        Returns (search_id, result_ids) sorted by price ascending.
        """
        self._rate_limit_wait()

        filters: dict[str, Any] = {
            "equipment_filters": {
                "filters": {"ilvl": {"min": ilvl_min}},
            },
        }
        if rarity and rarity != "any":
            filters["type_filters"] = {
                "filters": {"rarity": {"option": rarity}},
            }
        if category:
            filters.setdefault("type_filters", {"filters": {}})
            filters["type_filters"]["filters"]["category"] = {"option": category}

        # Build stats block
        api_stat_filters = []
        for sf in stat_filters:
            entry: dict[str, Any] = {"id": sf["id"], "disabled": False}
            value: dict[str, Any] = {}
            if sf.get("min") is not None:
                value["min"] = sf["min"]
            if sf.get("max") is not None:
                value["max"] = sf["max"]
            if value:
                entry["value"] = value
            api_stat_filters.append(entry)

        stats_block = [{"type": "and", "filters": api_stat_filters}] if api_stat_filters else []

        resp = self._post(f"search/{urllib.parse.quote(league)}", {
            "query": {
                "status": {"option": "online"},
                "filters": filters,
                "stats": stats_block,
            },
            "sort": {"price": "asc"},
        })
        if "error" in resp:
            raise TradeError(resp["error"].get("message", str(resp["error"])))
        return resp["id"], resp.get("result", [])

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def fetch_listings(self, search_id: str, result_ids: list[str]) -> list[dict]:
        """
        Fetch up to _FETCH_BATCH listing details for the given IDs.

        Returns list of {name, base_type, rarity, ilvl, price_amount,
                          price_currency, price_chaos_hint, whisper}.
        """
        if not result_ids:
            return []
        ids = result_ids[:_FETCH_BATCH]
        ids_str = ",".join(ids)
        resp = self._get(f"fetch/{ids_str}", {"query": search_id, "realm": "poe2"})
        results = []
        for r in resp.get("result", []):
            item    = r.get("item", {})
            listing = r.get("listing", {})
            price   = listing.get("price", {})
            results.append({
                "name":           item.get("name", ""),
                "base_type":      item.get("baseType", ""),
                "rarity":         item.get("rarity", ""),
                "ilvl":           item.get("ilvl", 0),
                "price_amount":   price.get("amount"),
                "price_currency": price.get("currency", ""),
                "account":        listing.get("account", {}).get("name", ""),
            })
        return results

    # ── Price Estimation ──────────────────────────────────────────────────────

    def estimate_price(
        self,
        league: str,
        name: str | None = None,
        base_name: str | None = None,
        ilvl_min: int = 80,
        rarity: str = "nonunique",
        sample: int = _DEFAULT_SAMPLE,
    ) -> dict:
        """
        Get a price estimate for a unique item or base item.

        Provide `name` for uniques, `base_name` for item bases.
        rarity: "nonunique" | "normal" | "magic" | "rare" | "any" (for base searches)
        Returns a result dict with trade_url, min_price, median_price, listings, etc.

        Returns:
            {
              found: bool,
              name: str,
              total_listings: int,
              sample_size: int,
              min_price: {amount, currency},
              median_price: {amount, currency},
              trade_url: str,
              listings: [{name, base_type, ilvl, price_amount, price_currency}, ...],
              note: str (if any issue),
            }
        """
        try:
            if name:
                search_id, ids = self.search_unique(league, name)
            elif base_name:
                search_id, ids = self.search_base(
                    league, base_name, ilvl_min=ilvl_min, rarity=rarity
                )
            else:
                raise TradeError("Must provide name or base_name")
        except TradeError as e:
            return {"found": False, "error": str(e)}

        trade_url = (
            f"https://www.pathofexile.com/trade2/search/"
            f"{urllib.parse.quote(league)}/{search_id}"
        )

        total = len(ids)
        if total == 0:
            return {
                "found": False,
                "name": name or base_name,
                "total_listings": 0,
                "trade_url": trade_url,
                "note": "No listings found on trade.",
            }

        listings = self.fetch_listings(search_id, ids[:sample])

        # Extract numeric prices — try to normalise to the dominant currency
        prices_by_currency: dict[str, list[float]] = {}
        for lst in listings:
            amt = lst.get("price_amount")
            cur = lst.get("price_currency", "")
            if amt is not None and cur:
                prices_by_currency.setdefault(cur, []).append(float(amt))

        # Pick the most common currency
        if not prices_by_currency:
            return {
                "found": True,
                "name": name or base_name,
                "total_listings": total,
                "sample_size": len(listings),
                "trade_url": trade_url,
                "listings": listings,
                "note": "Could not extract prices from listings.",
            }

        dominant_cur = max(prices_by_currency, key=lambda c: len(prices_by_currency[c]))
        prices = sorted(prices_by_currency[dominant_cur])
        min_price = prices[0]
        median_price = statistics.median(prices)

        return {
            "found": True,
            "name": name or base_name,
            "total_listings": total,
            "sample_size": len(listings),
            "min_price":    {"amount": min_price,    "currency": dominant_cur},
            "median_price": {"amount": median_price, "currency": dominant_cur},
            "trade_url": trade_url,
            "listings": listings,
        }

    def estimate_trade_price(
        self,
        league: str,
        stat_filters: list[dict],
        category: str | None = None,
        rarity: str = "magic",
        ilvl_min: int = 80,
        sample: int = _DEFAULT_SAMPLE,
    ) -> dict:
        """
        Estimate the price of items matching stat filters on the trade site.

        stat_filters: [{id, min?, max?}]  — explicit stat IDs with optional bounds.
        category: trade category (e.g. "armour.gloves"). Use SLOT_TO_CATEGORY helper.
        rarity: "magic" | "rare" | "normal" | "any"
        ilvl_min: minimum item level.

        Returns the same shape as estimate_price():
            {found, total_listings, min_price, median_price, trade_url, listings, ...}
        """
        label = category or "any slot"
        try:
            search_id, ids = self.search_trade(
                league, stat_filters, category=category, rarity=rarity, ilvl_min=ilvl_min
            )
        except TradeError as e:
            return {"found": False, "error": str(e)}

        trade_url = (
            f"https://www.pathofexile.com/trade2/search/"
            f"{urllib.parse.quote(league)}/{search_id}"
        )

        total = len(ids)
        if total == 0:
            return {
                "found": False,
                "category": label,
                "rarity": rarity,
                "total_listings": 0,
                "trade_url": trade_url,
                "note": "No listings found matching these stat filters.",
            }

        listings = self.fetch_listings(search_id, ids[:sample])

        prices_by_currency: dict[str, list[float]] = {}
        for lst in listings:
            amt = lst.get("price_amount")
            cur = lst.get("price_currency", "")
            if amt is not None and cur:
                prices_by_currency.setdefault(cur, []).append(float(amt))

        if not prices_by_currency:
            return {
                "found": True,
                "category": label,
                "rarity": rarity,
                "total_listings": total,
                "sample_size": len(listings),
                "trade_url": trade_url,
                "listings": listings,
                "note": "Could not extract prices from listings.",
            }

        dominant_cur = max(prices_by_currency, key=lambda c: len(prices_by_currency[c]))
        prices = sorted(prices_by_currency[dominant_cur])
        min_price = prices[0]
        median_price = statistics.median(prices)

        return {
            "found": True,
            "category": label,
            "rarity": rarity,
            "total_listings": total,
            "sample_size": len(listings),
            "min_price":    {"amount": min_price,    "currency": dominant_cur},
            "median_price": {"amount": median_price, "currency": dominant_cur},
            "trade_url": trade_url,
            "listings": listings,
        }
