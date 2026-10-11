"""Intraday rules: trading sessions, unfinished bars, live crypto inputs. Run with: pytest"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from market import analyze
from market.fetch import demo_prices
from market.sessions import final_prices, market_status, session_status

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
SES = CFG["sessions"]
UTC = dt.timezone.utc


def at(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=UTC)


D = dt.date


# 2026-10-13 is a Tuesday; New York is UTC-4, Chicago UTC-5, London UTC+1, Shanghai UTC+8 in October.
@pytest.mark.parametrize("sess,now,expected", [
    ("us", at(2026, 10, 13, 13, 0), ("pre", D(2026, 10, 13))),        # 09:00 New York
    ("us", at(2026, 10, 13, 14, 7), ("live", D(2026, 10, 13))),
    ("us", at(2026, 10, 13, 20, 30), ("closed", D(2026, 10, 13))),     # 16:30 New York
    ("us", at(2026, 10, 17, 15, 0), ("off", None)),                    # Saturday
    ("china", at(2026, 10, 13, 3, 0), ("live", D(2026, 10, 13))),      # 11:00 Shanghai
    ("china", at(2026, 10, 13, 4, 30), ("live", D(2026, 10, 13))),     # lunch break: the bar is not final yet
    ("china", at(2026, 10, 13, 7, 30), ("closed", D(2026, 10, 13))),   # 15:30 Shanghai
    ("china", at(2026, 10, 12, 23, 0), ("pre", D(2026, 10, 13))),      # Tue 07:00 Shanghai, Mon evening UTC
    ("futures", at(2026, 10, 13, 15, 0), ("live", D(2026, 10, 13))),   # 10:00 Chicago
    ("futures", at(2026, 10, 13, 21, 30), ("closed", D(2026, 10, 13))),  # 16:30 Chicago: daily break
    ("futures", at(2026, 10, 13, 22, 30), ("live", D(2026, 10, 14))),  # 17:30 Chicago: next trading date
    ("futures", at(2026, 10, 16, 22, 30), ("off", None)),              # Friday evening
    ("futures", at(2026, 10, 18, 22, 30), ("live", D(2026, 10, 19))),  # Sunday evening opens Monday
    ("fx", at(2026, 10, 13, 23, 30), ("live", D(2026, 10, 14))),       # 00:30 London
    ("fx", at(2026, 10, 17, 12, 0), ("off", None)),
    ("crypto", at(2026, 10, 17, 12, 0), ("live", D(2026, 10, 17))),
])
def test_session_status(sess, now, expected):
    assert session_status(SES[sess], now) == expected


def test_unknown_session():
    assert session_status(None, at(2026, 10, 13, 12, 0)) == ("unknown", None)


def _prices(end: str):
    idx = pd.date_range(end=end, periods=40, freq="D")
    rng = np.random.default_rng(1)
    us = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 40))), index=idx)
    cn = pd.Series(50 * np.exp(np.cumsum(rng.normal(0, 0.01, 40))), index=idx)
    us[idx.dayofweek >= 5] = np.nan
    cn[idx.dayofweek >= 5] = np.nan
    return pd.DataFrame({"S&P 500": us, "CSI 300": cn})


ASSETS = [{"name": "S&P 500", "session": "us"}, {"name": "CSI 300", "session": "china"}]


def test_only_the_bar_of_an_open_market_is_unfinished():
    p = _prices("2026-10-13")
    st = market_status(p, ASSETS, SES, at(2026, 10, 13, 14, 7))
    assert st["S&P 500"]["partial"] and not st["CSI 300"]["partial"]
    f = final_prices(p, st)
    assert np.isnan(f.loc["2026-10-13", "S&P 500"]) and f.loc["2026-10-13", "CSI 300"] == p.loc["2026-10-13", "CSI 300"]
    assert f.loc["2026-10-12", "S&P 500"] == p.loc["2026-10-12", "S&P 500"]       # earlier days untouched


def test_before_the_open_yesterday_is_final():
    p = _prices("2026-10-12")                                  # no Tuesday bar yet
    st = market_status(p, ASSETS, SES, at(2026, 10, 13, 13, 0))
    assert st["S&P 500"] == {"status": "pre", "session_date": "2026-10-13", "bar_date": "2026-10-12", "partial": False}


@pytest.fixture(scope="module")
def live_res():
    prices = demo_prices(CFG["assets"])
    last = prices.index[-1]
    now = dt.datetime(last.year, last.month, last.day, 12, 0, tzinfo=UTC)
    return analyze.run_analysis(prices, CFG, now=now), prices, now


def test_unfinished_bars_stay_out_of_correlations(live_res):
    res, prices, now = live_res
    st = res["live"]["status"]
    partial = [n for n, s in st.items() if s["partial"]]
    assert "Bitcoin" in partial                                 # crypto always trades
    expected = analyze.correlation(analyze.corr_moves(final_prices(prices, st), {a["name"]: a.get("kind", "price") for a in CFG["assets"]}), res["corr"]["w_short"])
    got = np.array(res["corr"]["short"], dtype=float)
    assert np.allclose(np.nan_to_num(got), np.nan_to_num(expected.round(3).values))


def test_live_crypto_inputs_reproduce_the_built_sigma(live_res):
    res, prices, now = live_res
    for c in res["live"]["crypto"]:
        for per, ref in c["refs"].items():
            z = np.log(c["last"] / ref) / (c["vol"] * np.sqrt(c["n"][per]))
            assert z == pytest.approx(res["float"]["periods"][per][c["name"]]["z"][c["idx"]], abs=2e-3)
        assert (c["last"] / c["perf_refs"]["1W"] - 1) * 100 == pytest.approx(res["performance"][c["name"]]["1W"], abs=2e-3)


def test_demo_and_cache_builds_have_no_live_parts(cfg=CFG):
    res = analyze.run_analysis(demo_prices(cfg["assets"]), cfg)
    assert res["live"]["status"] == {} and res["live"]["crypto"] == [] and res["live"]["intraday"] is False
