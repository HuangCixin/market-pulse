"""Turn prices into moves, the 3D float layout, and cross-market relationships.

Everything here returns plain numbers; market/report.py turns them into the page.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS = {"day": 1, "week": 7, "month": 30}  # calendar days per period


# ---------------------------------------------------------------- moves
def _own_moves(s: pd.Series, kind: str) -> pd.Series:
    s = s.dropna()
    return s.diff() if kind == "yield" else np.log(s).diff()


def daily_moves(prices: pd.DataFrame, kinds: dict[str, str]) -> pd.DataFrame:
    """Daily moves on each asset's own calendar (holidays stay NaN, never filled).

    price assets -> log return; yield assets -> change in percentage points.
    """
    return pd.DataFrame({c: _own_moves(prices[c], kinds.get(c, "price")) for c in prices}).sort_index()


def corr_moves(prices: pd.DataFrame, kinds: dict[str, str]) -> pd.DataFrame:
    """Moves used for correlations: every asset sampled on weekdays only.

    Crypto trades on weekends. Its Monday move must cover Fri->Mon, like stocks,
    otherwise crypto-vs-stock correlations are understated.
    """
    wk = prices[prices.index.dayofweek < 5]
    return daily_moves(wk, kinds)


def _fmt_move(kind: str, raw: float) -> float:
    """Raw move -> human units: % for prices, basis points for yields."""
    return raw * 100 if kind == "yield" else (np.exp(raw) - 1) * 100


# ---------------------------------------------------------------- correlations
def correlation(moves: pd.DataFrame, window: int) -> pd.DataFrame:
    return moves.tail(window).corr(min_periods=max(20, window // 3))


def rolling_corr(moves: pd.DataFrame, a: str, b: str, window: int) -> pd.Series:
    pair = moves[[a, b]].dropna()
    return pair[a].rolling(window, min_periods=window // 2).corr(pair[b])


def corr_shifts(short: pd.DataFrame, long: pd.DataFrame, top: int = 8) -> list[dict]:
    rows = []
    cols = list(short.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            s, l = short.loc[a, b], long.loc[a, b]
            if pd.notna(s) and pd.notna(l):
                rows.append({"a": a, "b": b, "short": round(float(s), 3),
                             "long": round(float(l), 3), "change": round(float(s - l), 3)})
    rows.sort(key=lambda r: -abs(r["change"]))
    return rows[:top]


def us_to_china_leadlag(moves: pd.DataFrame, regions: dict[str, str], window: int) -> dict:
    """Correlation of the previous US trading day's move with today's China move.

    Asia closes before New York opens, so a US move on day t shows up in China on t+1.
    """
    us = [c for c in moves if regions.get(c) == "US"]
    cn = [c for c in moves if regions.get(c) == "China"]
    recent = moves.tail(window + 1)
    out = {}
    for u in us:
        lagged = recent[u].dropna().shift(1)
        out[u] = {}
        for c in cn:
            pair = pd.concat([lagged, recent[c]], axis=1, join="inner").dropna()
            v = pair.iloc[:, 0].corr(pair.iloc[:, 1]) if len(pair) > 20 else np.nan
            out[u][c] = None if pd.isna(v) else round(float(v), 3)
    return out


# ---------------------------------------------------------------- 3D float layout
def mds_positions(corr: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Place assets on a plane so assets that move together sit close together.

    Classical multidimensional scaling on distance d = sqrt(2 * (1 - corr)).
    """
    names = list(corr.columns)
    c = corr.fillna(0).values.copy()
    np.fill_diagonal(c, 1)
    d2 = 2 * (1 - c)
    n = len(names)
    j = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * j @ d2 @ j
    vals, vecs = np.linalg.eigh(b)
    order = np.argsort(vals)[::-1][:2]
    xy = vecs[:, order] * np.sqrt(np.maximum(vals[order], 1e-9))
    xy -= xy.mean(axis=0)
    xy /= np.abs(xy).max() or 1
    # outliers stretch the map and crowd the centre: compress radii (keeps direction and order)
    r = np.hypot(xy[:, 0], xy[:, 1])
    xy = xy * (np.where(r > 1e-9, r ** 0.5 / np.maximum(r, 1e-9), 1))[:, None]
    # gentle repulsion so tightly linked markets stay close but never overlap
    dmin = 0.3
    for _ in range(300):
        moved = False
        for i in range(n):
            for k in range(i + 1, n):
                d = xy[i] - xy[k]
                dist = float(np.hypot(*d))
                if dist < dmin:
                    push = (d / dist if dist > 1e-6 else np.array([1.0, 0.0])) * (dmin - dist) / 2
                    xy[i] += push; xy[k] -= push; moved = True
        if not moved:
            break
    xy -= xy.mean(axis=0)
    xy /= np.abs(xy).max() or 1
    return {nm: (round(float(x), 4), round(float(y), 4)) for nm, (x, y) in zip(names, xy)}


