from __future__ import annotations

import requests
import time
from datetime import date, timedelta
from typing import Optional
from flask import current_app

from app.app_config_loader import get_cache_timeout, get_exchangerate_api_key


class ExchangeRateService:
    """
    Wrapper around exchangerate.host REST API.

    API klíč se načítá přes get_exchangerate_api_key() — config.yml má přednost,
    fallback na env proměnnou EXCHANGERATE_API_KEY.
    """

    def _base_url(self) -> str:
        return current_app.config["EXCHANGERATE_BASE_URL"]

    def _api_key(self) -> str:
        return get_exchangerate_api_key()

    def _cache(self):
        from app.extensions import cache
        return cache

    def get_latest(self, base: str = "USD", symbols: Optional[list[str]] = None) -> dict:
        cache_key = f"latest:{base}:{','.join(sorted(symbols)) if symbols else 'all'}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_latest(base, symbols)
        self._cache().set(cache_key, result, timeout=get_cache_timeout())
        return result

    def get_historical(self, target_date: date, base: str = "USD",
                       symbols: Optional[list[str]] = None) -> dict:
        cache_key = f"hist:{target_date.isoformat()}:{base}:{','.join(sorted(symbols)) if symbols else 'all'}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_historical(target_date, base, symbols)
        self._cache().set(cache_key, result, timeout=86400)
        return result

    def get_timeframe(self, start: date, end: date, base: str = "USD",
                      symbols: Optional[list[str]] = None) -> dict[str, dict[str, float]]:
        cache_key = f"tf:{start.isoformat()}:{end.isoformat()}:{base}:{','.join(sorted(symbols)) if symbols else 'all'}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_timeframe(start, end, base, symbols)
        self._cache().set(cache_key, result, timeout=86400)
        return result

    def strongest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        fetch = [s for s in symbols if s != base]
        if not fetch:
            raise ExchangeRateError("Žádné porovnávané měny (po vyloučení základní měny).")
        data = self.get_latest(base, fetch)
        rates = data.get("rates") or {}
        if not rates:
            raise ExchangeRateError("Žádná data pro výpočet nejsilnější měny.")
        return min(rates.items(), key=lambda x: x[1])

    def weakest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        fetch = [s for s in symbols if s != base]
        if not fetch:
            raise ExchangeRateError("Žádné porovnávané měny (po vyloučení základní měny).")
        data = self.get_latest(base, fetch)
        rates = data.get("rates") or {}
        if not rates:
            raise ExchangeRateError("Žádná data pro výpočet nejslabší měny.")
        return max(rates.items(), key=lambda x: x[1])

    def average_rates(self, base: str, symbols: list[str], days: int = 7) -> dict[str, float]:
        if days < 1 or days > 365:
            raise ExchangeRateError("Počet dní musí být v rozsahu 1–365.")

        same_as_base = [s for s in symbols if s == base]
        fetch_symbols = [s for s in symbols if s != base]

        cache_key = f"avg:{base}:{','.join(sorted(fetch_symbols))}:{days}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached

        today = date.today()
        start = today - timedelta(days=days - 1)

        result: dict[str, float] = {}
        try:
            daily = self.get_timeframe(start, today, base, fetch_symbols or None)
            result = self._compute_averages(daily, fetch_symbols)
        except ExchangeRateError:
            result = self._average_via_historical(base, fetch_symbols, days)

        for s in same_as_base:
            result[s] = 1.0

        self._cache().set(cache_key, result, timeout=get_cache_timeout())
        return result

    def _fetch_latest(self, base: str, symbols: Optional[list[str]]) -> dict:
        fetch_symbols: Optional[list[str]] = None
        if symbols:
            if base != "USD":
                non_usd = [s for s in symbols if s != "USD"]
                fetch_symbols = list(set(non_usd) | {base})
            else:
                fetch_symbols = list(symbols)
        params: dict = {"access_key": self._api_key()}
        if fetch_symbols:
            params["symbols"] = ",".join(fetch_symbols)
        data = self._get("/live", params)
        return self._normalize_to_base(data, base, symbols)

    def _fetch_historical(self, target_date: date, base: str,
                          symbols: Optional[list[str]]) -> dict:
        fetch_symbols: Optional[list[str]] = None
        if symbols:
            if base != "USD":
                non_usd = [s for s in symbols if s != "USD"]
                fetch_symbols = list(set(non_usd) | {base})
            else:
                fetch_symbols = list(symbols)
        params: dict = {
            "access_key": self._api_key(),
            "date": target_date.isoformat(),
        }
        if fetch_symbols:
            params["symbols"] = ",".join(fetch_symbols)
        data = self._get("/historical", params)
        return self._normalize_to_base(data, base, symbols)

    def _fetch_timeframe(self, start: date, end: date, base: str,
                         symbols: Optional[list[str]]) -> dict[str, dict[str, float]]:
        fetch_symbols: Optional[list[str]] = None
        if symbols:
            if base != "USD":
                non_usd = [s for s in symbols if s != "USD"]
                fetch_symbols = list(set(non_usd) | {base})
            else:
                fetch_symbols = list(symbols)
        params: dict = {
            "access_key": self._api_key(),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        if fetch_symbols:
            params["symbols"] = ",".join(fetch_symbols)
        data = self._get("/timeframe", params)
        raw_by_date = data.get("quotes") or data.get("rates") or {}
        result: dict[str, dict[str, float]] = {}
        for day_str, day_raw in raw_by_date.items():
            day_data = {"quotes": day_raw} if "rates" not in day_raw else {"rates": day_raw}
            normalized = self._normalize_to_base(day_data, base, symbols)
            result[day_str] = normalized.get("rates") or {}
        return result

    def _normalize_to_base(self, data: dict, base: str,
                            symbols: Optional[list[str]]) -> dict:
        usd_rates = self._extract_rates(data, "USD")
        if base == "USD":
            if symbols:
                return {"success": True, "rates": {k: v for k, v in usd_rates.items() if k in symbols}}
            return {"success": True, "rates": usd_rates}
        usd_to_base = usd_rates.get(base)
        if not usd_to_base:
            raise ExchangeRateError(f"Kurz pro základní měnu {base} není dostupný.")
        cross_rates: dict[str, float] = {}
        for sym, usd_rate in usd_rates.items():
            if sym == base:
                continue
            if symbols and sym not in symbols:
                continue
            cross_rates[sym] = usd_rate / usd_to_base
        if symbols and "USD" in symbols:
            cross_rates["USD"] = 1.0 / usd_to_base
        return {"success": True, "rates": cross_rates}

    def _compute_averages(self, daily: dict[str, dict[str, float]],
                          symbols: list[str]) -> dict[str, float]:
        accumulator: dict[str, list[float]] = {s: [] for s in symbols}
        for _day, rates in daily.items():
            for sym, rate in rates.items():
                if sym in accumulator:
                    accumulator[sym].append(rate)
        return {s: (sum(v) / len(v) if v else 0.0) for s, v in accumulator.items()}

    def _average_via_historical(self, base: str, fetch_symbols: list[str],
                                 days: int) -> dict[str, float]:
        accumulator: dict[str, list[float]] = {s: [] for s in fetch_symbols}
        today = date.today()
        for offset in range(days):
            target = today - timedelta(days=offset)
            try:
                data = self.get_historical(target, base, fetch_symbols or None)
                for sym, rate in (data.get("rates") or {}).items():
                    if sym in accumulator:
                        accumulator[sym].append(rate)
            except ExchangeRateError:
                continue
        return {s: (sum(v) / len(v) if v else 0.0) for s, v in accumulator.items()}

    def _get(self, path: str, params: dict, retries: int = 2) -> dict:
        url = f"{self._base_url()}{path}"
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 429:
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise ExchangeRateError("Rate limit exceeded, zkus to za chvíli znovu.")
                resp.raise_for_status()
            except ExchangeRateError:
                raise
            except requests.RequestException as exc:
                raise ExchangeRateError(f"Request failed: {exc}") from exc
            data = resp.json()
            if not data.get("success", True):
                raise ExchangeRateError(data.get("error", {}).get("info", "Unknown API error"))
            return data
        raise ExchangeRateError("Rate limit exceeded, zkus to za chvíli znovu.")

    @staticmethod
    def _extract_rates(data: dict, base: str = "") -> dict[str, float]:
        raw = data.get("rates") or data.get("quotes") or {}
        if not raw:
            return {}
        prefix_len = len(base)
        if prefix_len and any(
            k.upper().startswith(base.upper()) and len(k) > prefix_len for k in raw
        ):
            return {
                k[prefix_len:]: float(v)
                for k, v in raw.items()
                if k.upper().startswith(base.upper())
            }
        return {k: float(v) for k, v in raw.items()}


class ExchangeRateError(Exception):
    pass
