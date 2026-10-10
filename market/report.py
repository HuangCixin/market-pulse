"""Render the analysis as a self-contained HTML report + machine-readable summaries."""
from __future__ import annotations

import base64
import io
import json
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

GROUP_ORDER = ["Commodities", "US Stocks", "China Stocks", "FX", "Rates", "Volatility", "Crypto", "Other"]
INK, MUTED, GRID = "#1f2328", "#6e7781", "#e6e8eb"
SERIES = ["#2f6fdf", "#d9642b", "#1f9e76", "#b5418f", "#8a6d1f", "#5b5fc7"]


# ---------- helpers ----------
def _ordered(names, groups):
    return sorted(names, key=lambda n: (GROUP_ORDER.index(groups.get(n, "Other"))
                                        if groups.get(n, "Other") in GROUP_ORDER else 99, n))


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=144, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _fmt(v, d=2, signed=False, suffix=""):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    return f"{v:+,.{d}f}{suffix}" if signed else f"{v:,.{d}f}{suffix}"


def _cell_color(v, scale):
    """Diverging background: green up, red down, intensity by |v|/scale."""
    if v is None or np.isnan(v):
        return ""
    a = min(abs(v) / scale, 1) * 0.55
    rgb = "31,158,118" if v > 0 else "214,69,65"
    return f"background:rgba({rgb},{a:.2f})"


# ---------- charts ----------
def chart_rebased(prices, groups, kinds, days=92):
    present = [g for g in GROUP_ORDER if any(groups.get(c) == g for c in prices.columns)]
    fig, axes = plt.subplots(1, len(present), figsize=(3.3 * len(present), 2.8), squeeze=False)
    cutoff = prices.index[-1] - pd.Timedelta(days=days)
    for ax, g in zip(axes[0], present):
        cols = [c for c in prices.columns if groups.get(c) == g]
        for i, c in enumerate(cols):
            s = prices[c].dropna()
            s = s[s.index >= cutoff]
            if len(s) < 2:
                continue
            y = (s - s.iloc[0]) * 100 if kinds.get(c) == "yield" else (s / s.iloc[0] - 1) * 100
            ax.plot(y.index, y.values, lw=1.4, color=SERIES[i % len(SERIES)], label=c)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_title(g + (" (bp)" if g == "Rates" else " (%)"), fontsize=9, color=INK, loc="left")
        _style(ax)
        ax.tick_params(axis="x", rotation=0)
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator())
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
        ax.legend(fontsize=7, frameon=False, loc="best")
    fig.tight_layout()
    return _png(fig)


def chart_heatmap(corr, groups, title):
    names = _ordered(list(corr.columns), groups)
    m = corr.loc[names, names].values.astype(float)
    n = len(names)
    fig, ax = plt.subplots(figsize=(0.48 * n + 2.5, 0.42 * n + 1.5))
    im = ax.imshow(m, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(n), names, rotation=60, ha="right", fontsize=8, color=INK)
    ax.set_yticks(range(n), names, fontsize=8, color=INK)
    for i in range(n):
        for j in range(n):
            if i != j and not np.isnan(m[i, j]):
                ax.text(j, i, f"{m[i, j]:.1f}".replace("0.", ".").replace("-.", "−."),
                        ha="center", va="center", fontsize=6.5,
                        color="white" if abs(m[i, j]) > 0.6 else INK)
    # group separators
    gs = [groups.get(x) for x in names]
    for k in range(1, n):
        if gs[k] != gs[k - 1]:
            ax.axhline(k - 0.5, color="white", lw=2)
            ax.axvline(k - 0.5, color="white", lw=2)
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.ax.tick_params(labelsize=7, colors=MUTED)
    cb.outline.set_visible(False)
    return _png(fig)