def float_frames(prices: pd.DataFrame, kinds: dict[str, str], n_dates: int = 120) -> dict:
    """For each of the last n_dates calendar dates and each period, every asset's
    move in sigma units (move / typical move for that period) and in human units.

    Sigma makes a 0.3% FX move and a 4% crypto move comparable: both say
    "how unusual was this for that asset?". Day values are None when a market
    was closed that day.
    """
    all_dates = prices.dropna(how="all").index
    dates = all_dates[-n_dates:]
    out = {p: {} for p in PERIODS}
    for col in prices.columns:
        kind = kinds.get(col, "price")
        s = prices[col].dropna()
        mv = _own_moves(s, kind)
        sd = mv.rolling(60, min_periods=20).std().shift(1)  # vol known *before* the day
        per = {p: {"z": [], "v": []} for p in PERIODS}
        for d in dates:
            hist = s[s.index <= d]
            if len(hist) < 25:
                for p in PERIODS:
                    per[p]["z"].append(None); per[p]["v"].append(None)
                continue
            last_d = hist.index[-1]
            vol = sd.get(last_d, np.nan)
            for p, days in PERIODS.items():
                if p == "day":
                    if last_d != d:  # market closed that day
                        per[p]["z"].append(None); per[p]["v"].append(None)
                        continue
                    raw, n = mv.get(d, np.nan), 1
                else:
                    base = hist[hist.index <= d - pd.Timedelta(days=days)]
                    if base.empty:
                        per[p]["z"].append(None); per[p]["v"].append(None)
                        continue
                    a, b = base.iloc[-1], hist.iloc[-1]
                    raw = (b - a) if kind == "yield" else np.log(b / a)
                    n = max(1, ((hist.index > base.index[-1]) & (hist.index <= d)).sum())
                ok = pd.notna(raw) and pd.notna(vol) and vol > 0
                per[p]["z"].append(round(float(raw / (vol * np.sqrt(n))), 3) if ok else None)
                per[p]["v"].append(round(float(_fmt_move(kind, raw)), 3) if pd.notna(raw) else None)
        for p in PERIODS:
            out[p][col] = per[p]
    # latest date on which at least half the markets traded (weekends: only crypto is open)
    open_counts = [sum(out["day"][c]["z"][k] is not None for c in out["day"]) for k in range(len(dates))]
    main_idx = max((k for k, n in enumerate(open_counts) if n >= len(out["day"]) / 2), default=len(dates) - 1)
    return {"dates": [d.date().isoformat() for d in dates], "periods": out, "main_idx": main_idx}


# ---------------------------------------------------------------- performance
def performance(prices: pd.DataFrame, kinds: dict[str, str]) -> dict:
    rows = {}
    for col in prices.columns:
        s = prices[col].dropna()
        if len(s) < 2:
            continue
        kind = kinds.get(col, "price")
        last, last_date = s.iloc[-1], s.index[-1]

        def ref(days):
            past = s[s.index <= last_date - pd.Timedelta(days=days)]
            return past.iloc[-1] if len(past) else np.nan

        ytd = s[s.index < pd.Timestamp(last_date.year, 1, 1)]
        refs = {"1D": s.iloc[-2], "1W": ref(7), "1M": ref(30), "3M": ref(91),
                "1Y": ref(365), "YTD": ytd.iloc[-1] if len(ytd) else np.nan}
        row = {"last": round(float(last), 4), "date": last_date.date().isoformat()}
        for k, r in refs.items():
            if pd.isna(r):
                row[k] = None
            else:
                raw = (last - r) if kind == "yield" else np.log(last / r)
                row[k] = round(float(_fmt_move(kind, raw)), 3)
        rows[col] = row
    return rows


