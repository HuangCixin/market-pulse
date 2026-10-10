# Market Pulse

A daily report on global markets (gold, silver, oil, copper, US stocks, Chinese stocks,
currencies, US 10-year yield, VIX) and how they relate to each other.

## Setup (once)
```bash
cd market-pulse
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_daily.py --demo --open    # test run with fake data
```

## Every day
```bash
python run_daily.py --open
```
Best time from Paris: after 22:30 (US close). Chinese markets will already have closed that day.

Or open the folder in Claude Code (`claude` in this directory) and ask:
> Run today's market report and explain what happened.

## What's in the report
1. **Headlines** — unusual moves (measured in σ against each asset's own recent volatility)
   and relationships that changed.
2. **Performance** — last price, 1D / 1W / 1M / 3M / YTD, colored by size.
3. **Correlation heatmaps** — 60-day and 250-day, grouped by asset class.
4. **Biggest changes in relationships** — where the recent 60-day correlation departs from the 250-day norm.
5. **US → China spillover** — does yesterday's Wall Street move show up in today's China market?
6. **Rolling correlations** for key pairs (gold vs dollar, oil vs S&P 500, CSI 300 vs USD/CNY, …).

## Customize
Edit `config.yaml`: add any Yahoo Finance ticker (e.g. `BTC-USD`, `^N225`, `^STOXX50E`, `NG=F`),
change the correlation windows, or choose different key pairs.

## Run automatically every day
macOS/Linux, `crontab -e` (weekdays 23:00):
```
0 23 * * 1-5 cd /path/to/market-pulse && .venv/bin/python run_daily.py >> logs.txt 2>&1
```
Windows: Task Scheduler → run `.venv\Scripts\python.exe run_daily.py` in this folder.

## Notes
Data comes from Yahoo Finance via `yfinance`: free, delayed, unofficial, and sometimes a ticker
fails for a day (the report skips it and tells you). For research only, not investment advice.
