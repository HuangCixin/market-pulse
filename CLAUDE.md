# Market Pulse — notes for Claude Code

Daily cross-asset market report: commodities (gold, oil, copper), US stocks, Chinese stocks,
FX (dollar index, EUR/USD, USD/CNY, USD/JPY), US 10Y yield, VIX. Produces performance tables
and the relationships (correlations) between all assets.

## Run
```bash
pip install -r requirements.txt
python run_daily.py          # download data + build today's report
python run_daily.py --demo   # offline, synthetic data (use for testing code changes)
python run_daily.py --cache  # rebuild from data/prices.csv, no download
```
Output goes to `reports/<date>/`: `report.html` (open in a browser), `summary.json`
(headlines, performance, correlation shifts, lead/lag), `performance.csv`, `corr_*.csv`.

## Layout
- `config.yaml` — the asset list (Yahoo Finance tickers), windows, key pairs. Add/remove assets here, not in code.
- `market/fetch.py` — yfinance download + cache in `data/prices.csv`; `demo_prices()` for offline tests.
- `market/analyze.py` — returns, performance, correlations, rolling correlations, US→China lead/lag.
- `market/report.py` — matplotlib charts (embedded as base64) + HTML, plus JSON/CSV outputs.
- `run_daily.py` — CLI entry point.

## Methodology rules (keep these when changing the analysis)
- Correlate **daily moves**, never price levels (levels give spurious correlation).
- Price assets use log returns; `kind: yield` assets use daily change in percentage points (shown as bp).
- Each market keeps its own calendar. Do NOT forward-fill holidays before computing returns:
  that creates fake zero-return days and biases correlations toward zero.
- US and China trade in different hours. Same-day US/China correlation is understated; the
  lead/lag table (US day t−1 vs China day t) is the right measure of spillover.
- USD/CNY up = yuan weaker. USD/JPY up = yen weaker. EUR/USD up = dollar weaker.

## When asked "what happened in the markets today?"
Run `python run_daily.py`, then read `reports/<latest>/summary.json` and explain it in plain
language: biggest movers (by σ, not just %), notable correlation shifts, and the US→China
spillover. Present data, not investment advice.

## Conventions
- Python 3.10+, pandas, matplotlib. No plotly/JS dependencies; the report must stay a single self-contained HTML file.
- Test any change with `python run_daily.py --demo` before running on live data.
