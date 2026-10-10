"""Download daily closing prices, with a local CSV cache.

Prices are stored wide: one column per asset name, indexed by date.
Each market keeps its own trading calendar, so holidays show up as NaN
(they are NOT forward-filled here; analysis handles gaps explicitly).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "data" / "prices.csv"


def fetch_prices(assets: list[dict], lookback_days: int, use_cache: bool = True) -> pd.DataFrame:
    """Return a DataFrame of daily closes (columns = asset names)."""
    import yfinance as yf  # imported lazily so --demo works without it

    start = dt.date.today() - dt.timedelta(days=lookback_days)
    tickers = [a["ticker"] for a in assets]
    raw = yf.download(tickers, start=start.isoformat(), interval="1d",
                      auto_adjust=True, progress=False, group_by="column", threads=True)
    if raw is None or raw.empty:
        if use_cache and CACHE.exists():
            print("! Download returned nothing; using cached prices.")
            return load_cache()
        raise RuntimeError("No data downloaded and no cache available.")

    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if not isinstance(raw.columns, pd.MultiIndex):  # single ticker case
        close.columns = tickers

    by_ticker = {a["ticker"]: a["name"] for a in assets}
    missing = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
    for t in missing:
        print(f"! No data for {by_ticker[t]} ({t}); it will be skipped.")

    prices = close[[t for t in tickers if t not in missing]].rename(columns=by_ticker)
    prices.index = pd.to_datetime(prices.index).tz_localize(None).normalize()
    prices = prices.sort_index().dropna(how="all")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(CACHE)
    return prices


def load_cache() -> pd.DataFrame:
    return pd.read_csv(CACHE, index_col=0, parse_dates=True)


def demo_prices(assets: list[dict], n_days: int = 730, seed: int = 7) -> pd.DataFrame:
    """Synthetic but realistic-looking prices for offline testing (--demo).

    Uses a few latent factors (global risk, US dollar, China, energy) so the
    correlation structure looks like real markets, plus market holidays.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n_days, freq="D")
    weekend = dates.dayofweek >= 5
    f = {k: rng.normal(0, 1, n_days) for k in ["risk", "usd", "china", "energy", "rates", "crypto"]}
    loadings = {
        "Gold": dict(usd=-0.5, rates=-0.3), "Silver": dict(usd=-0.5, rates=-0.2, risk=0.3),
        "WTI Oil": dict(energy=1.0, risk=0.3), "Brent Oil": dict(energy=1.0, risk=0.25),
        "Copper": dict(risk=0.4, china=0.4), "S&P 500": dict(risk=0.9),
        "Nasdaq": dict(risk=1.0, rates=-0.2), "Dow Jones": dict(risk=0.8),
        "VIX": dict(risk=-0.8), "Shanghai Comp": dict(china=0.9, risk=0.15),
        "CSI 300": dict(china=0.95, risk=0.2), "Shenzhen Comp": dict(china=0.9, risk=0.2),
        "Hang Seng": dict(china=0.7, risk=0.4), "Dollar Index": dict(usd=1.0),
        "EUR/USD": dict(usd=-0.9), "USD/CNY": dict(usd=0.4, china=-0.3),
        "USD/JPY": dict(usd=0.6, rates=0.4), "US 10Y Yield": dict(rates=1.0, risk=0.2),
        "Bitcoin": dict(crypto=1.0, risk=0.4), "Ethereum": dict(crypto=1.0, risk=0.45),
        "Solana": dict(crypto=0.9, risk=0.5),
    }
    vol = {"VIX": 0.06, "WTI Oil": 0.022, "Brent Oil": 0.02, "US 10Y Yield": 0.05,
           "USD/CNY": 0.002, "EUR/USD": 0.004, "Dollar Index": 0.004, "USD/JPY": 0.006,
           "Bitcoin": 0.03, "Ethereum": 0.04, "Solana": 0.05}
    start = {"Gold": 2400, "Silver": 29, "WTI Oil": 75, "Brent Oil": 79, "Copper": 4.3,
             "S&P 500": 5500, "Nasdaq": 17500, "Dow Jones": 41000, "VIX": 16,
             "Shanghai Comp": 3000, "CSI 300": 3600, "Shenzhen Comp": 9500, "Hang Seng": 18000,
             "Dollar Index": 103, "EUR/USD": 1.09, "USD/CNY": 7.15, "USD/JPY": 148, "US 10Y Yield": 4.2,
             "Bitcoin": 95000, "Ethereum": 3500, "Solana": 180}
    cols = {}
    for a in assets:
        name = a["name"]
        load = loadings.get(name, dict(risk=0.5))
        common = sum(w * f[k] for k, w in load.items())
        scale = np.sqrt(sum(w * w for w in load.values()) + 0.35)
        z = (common + rng.normal(0, 0.6, n_days)) / scale
        s = vol.get(name, 0.012) * z + 0.0002
        p0 = start.get(name, 100.0)
        if name == "VIX":  # volatility mean-reverts instead of trending
            lv = np.zeros(n_days)
            for t in range(1, n_days):
                lv[t] = 0.95 * lv[t - 1] + s[t] * 1.2
            series = p0 * np.exp(lv)
        elif a.get("kind") == "yield":
            series = p0 + np.cumsum(s * 1.5)
        else:
            series = p0 * np.exp(np.cumsum(s))
        ser = pd.Series(series, index=dates)
        if a.get("group") != "Crypto":  # traditional markets: closed weekends + holidays
            holidays = rng.random(n_days) < (0.04 if a.get("region") == "China" else 0.015)
            ser[weekend | holidays] = np.nan
        cols[name] = ser
    return pd.DataFrame(cols)
