"""Write the interactive HTML page plus machine-readable summaries.

The page is market/template.html with the analysis embedded as JSON.
It has no external dependencies, so it works offline and can be emailed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("template.html")


def _fmt(v: float | None, kind: str) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.0f}bp" if kind == "yield" else f"{v:+.2f}%"


GROUP_ZH = {"Commodities": "大宗商品", "US Stocks": "美股", "China Stocks": "中国股市",
            "FX": "外汇", "Rates & Vol": "利率与波动率", "Crypto": "加密货币"}
REGIME_ZH = {"Risk-on": "风险偏好上升", "Risk-off": "避险", "Mixed": "分化"}


def headlines(res: dict, lang: str = "en") -> list[str]:
    """Plain-language bullets for the latest main trading day, in English or Chinese."""
    zh = lang == "zh"
    kinds = {a["name"]: a["kind"] for a in res["assets"]}
    groups = {a["name"]: a["group"] for a in res["assets"]}
    nm = {a["name"]: (a.get("name_zh") or a["name"]) if zh else a["name"] for a in res["assets"]}
    gn = (lambda g: GROUP_ZH.get(g, g)) if zh else (lambda g: g)
    day = res["float"]["periods"]["day"]
    week = res["float"]["periods"]["week"]
    k = res["float"]["main_idx"]
    lines = []

    r = res["regime"]["day"]
    if zh:
        lines.append(f"{res['as_of']} 市场整体：<b>{REGIME_ZH.get(r['label'], r['label'])}</b>"
                     f"（得分 {r['score']:+.2f}：股票和加密货币 对比 黄金、VIX 和日元）。")
    else:
        lines.append(f"{res['as_of']} reads <b>{r['label'].lower()}</b> (score {r['score']:+.2f}: "
                     "stocks and crypto versus gold, VIX and the yen).")

    movers = [(n, day[n]["z"][k], day[n]["v"][k]) for n in day if day[n]["z"][k] is not None]
    movers.sort(key=lambda t: -abs(t[1]))
    big = [m for m in movers if abs(m[1]) >= 1.5][:3]
    if big:
        items = [f"<b>{nm[n]}</b> {_fmt(v, kinds[n])} ({z:+.1f}σ)" for n, z, v in big]
        lines.append(("异常波动：" + "；".join(items) + "。") if zh else ("Unusual moves: " + "; ".join(items) + "."))
    else:
        lines.append("没有市场波动超过 1.5σ，行情平静。" if zh else "No market moved more than 1.5σ; a quiet session.")

    # strongest and weakest group over the week
    avg = {}
    for n, s in week.items():
        if s["z"][k] is not None:
            avg.setdefault(groups[n], []).append(s["z"][k])
    if len(avg) >= 2:
        g = sorted(((grp, sum(v) / len(v)) for grp, v in avg.items()), key=lambda t: t[1])
        if zh:
            lines.append(f"本周资金偏向 <b>{gn(g[-1][0])}</b>（{g[-1][1]:+.1f}σ），"
                         f"流出 <b>{gn(g[0][0])}</b>（{g[0][1]:+.1f}σ）。")
        else:
            lines.append(f"This week, money leaned toward <b>{g[-1][0]}</b> ({g[-1][1]:+.1f}σ) "
                         f"and away from <b>{g[0][0]}</b> ({g[0][1]:+.1f}σ).")

    if res["shifts"]:
        s = res["shifts"][0]
        if abs(s["change"]) >= 0.3:
            ws, wl = res["corr"]["w_short"], res["corr"]["w_long"]
            if zh:
                lines.append(f"关系变化最大：<b>{nm[s['a']]}</b> 与 <b>{nm[s['b']]}</b>，相关系数 "
                             f"{s['long']:+.2f} → {s['short']:+.2f}（{wl}天 → {ws}天）。")
            else:
                lines.append(f"Biggest relationship change: <b>{s['a']}</b> & <b>{s['b']}</b>, correlation "
                             f"{s['long']:+.2f} → {s['short']:+.2f} ({wl}d → {ws}d).")
    return lines


def write_report(res: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    res["headlines"] = headlines(res)
    res["headlines_zh"] = headlines(res, "zh")
    payload = json.dumps(res, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload, 1)
    page = out_dir / "report.html"
    page.write_text(html, encoding="utf-8")

    # summary.json: compact, for Claude Code or other scripts
    day = res["float"]["periods"]["day"]
    summary = {
        "as_of": res["as_of"],
        "regime": res["regime"],
        "headlines": [h.replace("<b>", "").replace("</b>", "") for h in res["headlines"]],
        "headlines_zh": [h.replace("<b>", "").replace("</b>", "") for h in res["headlines_zh"]],
        "day_sigma": {n: day[n]["z"][res["float"]["main_idx"]] for n in day},
        "performance": res["performance"],
        "correlation_shifts": res["shifts"],
        "us_to_china_leadlag": res["leadlag"],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(out_dir / "performance.csv", "w", newline="", encoding="utf-8") as f:
        cols = ["last", "1D", "1W", "1M", "3M", "YTD", "1Y", "date"]
        w = csv.writer(f)
        w.writerow(["asset", "group"] + cols)
        for a in res["assets"]:
            p = res["performance"].get(a["name"])
            if p:
                w.writerow([a["name"], a["group"]] + [p.get(c) for c in cols])
    return page
