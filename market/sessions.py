"""Trading sessions: is a market open right now, and is its latest daily bar still forming?

Pages are rebuilt during the trading day. A market that is still trading has a daily bar that will
keep changing until its close; such a bar is "partial". Partial bars are shown (that is the point of
an intraday update) but kept out of correlations and the US -> China lead/lag, which need finished days.

Sessions are defined in config.yaml (`sessions:`) and attached to each market (`session:`).
Exchange holidays are not modelled: on a holiday a market looks "open" but has no bar for the day,
which shows up as "waiting for today's data".
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)          # "24:00" -> 1440 (open until midnight)


def session_status(sess: dict | None, now: dt.datetime) -> tuple[str, dt.date | None]:
    """Return (status, trading_date) at `now` (timezone-aware).

    status: "live"   - trading now; trading_date is the date of the bar being formed
            "pre"    - a trading day, before the open (today's bar has not started)
            "closed" - a trading day, after the close (today's bar is final)
            "off"    - no session today (weekend)
            "unknown"- no session configured
    Overnight sessions (futures) start the evening before their trading date.
    """
    if not sess:
        return "unknown", None
    if sess.get("always"):
        return "live", now.astimezone(ZoneInfo(sess.get("tz", "UTC"))).date()
    loc = now.astimezone(ZoneInfo(sess["tz"]))
    mins, today = loc.hour * 60 + loc.minute, loc.date()
    o, c = _minutes(sess["open"]), _minutes(sess["close"])
    days = set(sess.get("days", [0, 1, 2, 3, 4]))
    if sess.get("overnight"):
        if mins >= o:                                    # evening session of the next trading date
            nxt = today + dt.timedelta(days=1)
            return ("live", nxt) if nxt.weekday() in days else ("off", None)
        if today.weekday() not in days:
            return "off", None
        return ("live", today) if mins < c else ("closed", today)
    if today.weekday() not in days:
        return "off", None
    if mins < o:
        return "pre", today
    return ("live", today) if mins < c else ("closed", today)


def market_status(prices: pd.DataFrame, assets: list[dict], sessions: dict, now: dt.datetime) -> dict:
    """Per market: session status, the date of its latest bar, and whether that bar is still forming."""
    out = {}
    for a in assets:
        name = a["name"]
        if name not in prices:
            continue
        s = prices[name].dropna()
        if s.empty:
            continue
        bar = s.index[-1].date()
        st, td = session_status(sessions.get(a.get("session")) if sessions else None, now)
        out[name] = {"status": st, "session_date": td.isoformat() if td else None,
                     "bar_date": bar.isoformat(), "partial": bool(st == "live" and bar == td)}
    return out


def final_prices(prices: pd.DataFrame, status: dict) -> pd.DataFrame:
    """Prices with every partial (still forming) last bar removed, as if that day had not happened yet."""
    out = prices.copy()
    for name, st in status.items():
        if st.get("partial") and name in out:
            last = out[name].last_valid_index()
            if last is not None:
                out.loc[last, name] = float("nan")
    return out
