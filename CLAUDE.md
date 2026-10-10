# Market Pulse — notes for Claude Code

Daily cross-market report on 21 markets in 6 groups: Commodities (gold, silver, WTI, Brent, copper),
US Stocks, China Stocks (Shanghai, CSI 300, Shenzhen, Hang Seng), FX (dollar index, EUR/USD,
USD/CNY, USD/JPY), Rates & Vol (US 10Y yield, VIX), Crypto (Bitcoin, Ethereum, Solana).
Output is one interactive, self-contained HTML page per day (no external JS/CSS, works offline).

## Run
```bash
pip install -r requirements.txt
python run_daily.py --open   # download data + build today's page
python run_daily.py --demo   # offline, synthetic data (use this to test code changes)
python run_daily.py --cache  # rebuild from data/prices.csv, no download
```
Output: `reports/<date>/report.html`, `summary.json` (headlines, regime, σ moves,
performance, correlation shifts, US→China lead/lag), `performance.csv`.

## Layout
- `config.yaml` — markets (Yahoo Finance tickers), groups, windows, key pairs. Add/remove markets here, not in code.
- `market/fetch.py` — yfinance download + CSV cache; `demo_prices()` builds synthetic data.
- `market/analyze.py` — all numbers: moves, σ, 3D layout (MDS), correlations, regime. Returns a JSON-able dict.
- `market/report.py` — headlines, embeds the dict into the template, writes summary files.
- `market/template.html` — the page: vanilla JS + canvas/SVG. Data arrives as `const D = {...}`.
- `run_daily.py` — CLI.

## Page sections (template.html)
1. **Market float (3D canvas)**: x/y = MDS of the long-window correlation (markets that move
   together sit close); height = move in σ; above the surface = up. Links = |corr| ≥ 0.6
   (solid = together, dashed = opposite). Drag/zoom/hover, date slider + Play.
2. **Where the money moved**: diverging σ bars per group, synced to the float's date/period.
3. **Trends**: line small multiples per group (1M/3M/6M/1Y). Yields are plotted separately in bp.
4. **How markets move together**: relationship changes, US→China next-day table, rolling correlations,
   and a collapsed correlation grid (the user prefers not to lead with heatmaps).
5. **All markets** table.
Controls: Period (day/week/month), Colors (green-up Western / red-up Chinese convention), Theme.

## Methodology rules (keep these when changing the analysis)
- Correlate **daily moves**, never price levels.
- Price assets: log returns. `kind: yield`: change in percentage points, shown in bp.
- σ = move ÷ (prior 60-day daily vol × √days in period). This makes gold, FX and crypto comparable.
- Each market keeps its own calendar; never forward-fill holidays before computing returns.
- Correlations sample every market on weekdays only, so crypto's Monday move covers Fri→Mon like stocks.
- US/China trade in different hours: use the lead/lag table (US day t → China day t+1), not same-day correlation.
- "Money moved" is a price-based read (risk-on/off), not actual fund-flow data. Say so when explaining.
- USD/CNY up = yuan weaker; USD/JPY up = yen weaker; EUR/USD up = dollar weaker.

## When asked "what happened in the markets today?"
Run `python run_daily.py`, read the latest `reports/*/summary.json`, and explain in plain language:
regime, biggest σ movers, which group gained/lost this week, notable relationship changes, US→China
spillover. Present data, not investment advice.

## Conventions
- Python 3.10+, pandas, numpy, yfinance, pyyaml. No plotting libraries; charts are drawn in template.html.
- The page must stay a single self-contained file (no CDN), readable in light and dark mode, and usable on a phone.
- Test changes with `python run_daily.py --demo --open` before running on live data.
