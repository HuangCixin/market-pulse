"""Tests for the analysis rules in docs/METHODOLOGY.md. Run with: pytest"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from market import analyze
from market.fetch import demo_prices
from market.report import headlines, write_report

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prices(cfg):
    return demo_prices(cfg["assets"])


@pytest.fixture(scope="module")
def res(prices, cfg):
    return analyze.run_analysis(prices, cfg)


# ---------- moves
def test_price_moves_are_log_returns():
    idx = pd.date_range("2026-01-05", periods=3, freq="B")
    p = pd.DataFrame({"A": [100.0, 110.0, 99.0]}, index=idx)
    mv = analyze.daily_moves(p, {"A": "price"})["A"].dropna()
    assert mv.tolist() == pytest.approx([np.log(1.1), np.log(0.9)])


def test_yield_moves_are_point_changes():
    idx = pd.date_range("2026-01-05", periods=3, freq="B")
    p = pd.DataFrame({"Y": [4.00, 4.10, 4.05]}, index=idx)
    mv = analyze.daily_moves(p, {"Y": "yield"})["Y"].dropna()
    assert mv.tolist() == pytest.approx([0.10, -0.05])


def test_holidays_are_not_filled():
    """A closed day must not become a fake 0% move."""
    idx = pd.date_range("2026-01-05", periods=4, freq="B")
    p = pd.DataFrame({"A": [100.0, np.nan, 102.0, 103.0]}, index=idx)
    mv = analyze.daily_moves(p, {"A": "price"})["A"]
    closed = idx[1]
    assert closed not in mv.index or np.isnan(mv[closed])       # closed day gets no move
    assert mv[idx[2]] == pytest.approx(np.log(102 / 100))       # next move spans the gap
    assert (mv.dropna() != 0).all()


def test_correlations_use_weekdays_only():
    """Crypto's Monday move must span Friday -> Monday, like a stock's."""
    idx = pd.date_range("2026-01-02", periods=4, freq="D")      # Fri, Sat, Sun, Mon
    p = pd.DataFrame({"BTC": [100.0, 120.0, 90.0, 110.0]}, index=idx)
    mv = analyze.corr_moves(p, {"BTC": "price"})["BTC"].dropna()
    assert len(mv) == 1
    assert mv.iloc[0] == pytest.approx(np.log(110 / 100))


# ---------- correlation layout
def test_mds_places_correlated_markets_close():
    names = ["A", "B", "C"]
    corr = pd.DataFrame([[1, 0.95, -0.8], [0.95, 1, -0.75], [-0.8, -0.75, 1]], index=names, columns=names)
    pos = analyze.mds_positions(corr)
    d = lambda a, b: np.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1])
    assert d("A", "B") < d("A", "C")
    assert all(abs(v) <= 1.0 + 1e-9 for xy in pos.values() for v in xy)


def test_leadlag_detects_next_day_spillover():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2025-01-01", periods=120)
    us = pd.Series(rng.normal(0, 0.01, 120), index=idx)
    cn = us.shift(1) * 0.8 + rng.normal(0, 0.003, 120)         # China follows the US a day later
    moves = pd.DataFrame({"SPX": us, "CSI": cn})
    out = analyze.us_to_china_leadlag(moves, {"SPX": "US", "CSI": "China"}, 60)
    assert out["SPX"]["CSI"] > 0.8


# ---------- full pipeline on demo data
def test_sigma_values_are_reasonable(res):
    z = [v for s in res["float"]["periods"]["day"].values() for v in s["z"] if v is not None]
    assert len(z) > 1000
    assert 0.6 < np.std(z) < 1.6                                # roughly unit scale
    assert max(abs(v) for v in z) < 10


def test_main_trading_day_has_most_markets_open(res):
    day = res["float"]["periods"]["day"]
    k = res["float"]["main_idx"]
    open_now = sum(s["z"][k] is not None for s in day.values())
    assert open_now >= len(day) / 2
    assert res["as_of"] == res["float"]["dates"][k]


def test_every_market_has_position_and_chinese_name(res):
    for a in res["assets"]:
        assert a["name"] in res["positions"]
        assert a["name_zh"]


def test_headlines_exist_in_both_languages(res):
    en, zh = headlines(res), headlines(res, "zh")
    assert len(en) == len(zh) >= 2
    assert any("一" <= ch <= "鿿" for ch in "".join(zh))


def test_report_is_self_contained(res, tmp_path):
    page = write_report(res, tmp_path)
    html = page.read_text(encoding="utf-8")
    assert "/*__DATA__*/" not in html                           # data was embedded
    assert "<script src=" not in html and "<link " not in html  # no external dependencies
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert {"headlines", "headlines_zh", "day_sigma", "performance"} <= summary.keys()
