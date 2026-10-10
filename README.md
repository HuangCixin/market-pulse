# Market Pulse

A daily, interactive page showing how 21 global markets moved and how money shifted between them:
commodities (gold, silver, oil, copper), US stocks, Chinese stocks, currencies, US 10-year yield and VIX,
and crypto (Bitcoin, Ethereum, Solana). One self-contained HTML file, no internet needed to view it.

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

## What's on the page
1. **Market float (3D)**: every market is a sphere. Up today = floats above the surface, down = sinks
   below; height is how unusual the move was (σ). Markets that usually move together sit close, and lines
   join strongly linked pairs. Drag to rotate, scroll to zoom, hover for details, and press **Play**
   to watch the last two months.
2. **Where the money moved**: one card per market group, with bars showing who gained and who lost.
3. **Trends**: line charts per group (1M / 3M / 6M / 1Y).
4. **How markets move together**: relationships that changed, US → China next-day spillover,
   rolling correlations for key pairs, and the full correlation grid (collapsed by default).
5. **All markets**: performance table.

Switch **Period** (day / week / month), **Colors** (green = up, or red = up 红涨) and **Theme** at the top.

## Customize
Edit `config.yaml`: add any Yahoo Finance ticker (e.g. `^N225`, `^STOXX50E`, `NG=F`, `XRP-USD`),
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
