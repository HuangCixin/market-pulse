"""Turn prices into returns, performance tables and cross-asset relationships."""
from __future__ import annotations

import numpy as np
import pandas as pd


def daily_moves(prices: pd.DataFrame, kinds: dict[str, str]) -> pd.DataFrame:
    """Daily moves per asset, computed on each asset's own trading days.

    price assets -> log return; yield assets -> change in percentage points.
    Holidays stay NaN so no fake zero-return days enter correlations.
    """
    out = {}
    for col in prices.columns:
        s = prices[col].dropna()
        if kinds.get(col) == "yield":
            out[col] = s.diff()
        else:
            out[col] = np.log(s).diff()
    return pd.DataFrame(out).sort_index()


def performance(prices: pd.DataFrame, kinds: dict[str, str]) -> pd.DataFrame:
    """Last close and 1D / 1W / 1M / 3M / YTD changes for every asset."""
    rows = []
    for col in prices.columns:
        s = prices[col].dropna()
        if len(s) < 2:
            continue
        last, last_date = s.iloc[-1], s.index[-1]

        def ago(days):
            past = s[s.index <= last_date - pd.Timedelta(days=days)]
            return past.iloc[-1] if len(past) else np.nan

        ytd_base = s[s.index < pd.Timestamp(last_date.year, 1, 1)]
        refs = {"1D": s.iloc[-2], "1W": ago(7), "1M": ago(30), "3M": ago(91),
                "YTD": ytd_base.iloc[-1] if len(ytd_base) else np.nan}
        row = {"asset": col, "last": last, "date": last_date.date().isoformat()}
        for k, ref in refs.items():
            if kinds.get(col) == "yield":
                row[k] = (last - ref) * 100  # basis points
            else:
                row[k] = (last / ref - 1) * 100  # percent
        # 1D move vs. its own recent volatility -> "how unusual was today?"
        moves = daily_moves(s.to_frame(col), kinds)[col].dropna().tail(61)
        sd = moves.iloc[:-1].std()
        row["z_1D"] = moves.iloc[-1] / sd if sd and len(moves) > 20 else np.nan
        row["vol_60d_ann"] = sd * np.sqrt(252) * (100 if kinds.get(col) != "yield" else 100)
        rows.append(row)
    return pd.DataFrame(rows).set_index("asset")


def correlation(moves: pd.DataFrame, window: int, min_obs: int | None = None) -> pd.DataFrame:
    """Pairwise correlation over the last `window` rows (pairwise-complete)."""
    recent = moves.tail(window)
    return recent.corr(min_periods=min_obs or max(20, window // 3))


def rolling_corr(moves: pd.DataFrame, a: str, b: str, window: int) -> pd.Series:
    pair = moves[[a, b]].dropna()
    return pair[a].rolling(window, min_periods=window // 2).corr(pair[b])


def corr_shifts(short: pd.DataFrame, long: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Pairs whose short-window correlation moved most vs. the long-window norm."""
    rows = []
    cols = list(short.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            s, l = short.loc[a, b], long.loc[a, b]
            if pd.notna(s) and pd.notna(l):
                rows.append({"pair": f"{a} / {b}", "short": s, "long": l, "change": s - l})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.reindex(df["change"].abs().sort_values(ascending=False).index).head(top)


def us_to_china_leadlag(moves: pd.DataFrame, regions: dict[str, str], window: int) -> pd.DataFrame:
    """Correlation of yesterday's US move with today's China move.

    Asian markets close before the US opens, so a US move on day t is
    priced into China on day t+1. Same-day correlation understates the link.
    """
    us = [c for c in moves.columns if regions.get(c) == "US"]
    cn = [c for c in moves.columns if regions.get(c) == "China"]
    recent = moves.tail(window + 1)
    out = pd.DataFrame(index=us, columns=cn, dtype=float)
    for u in us:
        lagged = recent[u].dropna().shift(1)  # previous US trading day
        for c in cn:
            pair = pd.concat([lagged, recent[c]], axis=1, join="inner").dropna()
            out.loc[u, c] = pair.iloc[:, 0].corr(pair.iloc[:, 1]) if len(pair) > 20 else np.nan
    return out


def run_analysis(prices: pd.DataFrame, cfg: dict) -> dict:
    assets = [a for a in cfg["assets"] if a["name"] in prices.columns]
    kinds = {a["name"]: a.get("kind", "price") for a in assets}
    regions = {a["name"]: a.get("region", "Global") for a in assets}
    groups = {a["name"]: a.get("group", "Other") for a in assets}
    w_short, w_long = cfg.get("corr_windows", [60, 250])
    w_roll = cfg.get("rolling_window", 60)

    moves = daily_moves(prices, kinds)
    corr_s, corr_l = correlation(moves, w_short), correlation(moves, w_long)
    pairs = [p for p in cfg.get("key_pairs", []) if p[0] in moves and p[1] in moves]
    return {
        "as_of": prices.dropna(how="all").index[-1].date().isoformat(),
        "kinds": kinds, "regions": regions, "groups": groups,
        "prices": prices, "moves": moves,
        "performance": performance(prices, kinds),
        "corr_short": corr_s, "corr_long": corr_l, "w_short": w_short, "w_long": w_long,
        "shifts": corr_shifts(corr_s, corr_l),
        "leadlag": us_to_china_leadlag(moves, regions, w_short),
        "rolling": {f"{a} / {b}": rolling_corr(moves, a, b, w_roll) for a, b in pairs},
        "w_roll": w_roll,
    }
