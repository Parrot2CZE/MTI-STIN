from __future__ import annotations

import requests
import time
from datetime import date, timedelta
from typing import Optional
from flask import current_app


class ExchangeRateService:
    """
    Wrapper around exchangerate.host REST API (paid, access_key required).

    Definice kurzů (FR2/FR3):
      - Kurz = kolik jednotek cizí měny dostaneme za 1 jednotku základní měny.
        Příklad: base=EUR, rate CZK=25.0 → 1 EUR = 25 CZK
      - Nejsilnější měna = nejvyšší číselná hodnota kurzu
        (dostaneme za 1 EUR nejvíc jednotek → ta měna je "slabá" sama o sobě,
         ale z pohledu zadání je to "nejsilnější" dle specifikace FR2)
      - Nejslabší měna  = nejnižší číselná hodnota kurzu (FR3)
    """

    def _base_url(self) -> str:
        return current_app.config["EXCHANGERATE_BASE_URL"]

    def _api_key(self) -> str:
        return current_app.config["EXCHANGERATE_API_KEY"]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest(self, base: str = "USD", symbols: Optional[list[str]] = None) -> dict:
        """Aktuální kurzy pro *base* měnu."""
        params: dict = {"access_key": self._api_key(), "base": base}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._get("/live", params)

    def get_historical(self, target_date: date, base: str = "USD",
                       symbols: Optional[list[str]] = None) -> dict:
        """Historické kurzy pro konkrétní datum."""
        params: dict = {
            "access_key": self._api_key(),
            "base": base,
            "date": target_date.isoformat(),
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._get("/historical", params)

    # ------------------------------------------------------------------
    # Analytics (FR2, FR3, FR4)
    # ------------------------------------------------------------------

    def strongest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """
        FR2 – Nejsilnější měna = nejvyšší hodnota kurzu vůči base.
        Příklad: base=EUR, JPY=160, USD=1.10 → nejsilnější je JPY (160 > 1.10).
        """
        rates = self._extract_rates(self.get_latest(base, symbols))
        return max(rates.items(), key=lambda x: x[1])

    def weakest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """
        FR3 – Nejslabší měna = nejnižší hodnota kurzu vůči base.
        """
        rates = self._extract_rates(self.get_latest(base, symbols))
        return min(rates.items(), key=lambda x: x[1])

    def average_rates(
        self,
        base: str,
        symbols: list[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, float]:
        """
        FR4 – Aritmetický průměr kurzů pro každou měnu v rozsahu start_date..end_date.
        """
        if start_date > end_date:
            raise ValueError("start_date musí být <= end_date")

        accumulator: dict[str, list[float]] = {s: [] for s in symbols}
        current = start_date

        while current <= end_date:
            try:
                data = self.get_historical(current, base, symbols)
                rates = self._extract_rates(data)
                for symbol, rate in rates.items():
                    if symbol in accumulator:
                        accumulator[symbol].append(rate)
            except ExchangeRateError:
                pass  # přeskočíme dny kde API selže
            current += timedelta(days=1)

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

        raise ExchangeRateError("Rate limit překročen, zkus to za chvíli znovu.")

    @staticmethod
    def _extract_rates(data: dict) -> dict[str, float]:
        return data.get("rates") or data.get("quotes") or {}


class ExchangeRateError(Exception):
    """Vyvolána při selhání ExchangeRate API volání."""
