# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-11

### Added
- **Daily update**: the GitHub Pages site is rebuilt with real market data every weekday after the US close.
  `index.html` shows real data, `demo.html` the synthetic demo, and `summary.json` is published alongside.
- A "Synthetic demo data / 模拟演示数据" badge on pages built with `--demo`.

### Changed
- **Terrain layout by asset class**: markets now sit in fixed, colored zones (metals, FX, China stocks, energy,
  US stocks & Treasuries, crypto) instead of a correlation-based layout. Each zone has a colored ring, colored
  dots and a legend entry. Zones are configurable under `zones:` in `config.yaml`.
- Terrain labels are one line (name + σ); the % move is in the tooltip.

## [1.0.0] - 2026-10-10

### Added
- **Market terrain**: a filled, shaded 3D surface where height and color show each market's move in σ,
  with a labeled diverging color bar, date slider, and playback.
- **Where the money moved**: per-group diverging bars synced to the terrain's date and period.
- **Trends**: line charts per group for 1M / 3M / 6M / 1Y.
- **How markets move together**: relationship changes (60d vs 250d), US → China next-day spillover,
  rolling correlations for key pairs, and a collapsible correlation grid.
- **English / 中文** language switch covering every label, table, tooltip and headline.
- Color conventions: green = up, or red = up (红涨绿跌). Light and dark themes.
- Crypto (Bitcoin, Ethereum, Solana) with weekday sampling for correlations.
- `summary.json` with bilingual headlines for scripts and Claude Code.
- `--demo` mode with synthetic data, test suite, CI, and a live demo on GitHub Pages.
