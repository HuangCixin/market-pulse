#!/usr/bin/env python3
"""Market Pulse: daily cross-asset market report.

Usage:
    python run_daily.py            # download latest data, build today's report
    python run_daily.py --demo     # offline test with synthetic data
    python run_daily.py --cache    # rebuild from data/prices.csv without downloading
    python run_daily.py --open     # open the report in your browser when done
"""
from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

import yaml

from market.analyze import run_analysis
from market.fetch import demo_prices, fetch_prices, load_cache
from market.report import write_report

ROOT = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="use synthetic data (no internet needed)")
    ap.add_argument("--cache", action="store_true", help="use cached prices, skip download")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--open", action="store_true", help="open the report when finished")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    assets = cfg["assets"]

    if args.demo:
        prices = demo_prices(assets)
        print("Using synthetic demo data.")
    elif args.cache:
        prices = load_cache()
    else:
        print(f"Downloading {len(assets)} assets...")
        prices = fetch_prices(assets, cfg.get("lookback_days", 750))

    res = run_analysis(prices, cfg)
    res["demo"] = bool(args.demo)
    out_dir = ROOT / "reports" / (res["as_of"] + ("-demo" if args.demo else ""))
    path = write_report(res, out_dir)

    print(f"\nMarket Pulse — {res['as_of']}")
    for h in res["headlines"]:
        print("  • " + h.replace("<b>", "").replace("</b>", ""))
    print(f"\nReport: {path}")
    if args.open:
        webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
