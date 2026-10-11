# Methodology

**English** · [中文](METHODOLOGY.zh-CN.md)

This document explains every number on the Market Pulse page and the choices behind them.

## 1. Daily moves

Each market keeps its own trading calendar. Moves are computed only between consecutive days on which
that market actually traded.

| Market type | Daily move | Shown as |
|---|---|---|
| Prices (indices, commodities, FX, crypto, VIX) | log return `ln(Pₜ / Pₜ₋₁)` | percent, `(e^r − 1) × 100` |
| Yields (`kind: yield`, e.g. US 10Y) | change in percentage points `Yₜ − Yₜ₋₁` | basis points (× 100) |

Yields are not prices: a move from 4.00% to 4.10% is a change of 10 basis points, not a 2.5% return.

**Holidays are never forward-filled.** Filling a closed day with the previous price would create a fake
0% move, which drags volatility and correlations toward zero.

## 2. σ: how unusual was the move?

A 1% move means very different things for the euro and for Solana. Every move on the page is therefore
also expressed in standard deviations (σ):

```
σ-move = move over the period / (daily volatility × √n)
```

- **daily volatility**: standard deviation of the market's previous 60 daily moves (at least 20),
  known *before* the day in question, so a big day does not dampen itself.
- **n**: number of that market's trading days in the period (1 for a day; about 5 for a week, or 7
  for crypto; about 21 for a month).

As a rule of thumb, ±1σ is ordinary, ±2σ is unusual, and beyond ±3σ is rare.

**Latest main trading day.** The page and headlines default to the most recent date on which at least
half of the markets traded, so a Saturday (when only crypto trades) is not shown as "today".

## 3. Correlations

Correlation is computed on daily moves, never on price levels. Two trending prices look correlated even
when their daily moves are unrelated.

- **Weekday sampling.** For correlations, every market, crypto included, is sampled on Monday to Friday
  before moves are computed. Crypto's Monday move then spans Friday → Monday, like a stock's.
- **Pairwise complete observations.** Each pair uses the days on which both markets traded.
- **Windows:** 60 trading days ("recent") and 250 trading days ("normal", about a year). Configurable
  in `config.yaml`.
- **Relationships that changed** lists the pairs with the largest gap between the 60-day and 250-day
  correlation. "Flipped direction" means the sign changed and both values are beyond ±0.1.

## 4. US → China next-day spillover

Shanghai and Shenzhen close at 15:00 Beijing time and Hong Kong at 16:00, all before New York opens.
A US move on day *t* can therefore only show up in China on day *t + 1*. Same-day correlation understates
this link, so the table correlates the US move on the previous US trading day with the Chinese move on
each Chinese trading day, over the last 60 days.

## 5. The 3D layout

Markets are placed in fixed **zones by asset class**, defined under `zones:` in `config.yaml`:
metals, FX, China stocks, energy, US stocks & Treasuries, and crypto. Each zone has its own color,
used for its ring on the terrain, its market dots and its legend entry.

- Zones fill a grid of three per row, left to right, in the order listed in the config.
- Inside a zone, markets sit on a small circle around the zone centre.
- A market that is not listed in any zone gets a zone named after its `group`.

The layout is the same every day, so a market is always found in the same place. How markets relate
to each other is shown by the relationship lines (Links), the correlation charts and the US → China table.

## 6. The terrain surface

Height and color both encode the σ-move (clamped to ±4σ for height and ±3σ for color).

The surface is drawn on a 56 × 56 grid. Each grid point's height is a weighted blend of the markets' σ:

```
h(p) = Σ wᵢ σᵢ / (Σ wᵢ + K₀)        wᵢ = exp(−dᵢ² / 2s²) / (dᵢ² + ε)
```

- The `1 / (dᵢ² + ε)` factor makes the surface pass almost exactly through each market's value.
- `K₀` pulls areas far from any market back toward zero ("sea level").
- The rim fades to zero, so the terrain reads as one solid piece.

**Only the dots are data.** The surface between them is a visual aid. A valley between two rising
markets means only that no market sits there.

The color scale diverges around zero: light neutral near 0, teal for up, and orange-red for down.
In red-up mode (the Chinese convention) the two sides swap. Faces are lit with simple Lambert
shading so slopes stay readable.

## 7. "Where the money moved" and the regime

These are **price-based reads**, not fund-flow data.

- **Group average:** the mean σ-move of the open markets in the group. Above +0.5σ is labeled
  "inflow", below −0.5σ "outflow", otherwise "flat".
- **Regime score** for the latest main trading day:

  ```
  score = (2 × mean σ(stocks) + mean σ(crypto)) / 3 − mean σ(havens)
  havens = gold, VIX, and the yen (USD/JPY with its sign flipped)
  ```

  Above +0.5 reads as risk-on, below −0.5 as risk-off, otherwise mixed.

## 8. Known limitations

- Yahoo Finance data is delayed and unofficial. A ticker can fail for a day, and the report then skips it.
- Futures (gold, oil, copper) roll between contracts. With `auto_adjust` the effect is small but not zero.
- σ assumes recent volatility describes "normal". After a calm stretch, a moderate move can show a large σ.
- The layout shifts slowly as correlations evolve, so compare positions across months with care.