def chart_rolling(rolling, window):
    if not rolling:
        return None
    n = len(rolling)
    cols = 3
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(11, 2.5 * rows), squeeze=False, sharey=True)
    for ax, (name, s) in zip(axes.flat, rolling.items()):
        s = s.dropna()
        ax.fill_between(s.index, 0, s.values, where=s.values >= 0, color="#2f6fdf", alpha=0.25, lw=0)
        ax.fill_between(s.index, 0, s.values, where=s.values < 0, color="#d64541", alpha=0.25, lw=0)
        ax.plot(s.index, s.values, color=INK, lw=1)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_ylim(-1, 1)
        last = s.iloc[-1] if len(s) else np.nan
        ax.set_title(f"{name}   now {last:+.2f}", fontsize=9, color=INK, loc="left")
        _style(ax)
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(interval=4))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    fig.suptitle(f"Rolling {window}-day correlation of daily moves", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    return _png(fig)


# ---------- text ----------
def headlines(res) -> list[str]:
    perf = res["performance"]
    lines = []
    big = perf.dropna(subset=["z_1D"]).reindex(perf["z_1D"].abs().sort_values(ascending=False).index)
    for name, r in big.head(3).iterrows():
        if abs(r["z_1D"]) < 1.5:
            break
        unit = "bp" if res["kinds"].get(name) == "yield" else "%"
        lines.append(f"{name} moved {_fmt(r['1D'], 1 if unit=='bp' else 2, True, unit)} on the day, "
                     f"a {abs(r['z_1D']):.1f}σ move versus its last 60 days.")
    if not lines:
        lines.append("No asset moved more than 1.5σ today; a quiet session across the board.")
    sh = res["shifts"]
    for _, r in sh.head(3).iterrows():
        if abs(r["change"]) < 0.3:
            break
        if np.sign(r["short"]) != np.sign(r["long"]) and min(abs(r["short"]), abs(r["long"])) > 0.1:
            verdict = "the relationship has flipped direction"
        elif abs(r["short"]) > abs(r["long"]):
            verdict = "they are moving together more tightly than usual"
        else:
            verdict = "the usual link has weakened"
        lines.append(f"{r['pair']}: {res['w_short']}-day correlation {r['short']:+.2f} vs "
                     f"{r['long']:+.2f} over {res['w_long']} days; {verdict}.")
    ll = res["leadlag"]
    if ll.notna().any().any():
        stacked = ll.stack()
        u, c = stacked.abs().idxmax()
        lines.append(f"Strongest US→China spillover: yesterday's {u} vs today's {c}, "
                     f"correlation {ll.loc[u, c]:+.2f} ({res['w_short']} days).")
    return lines


def _table(df, cols, fmt, color_scale=None, index_name="Asset", groups=None):
    head = "".join(f"<th>{escape(c)}</th>" for c in [index_name] + cols)
    body, current = [], None
    for idx, r in df.iterrows():
        if groups is not None and groups.get(idx) != current:
            current = groups.get(idx)
            body.append(f'<tr class="grp"><td colspan="{len(cols)+1}">{escape(str(current))}</td></tr>')
        tds = [f"<td class='name'>{escape(str(idx))}</td>"]
        for c in cols:
            v = r[c]
            style = _cell_color(v, color_scale[c]) if color_scale and c in color_scale else ""
            tds.append(f"<td style='{style}'>{fmt[c](v, idx) if c in fmt else escape(str(v))}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


CSS = """
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;color:#1f2328;
     background:#fff;max-width:1180px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:24px;margin:0}h2{font-size:17px;margin:34px 0 8px;border-bottom:1px solid #e6e8eb;padding-bottom:6px}
.sub{color:#6e7781;margin:4px 0 18px}.note{color:#6e7781;font-size:12.5px;margin:6px 0}
ul.hl{background:#f6f8fa;border-radius:8px;padding:14px 14px 14px 34px;margin:0}ul.hl li{margin:3px 0}
table{border-collapse:collapse;font-size:12.5px;width:100%;font-variant-numeric:tabular-nums}
th{text-align:right;color:#6e7781;font-weight:600;padding:6px 8px;border-bottom:1px solid #d0d7de}
th:first-child,td.name{text-align:left}td{text-align:right;padding:4px 8px;border-bottom:1px solid #f0f2f4}
tr.grp td{text-align:left;font-weight:600;background:#fafbfc;color:#57606a;padding-top:8px}
img{max-width:100%;display:block;margin:6px 0}.wrap{overflow-x:auto}
.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:800px){.two{grid-template-columns:1fr}}
"""


def write_report(res: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups, kinds = res["groups"], res["kinds"]
    perf = res["performance"].loc[_ordered(list(res["performance"].index), groups)]

    def pct(v, name):
        u = "bp" if kinds.get(name) == "yield" else "%"
        return _fmt(v, 0 if u == "bp" else 2, True, u)

    perf_cols = ["last", "1D", "1W", "1M", "3M", "YTD", "z_1D", "date"]
    fmt = {c: pct for c in ["1D", "1W", "1M", "3M", "YTD"]}
    fmt["last"] = lambda v, n: _fmt(v, 4 if v < 20 else 2)
    fmt["z_1D"] = lambda v, n: _fmt(v, 1, True, "σ")
    fmt["date"] = lambda v, n: escape(str(v))
    scale = {"1D": 2, "1W": 4, "1M": 8, "3M": 12, "YTD": 20, "z_1D": 3}
    perf_html = _table(perf.rename(columns={}), perf_cols, fmt, scale, groups=groups)
    perf_html = perf_html.replace("<th>z_1D</th>", "<th title='1-day move ÷ 60-day volatility'>1D σ</th>")
    perf_html = perf_html.replace("<th>last</th>", "<th>Last</th>").replace("<th>date</th>", "<th>As of</th>")

    sh = res["shifts"].set_index("pair") if not res["shifts"].empty else pd.DataFrame()
    sh_html = "<p class='note'>Not enough data.</p>"
    if not sh.empty:
        f2 = {c: (lambda v, n: _fmt(v, 2, True)) for c in ["short", "long", "change"]}
        sh_html = _table(sh, ["short", "long", "change"], f2, {"change": 0.8}, index_name="Pair")
        sh_html = sh_html.replace("<th>short</th>", f"<th>{res['w_short']}d</th>").replace(
            "<th>long</th>", f"<th>{res['w_long']}d</th>").replace("<th>change</th>", "<th>Change</th>")

    ll = res["leadlag"]
    ll_html = "<p class='note'>Not enough data.</p>"
    if not ll.empty:
        f3 = {c: (lambda v, n: _fmt(v, 2, True)) for c in ll.columns}
        ll_html = _table(ll, list(ll.columns), f3, {c: 0.8 for c in ll.columns},
                         index_name="US (day t−1) → China (day t)")

    rolling_img = chart_rolling(res["rolling"], res["w_roll"])
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Market Pulse {res['as_of']}</title>
<style>{CSS}</style></head><body>
<h1>Market Pulse</h1><p class="sub">Global markets as of {res['as_of']} · {len(perf)} assets ·
correlations use daily log returns (yields: daily change)</p>
<ul class="hl">{''.join(f'<li>{escape(h)}</li>' for h in headlines(res))}</ul>

<h2>Performance</h2><div class="wrap">{perf_html}</div>
<p class="note">Yields are shown in basis points. "1D σ" = today's move divided by its 60-day daily volatility;
beyond ±2σ is unusual.</p>
<img src="{chart_rebased(res['prices'], groups, kinds)}" alt="3-month performance by group">

<h2>Relationships between assets</h2>
<div class="two">
<img src="{chart_heatmap(res['corr_short'], groups, f"Last {res['w_short']} trading days")}" alt="short-window correlation">
<img src="{chart_heatmap(res['corr_long'], groups, f"Last {res['w_long']} trading days")}" alt="long-window correlation">
</div>
<p class="note">+1 = move together, −1 = move opposite, 0 = unrelated. Same-day correlations between US and
Chinese markets look weak because Asia closes before New York opens; see the lead/lag table below.</p>

<h2>Biggest changes in relationships</h2>
<p class="note">Pairs whose recent correlation differs most from their longer-run norm. Regime shifts show up here first.</p>
<div class="wrap">{sh_html}</div>

<h2>US → China spillover (next-day)</h2>
<p class="note">Correlation between the US move on one day and the Chinese move on the following trading day.</p>
<div class="wrap">{ll_html}</div>

{f'<h2>Key pairs over time</h2><img src="{rolling_img}" alt="rolling correlations">' if rolling_img else ''}
<p class="note" style="margin-top:30px">Data: Yahoo Finance via yfinance (delayed, unofficial). For research only, not investment advice.</p>
</body></html>"""
    path = out_dir / "report.html"
    path.write_text(html, encoding="utf-8")

    # Machine-readable outputs (handy for Claude Code or further analysis)
    summary = {
        "as_of": res["as_of"],
        "headlines": headlines(res),
        "performance": json.loads(perf.drop(columns=["date"]).round(4).to_json(orient="index")),
        "correlation_shifts": res["shifts"].round(3).to_dict(orient="records"),
        "us_to_china_leadlag": json.loads(ll.round(3).to_json(orient="index")),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    res["corr_short"].round(3).to_csv(out_dir / f"corr_{res['w_short']}d.csv")
    res["corr_long"].round(3).to_csv(out_dir / f"corr_{res['w_long']}d.csv")
    perf.round(4).to_csv(out_dir / "performance.csv")
    return path