def regime(frames: dict, groups: dict[str, str], period: str = "day") -> dict:
    """A price-based risk-on / risk-off read for the latest date.

    Not actual fund flows: it reads where prices pushed relative to normal.
    """
    k = frames["main_idx"]
    z = {name: v["z"][k] for name, v in frames["periods"][period].items()}

    def avg(names):
        vals = [z[n] for n in names if n in z and z[n] is not None]
        return float(np.mean(vals)) if vals else 0.0

    stocks = [n for n, g in groups.items() if g in ("US Stocks", "China Stocks")]
    crypto = [n for n, g in groups.items() if g == "Crypto"]
    havens = [n for n in ("Gold", "VIX", "USD/JPY") if n in z]
    # USD/JPY falling = yen strengthening = haven demand, so flip its sign
    haven_vals = [(-z[n] if n == "USD/JPY" else z[n]) for n in havens if z[n] is not None]
    haven = float(np.mean(haven_vals)) if haven_vals else 0.0
    score = (avg(stocks) * 2 + avg(crypto)) / 3 - haven
    label = "Risk-on" if score > 0.5 else "Risk-off" if score < -0.5 else "Mixed"
    return {"score": round(score, 2), "label": label}


# ---------------------------------------------------------------- main entry
def run_analysis(prices: pd.DataFrame, cfg: dict) -> dict:
    assets = [a for a in cfg["assets"] if a["name"] in prices.columns]
    kinds = {a["name"]: a.get("kind", "price") for a in assets}
    regions = {a["name"]: a.get("region", "Global") for a in assets}
    groups = {a["name"]: a.get("group", "Other") for a in assets}
    w_short, w_long = cfg.get("corr_windows", [60, 250])
    w_roll = cfg.get("rolling_window", 60)
    prices = prices[[a["name"] for a in assets]]

    cm = corr_moves(prices, kinds)
    corr_s, corr_l = correlation(cm, w_short), correlation(cm, w_long)
    frames = float_frames(prices, kinds, cfg.get("float_days", 120))
    pairs = [p for p in cfg.get("key_pairs", []) if p[0] in cm and p[1] in cm]
    rolling = {}
    for a, b in pairs:
        r = rolling_corr(cm, a, b, w_roll).dropna().tail(500)
        rolling[f"{a} / {b}"] = {"dates": [d.date().isoformat() for d in r.index],
                                 "values": [round(float(v), 3) for v in r.values]}
    # one year of prices for the line charts (weekly-thinned beyond 6 months keeps the file small)
    recent = prices[prices.index >= prices.index[-1] - pd.Timedelta(days=380)]
    lines = {c: {"dates": [d.date().isoformat() for d in recent[c].dropna().index],
                 "values": [round(float(v), 4) for v in recent[c].dropna().values]} for c in prices}

    def clean(df):
        return [[None if pd.isna(v) else round(float(v), 3) for v in row] for row in df.values]

    return {
        "as_of": frames["dates"][frames["main_idx"]],
        "data_end": frames["dates"][-1],
        "assets": [{"name": a["name"], "group": groups[a["name"]], "region": regions[a["name"]],
                    "kind": kinds[a["name"]], "ticker": a["ticker"]} for a in assets],
        "positions": mds_positions(corr_l),
        "float": frames,
        "performance": performance(prices, kinds),
        "regime": {p: regime(frames, groups, p) for p in PERIODS},
        "corr": {"names": list(corr_s.columns), "short": clean(corr_s), "long": clean(corr_l),
                 "w_short": w_short, "w_long": w_long},
        "shifts": corr_shifts(corr_s, corr_l),
        "leadlag": us_to_china_leadlag(cm, regions, w_short),
        "rolling": rolling, "w_roll": w_roll,
        "lines": lines,
    }
