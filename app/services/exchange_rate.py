from __future__ import annotations

import requests
import time
from datetime import date, timedelta
from typing import Optional
from flask import current_app


class ExchangeRateService:
    """Wrapper around exchangerate.host REST API (paid, access_key required)."""

    def _base_url(self) -> str:
        return current_app.config["EXCHANGERATE_BASE_URL"]

    def _api_key(self) -> str:
        return current_app.config["EXCHANGERATE_API_KEY"]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_latest(self, base: str = "USD", symbols: Optional[list[str]] = None) -> dict:
        """Return latest exchange rates for *base* currency."""
        params: dict = {"access_key": self._api_key(), "base": base}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._get("/live", params)

    def get_historical(self, target_date: date, base: str = "USD",
                       symbols: Optional[list[str]] = None) -> dict:
        """Return historical rates for a single date."""
        params: dict = {
            "access_key": self._api_key(),
            "base": base,
            "date": target_date.isoformat(),
        }
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._get("/historical", params)

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def strongest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """Currency with the LOWEST rate vs base (= worth the most)."""
        rates = self._extract_rates(self.get_latest(base, symbols))
        return min(rates.items(), key=lambda x: x[1])

    def weakest_currency(self, base: str, symbols: list[str]) -> tuple[str, float]:
        """Currency with the HIGHEST rate vs base (= worth the least)."""
        rates = self._extract_rates(self.get_latest(base, symbols))
        return max(rates.items(), key=lambda x: x[1])

    def average_rates(self, base: str, symbols: list[str], days: int = 7) -> dict[str, float]:
        """Average rates for each symbol over the last *days* days."""
        accumulator: dict[str, list[float]] = {s: [] for s in symbols}
        today = date.today()

        for offset in range(days):
            target = today - timedelta(days=offset)
            try:
                data = self.get_historical(target, base, symbols)
                rates = self._extract_rates(data)
                for symbol, rate in rates.items():
                    if symbol in accumulator:
                        accumulator[symbol].append(rate)
            except ExchangeRateError:
                continue  # skip days that fail

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
                    # Rate limited — wait and retry
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
    def _extract_rates(data: dict) -> dict[str, float]:
        # exchangerate.host returns rates under 'quotes' or 'rates'
        return data.get("rates") or data.get("quotes") or {}


class ExchangeRateError(Exception):
    """Raised when the ExchangeRate API call fails."""