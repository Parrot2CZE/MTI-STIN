"""
Wrapper nad exchangerate.host REST API.

Pozor na strukturu API:
  - Základní měna je vždy USD (free tier neumozuje jinou)
  - Kurzy jsou ve formátu USDEUR, USDCZK atd. (s prefixem)
  - Pro non-USD základní měnu počítáme cross-rates ručně:
      kurs(base -> target) = USD_target / USD_base

Cache se řeší dvojitě: Flask-Caching na úrovni API endpointů
a manuální cache uvnitř service metod. Service cache kryje volání
z routes.py, kde se volá strongest/weakest/average za sebou
a nechceme tři identické HTTP requesty.
"""

from __future__ import annotations

import requests
import time
from datetime import date, timedelta
from typing import Optional
from flask import current_app

from app.app_config_loader import get_cache_timeout, get_exchangerate_api_key


class ExchangeRateService:

    def _base_url(self) -> str:
        return current_app.config["EXCHANGERATE_BASE_URL"]

    def _api_key(self) -> str:
        return get_exchangerate_api_key()

    def _cache(self):
        from app.extensions import cache
        return cache

    # --- Veřejné metody ---

    def get_latest(self, base: str = "USD", symbols: Optional[list[str]] = None) -> dict:
        """Vrátí aktuální kurzy. Výsledek se cachuje podle base+symbols."""
        cache_key = f"latest:{base}:{','.join(sorted(symbols)) if symbols else 'all'}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_latest(base, symbols)
        self._cache().set(cache_key, result, timeout=get_cache_timeout())
        return result

    def get_historical(self, target_date: date, base: str = "USD",
                       symbols: Optional[list[str]] = None) -> dict:
        """Historická data pro konkrétní den. Cachuje se na 24h — minulost se nemění."""
        cache_key = f"hist:{target_date.isoformat()}:{base}:{','.join(sorted(symbols)) if symbols else 'all'}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_historical(target_date, base, symbols)
        self._cache().set(cache_key, result, timeout=86400)
        return result

    def get_timeframe(self, start: date, end: date, base: str = "USD",
                      symbols: Optional[list[str]] = None) -> dict[str, dict[str, float]]:
        """
        Vrátí kurzy pro rozsah dat jako {datum: {měna: kurz}}.
        Cachuje se na 24h — data starší než dnes jsou neměnná.
        """
        cache_key = f"tf:{start.isoformat()}:{end.isoformat()}:{base}:{','.join(sorted(symbols)) if symbols else 'all'}"
        cached = self._cache().get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_timeframe(start, end, base, symbols)
        self._cache().set(cache_key, result, timeout=86400)
        return result

    def strongest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """
        Nejsilnější = měna s NEJNIZŠÍM kurzem vůči base.
        Logika: 1 EUR = 0.85 GBP vs 1 EUR = 25 CZK
        GBP je silnější, protože za 1 EUR dostaneme méně GBP než CZK.
        """
        fetch = [s for s in symbols if s != base]
        if not fetch:
            raise ExchangeRateError("Zadne porovnavane meny (po vylouceni zakladni meny).")
        data = self.get_latest(base, fetch)
        rates = data.get("rates") or {}
        if not rates:
            raise ExchangeRateError("Zadna data pro vypocet nejsilnejsi meny.")
        return min(rates.items(), key=lambda x: x[1])

    def weakest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """Nejslabší = měna s NEJVYŠŠÍM kurzem vůči base. Analogie k strongest."""
        fetch = [s for s in symbols if s != base]
        if not fetch:
            raise ExchangeRateError("Zadne porovnavane meny (po vylouceni zakladni meny).")
        data = self.get_latest(base, fetch)
        rates = data.get("rates") or {}
        if not rates:
            raise ExchangeRateError("Zadna data pro vypocet nejslabsi meny.")
        return max(rates.items(), key=lambda x: x[1])

    def average_rates(self, base: str, symbols: list[str], days: int = 7) -> dict[str, float]:
        """
        Aritmetický průměr kurzu za posledních N dní.
        Pokud timeframe endpoint selže, fallback na postupné volání historical per den.
        Pokud base je v seznamu symbols, přidá se s kurzem 1.0 (měna vůči sobě samé).
        """
        if days < 1 or days > 365:
            raise ExchangeRateError("Pocet dni musi byt v rozsahu 1-365.")

        # Základní měnu nefetchujeme — její kurz vůči sobě je vždy 1.0
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
            # timeframe endpoint selhal, zkusíme den po dni
            result = self._average_via_historical(base, fetch_symbols, days)

        for s in same_as_base:
            result[s] = 1.0

        self._cache().set(cache_key, result, timeout=get_cache_timeout())
        return result

    # --- Privátní fetch metody ---

    def _fetch_latest(self, base: str, symbols: Optional[list[str]]) -> dict:
        """
        Sestaví request na /live.
        Pro non-USD base musíme fetchovat i USD->base kurz, abychom mohli
        spočítat cross-rates. Proto přidáváme base do fetch listu.
        """
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
        """Stejná logika jako _fetch_latest, ale pro konkrétní datum."""
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
        """
        Načte kurzy pro rozsah dat z /timeframe endpointu.
        Odpověď je {datum: {USDEUR: 0.92, ...}}, normalizujeme každý den zvlášť.
        """
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
        # API může vracet data buď pod klíčem 'quotes' nebo 'rates'
        raw_by_date = data.get("quotes") or data.get("rates") or {}
        result: dict[str, dict[str, float]] = {}
        for day_str, day_raw in raw_by_date.items():
            day_data = {"quotes": day_raw} if "rates" not in day_raw else {"rates": day_raw}
            normalized = self._normalize_to_base(day_data, base, symbols)
            result[day_str] = normalized.get("rates") or {}
        return result

    def _normalize_to_base(self, data: dict, base: str,
                            symbols: Optional[list[str]]) -> dict:
        """
        Přepočítá USD-based kurzy na kurzy vůči zvolené base měně.

        Cross-rate vzorec:
          base_to_target = USD_to_target / USD_to_base

        Příklad: base=EUR, target=CZK
          USD->EUR = 0.92, USD->CZK = 23.5
          EUR->CZK = 23.5 / 0.92 = 25.54
        """
        usd_rates = self._extract_rates(data, "USD")
        if base == "USD":
            # Žádný přepočet není potřeba, jen vyfiltrujeme požadované symboly
            if symbols:
                return {"success": True, "rates": {k: v for k, v in usd_rates.items() if k in symbols}}
            return {"success": True, "rates": usd_rates}

        usd_to_base = usd_rates.get(base)
        if not usd_to_base:
            raise ExchangeRateError(f"Kurz pro zakladni menu {base} neni dostupny.")

        cross_rates: dict[str, float] = {}
        for sym, usd_rate in usd_rates.items():
            if sym == base:
                continue
            if symbols and sym not in symbols:
                continue
            cross_rates[sym] = usd_rate / usd_to_base

        # USD musíme přidat ručně — není v usd_rates jako samostatný klíč
        if symbols and "USD" in symbols:
            cross_rates["USD"] = 1.0 / usd_to_base

        return {"success": True, "rates": cross_rates}

    def _compute_averages(self, daily: dict[str, dict[str, float]],
                          symbols: list[str]) -> dict[str, float]:
        """Aritmetický průměr z denních kurzů. Dny bez dat pro daný symbol se přeskakují."""
        accumulator: dict[str, list[float]] = {s: [] for s in symbols}
        for _day, rates in daily.items():
            for sym, rate in rates.items():
                if sym in accumulator:
                    accumulator[sym].append(rate)
        return {s: (sum(v) / len(v) if v else 0.0) for s, v in accumulator.items()}

    def _average_via_historical(self, base: str, fetch_symbols: list[str],
                                 days: int) -> dict[str, float]:
        """
        Fallback výpočet průměru přes jednotlivé historické dny.
        Pomalejší než timeframe (N HTTP requestů místo 1), ale robustnější.
        Dny, kde API selže, se jednoduše přeskočí.
        """
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
        """
        HTTP GET s retry logikou pro 429 Too Many Requests.
        Exponenciální backoff: 1s, 2s — pak teprve ExchangeRateError.
        Timeout 10s na request, jinak by pomalé API mohlo zablokovat worker.
        """
        url = f"{self._base_url()}{path}"
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 429:
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise ExchangeRateError("Rate limit exceeded, zkus to za chvili znovu.")
                resp.raise_for_status()
            except ExchangeRateError:
                raise
            except requests.RequestException as exc:
                raise ExchangeRateError(f"Request failed: {exc}") from exc
            data = resp.json()
            # API vrací success=false s HTTP 200 při chybě autentizace nebo neplatném klíči
            if not data.get("success", True):
                raise ExchangeRateError(data.get("error", {}).get("info", "Unknown API error"))
            return data
        raise ExchangeRateError("Rate limit exceeded, zkus to za chvili znovu.")

    @staticmethod
    def _extract_rates(data: dict, base: str = "") -> dict[str, float]:
        """
        Vytáhne kurzy z raw API odpovědi a ořízne USD prefix.

        exchangerate.host vrací kurzy jako 'USDEUR': 0.92 místo 'EUR': 0.92
        Detekujeme prefix automaticky — pokud klíče začínají base kódem a jsou delší,
        ořízneme prefix. Jinak kurzy vrátíme jak jsou.
        """
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
    """Vyhozen při jakékoliv chybě komunikace s exchangerate.host API."""
    pass
