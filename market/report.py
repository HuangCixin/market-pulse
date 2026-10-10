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


def headlines(res: dict) -> list[str]:
    """Plain-language bullets for the latest day."""
    kinds = {a["name"]: a["kind"] for a in res["assets"]}
    groups = {a["name"]: a["group"] for a in res["assets"]}
    day = res["float"]["periods"]["day"]
    week = res["float"]["periods"]["week"]
    k = res["float"]["main_idx"]
    lines = []

    r = res["regime"]["day"]
    lines.append(f"{res['as_of']} reads <b>{r['label'].lower()}</b> (score {r['score']:+.2f}: "
                 "stocks and crypto versus gold, VIX and the yen).")

    movers = [(n, day[n]["z"][k], day[n]["v"][k]) for n in day if day[n]["z"][k] is not None]
    movers.sort(key=lambda t: -abs(t[1]))
    big = [m for m in movers if abs(m[1]) >= 1.5][:3]
    if big:
        lines.append("Unusual moves: " + "; ".join(
            f"<b>{n}</b> {_fmt(v, kinds[n])} ({z:+.1f}σ)" for n, z, v in big) + ".")
    else:
        lines.append("No market moved more than 1.5σ; a quiet session.")

    # strongest and weakest group over the week
    avg = {}
    for n, s in week.items():
        if s["z"][k] is not None:
            avg.setdefault(groups[n], []).append(s["z"][k])
    if len(avg) >= 2:
        g = sorted(((k, sum(v) / len(v)) for k, v in avg.items()), key=lambda t: t[1])
        lines.append(f"This week, money leaned toward <b>{g[-1][0]}</b> ({g[-1][1]:+.1f}σ) "
                     f"and away from <b>{g[0][0]}</b> ({g[0][1]:+.1f}σ).")

    if res["shifts"]:
        s = res["shifts"][0]
        if abs(s["change"]) >= 0.3:
            lines.append(f"Biggest relationship change: <b>{s['a']}</b> & <b>{s['b']}</b>, correlation "
                         f"{s['long']:+.2f} → {s['short']:+.2f} ({res['corr']['w_long']}d → {res['corr']['w_short']}d).")
    return lines


def write_report(res: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    res["headlines"] = headlines(res)
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
