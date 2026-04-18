from __future__ import annotations

import requests
import time
from datetime import date, timedelta
from typing import Optional
from flask import current_app


class ExchangeRateService:
    """
    Wrapper around exchangerate.host REST API.

    Důležité omezení API:
    - /live endpoint vždy vrací kurzy s USD jako základem, bez ohledu na parametr base.
      Proto get_latest() vždy stáhne USD kurzy a v případě jiné base přepočítá křížem.
    - /historical endpoint parametr base respektuje — přepočet není potřeba.
    """

    def _base_url(self) -> str:
        return current_app.config["EXCHANGERATE_BASE_URL"]

    def _api_key(self) -> str:
        return current_app.config["EXCHANGERATE_API_KEY"]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest(self, base: str = "USD", symbols: Optional[list[str]] = None) -> dict:
        """
        Vrátí aktuální kurzy pro základní měnu *base*.

        Protože /live vždy vrací USD jako zdroj, stáhneme USD kurzy
        a pokud base != USD, přepočítáme křížem:
            rate(base→symbol) = rate(USD→symbol) / rate(USD→base)
        """
        # Pro přepočet potřebujeme i kurz samotné base měny vůči USD
        fetch_symbols: Optional[list[str]] = None
        if symbols:
            if base != "USD":
                # Přidáme base do dotazu, abychom měli USD→base kurz
                fetch_symbols = list(set(symbols) | {base})
            else:
                fetch_symbols = list(symbols)

        params: dict = {"access_key": self._api_key()}
        if fetch_symbols:
            params["symbols"] = ",".join(fetch_symbols)

        data = self._get("/live", params)

        # /live vždy vrací prefix "USD" → ořízni
        usd_rates = self._extract_rates(data, "USD")

        if base == "USD":
            # Filtruj na požadované symboly
            if symbols:
                filtered = {k: v for k, v in usd_rates.items() if k in symbols}
            else:
                filtered = usd_rates
            return {"success": True, "rates": filtered}

        # Přepočet křížem pro base != USD
        usd_to_base = usd_rates.get(base)
        if not usd_to_base:
            raise ExchangeRateError(
                f"Kurz pro základní měnu {base} není dostupný v odpovědi API."
            )

        cross_rates: dict[str, float] = {}
        for sym, usd_rate in usd_rates.items():
            if sym == base:
                continue
            if symbols and sym not in symbols:
                continue
            cross_rates[sym] = usd_rate / usd_to_base

        return {"success": True, "rates": cross_rates}

    def get_historical(self, target_date: date, base: str = "USD",
                       symbols: Optional[list[str]] = None) -> dict:
        """
        Vrátí historické kurzy pro daný den.
        /historical respektuje parametr base — přepočet není potřeba.
        """
        params: dict = {
            "access_key": self._api_key(),
            "base": base,
            "date": target_date.isoformat(),
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        data = self._get("/historical", params)
        # /historical může vracet prefix i čisté klíče podle plánu
        rates = self._extract_rates(data, base)
        return {"success": True, "rates": rates}

    # ------------------------------------------------------------------
    # Analytics — FR2, FR3, FR4
    # ------------------------------------------------------------------

    def strongest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """
        FR2 — nejsilnější měna vůči základní.

        Definice: měna s NEJNIŽŠÍM kurzem vůči base = za 1 jednotku base
        dostanete nejméně cizí měny = cizí měna je nejcennější.
        Příklad (base=USD): EUR=0.92, JPY=149 → strongest je EUR (0.92).
        """
        data = self.get_latest(base, symbols)
        rates = data.get("rates") or {}
        if not rates:
            raise ExchangeRateError("Žádná data pro výpočet nejsilnější měny.")
        return min(rates.items(), key=lambda x: x[1])

    def weakest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """
        FR3 — nejslabší měna vůči základní.

        Definice: měna s NEJVYŠŠÍM kurzem vůči base = za 1 jednotku base
        dostanete nejvíce cizí měny = cizí měna je nejlevnější.
        Příklad (base=USD): EUR=0.92, JPY=149 → weakest je JPY (149).
        """
        data = self.get_latest(base, symbols)
        rates = data.get("rates") or {}
        if not rates:
            raise ExchangeRateError("Žádná data pro výpočet nejslabší měny.")
        return max(rates.items(), key=lambda x: x[1])

    def average_rates(self, base: str, symbols: list[str], days: int = 7) -> dict[str, float]:
        """
        FR4 — aritmetický průměr kurzů za posledních N dní.

        Vstupy: základní měna, seznam měn, počet dní (1–365).
        Pro každou měnu spočítá průměr přes dostupné historické dny.
        Dny, kde API selže, jsou přeskočeny (nejsou zahrnuty do průměru).
        """
        if days < 1 or days > 365:
            raise ExchangeRateError("Počet dní musí být v rozsahu 1–365.")

        accumulator: dict[str, list[float]] = {s: [] for s in symbols}
        today = date.today()

        for offset in range(days):
            target = today - timedelta(days=offset)
            try:
                data = self.get_historical(target, base, symbols)
                rates = data.get("rates") or {}
                for symbol, rate in rates.items():
                    if symbol in accumulator:
                        accumulator[symbol].append(rate)
            except ExchangeRateError:
                continue  # přeskoč dny, kde API selže

        return {
            symbol: (sum(vals) / len(vals) if vals else 0.0)
            for symbol, vals in accumulator.items()
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict, retries: int = 2) -> dict:
        url = f"{self._base_url()}{path}"
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 429:
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise ExchangeRateError(f"Request failed: {exc}") from exc

            data = resp.json()
            if not data.get("success", True):
                raise ExchangeRateError(data.get("error", {}).get("info", "Unknown API error"))
            return data

        raise ExchangeRateError("Rate limit exceeded, zkus to za chvíli znovu.")

    @staticmethod
    def _extract_rates(data: dict, base: str = "") -> dict[str, float]:
        """
        Normalizuje odpověď API na slovník { "EUR": 0.92, "CZK": 23.5, ... }.

        /live vrací klíče s prefixem base měny:  { "quotes": { "USDEUR": 0.92 } }
        /historical vrací čisté klíče:           { "rates":  { "EUR": 0.92 } }

        Pokud klíče začínají base prefixem, ořízne se.
        """
        raw = data.get("rates") or data.get("quotes") or {}
        if not raw:
            return {}

        prefix_len = len(base)
        if prefix_len and any(
            k.upper().startswith(base.upper()) and len(k) > prefix_len
            for k in raw
        ):
            return {
                k[prefix_len:]: float(v)
                for k, v in raw.items()
                if k.upper().startswith(base.upper())
            }

        return {k: float(v) for k, v in raw.items()}


class ExchangeRateError(Exception):
    """Raised when the ExchangeRate API call fails."""
