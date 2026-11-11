"""Sample exhibits for the chart kit (exhibit.chart, 0.3.0 phase 2), one per chart type.

They use the bake-off prompts' data, so eval/chart_check.py can check them like the agent's exhibits.
Writes into a store of its own (never ~/.exhibit):
    python -X utf8 eval/chart_samples.py <store_dir>
    set EXHIBIT_SOURCE=<store_dir> and run eval/chart_check.py <out_dir> <ids printed here>
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "plugin" / "exhibit" / "tools" / "exhibit_tool.py"
sys.path.insert(0, str(Path(__file__).parent))
from chart_check import EXPECTED, MONTHS  # noqa: E402

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg:#f6f5f1; --card:#fff; --fg:#1d1d1b; --muted:#6b6b66; --line:#e3e1da; --accent:#4f7cff; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#16171a; --card:#1f2125; --fg:#ececea; --muted:#a3a39e; --line:#34363b; --accent:#7c9cff; }}
}}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,sans-serif; }}
main {{ max-width:960px; margin:0 auto; padding:28px 20px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} p {{ color:var(--muted); margin:0 0 18px; }}
</style></head>
<body><main>
<h1>{title}</h1><p>{lead}</p>
<div class="card"><div id="chart"></div></div>
</main>
<script>
exhibit.chart("#chart", {spec});
</script>
</body></html>"""

SALES = EXPECTED["sales"]
BUDGET = EXPECTED["budget"]
SAMPLES = {
    "sales-line": ("Regional sales, line", "Monthly sales by region, $k.",
                   {"type": "line", "x": MONTHS, "series": SALES, "prefix": "$", "suffix": "k"}),
    "sales-area": ("Regional sales, stacked area", "Monthly sales by region, stacked.",
                   {"type": "area", "x": MONTHS, "series": SALES, "stack": True, "prefix": "$", "suffix": "k"}),
    "sales-bar": ("Regional sales, bars", "Monthly sales by region.",
                  {"type": "bar", "x": MONTHS, "series": SALES, "prefix": "$", "suffix": "k", "title": "Sales by month"}),
    "budget-pie": ("Budget, pie", "Annual budget by category.",
                   {"type": "pie", "data": BUDGET, "prefix": "$"}),
    "budget-donut": ("Budget, donut", "Annual budget by category.",
                     {"type": "donut", "data": BUDGET, "prefix": "$", "title": "Annual budget"}),
    "budget-hbar": ("Budget, horizontal bars", "Annual budget by category.",
                    {"type": "bar", "horizontal": True, "x": list(BUDGET), "series": {"Budget": list(BUDGET.values())},
                     "prefix": "$"}),
    "sales-scatter": ("North vs South", "Each month's North and South sales.",
                      {"type": "scatter", "series": {"Months": [[n, s] for n, s in zip(SALES["North"], SALES["South"])]},
                       "xLabel": "North", "yLabel": "South"}),
    "budget-linked": ("Budget with a linked total", "The total follows edits to the chart's data (onChange).", None),
    "sales-daily": ("Daily sales (zoom)", "A year of daily figures: the kit adds zooming past 24 points.",
                    {"type": "line", "x": [f"Day {i + 1}" for i in range(365)],
                     "series": {"Sales": [round(50 + 20 * ((i * 37) % 17) / 17 + i / 10, 1) for i in range(365)]}}),
}


# A page that keeps a total in step with the chart's Edit data table, through onChange.
LINKED = PAGE.replace('<div class="card"><div id="chart"></div></div>',
                      '<p>Total: <b id="total"></b></p><div class="card"><div id="chart"></div></div>').replace(
    'exhibit.chart("#chart", {spec});',
    'const show = (d) => {{ document.querySelector("#total").textContent = "$" + Object.values(d).reduce((a, b) => a + (b || 0), 0).toLocaleString(); }};\n'
    'show({budget});\n'
    'exhibit.chart("#chart", {{type: "pie", data: {budget}, prefix: "$", onChange: show}});')


def main(store: Path) -> None:
    os.environ["EXHIBIT_HOME"] = str(store)
    os.environ["EXHIBIT_NO_BROWSER"] = "1"
    spec = importlib.util.spec_from_file_location("exhibit_tool", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    ids = []
    for name, (title, lead, chart) in SAMPLES.items():
        if name == "budget-linked":
            html = LINKED.format(title=title, lead=lead, budget=json.dumps(BUDGET))
        else:
            html = PAGE.format(title=title, lead=lead, spec=json.dumps(chart))
        result = tool._run({"action": "show", "title": title, "html": html})
        exhibit_id = result.get("exhibit_id")
        if not exhibit_id:
            raise SystemExit(f"{name}: {result}")
        # chart_check picks the data to compare by "sales"/"budget" in the id
        target = store / "exhibits" / name
        (store / "exhibits" / exhibit_id).rename(target)
        meta = json.loads((target / "meta.json").read_text(encoding="utf-8"))
        meta["id"] = name
        (target / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        ids.append(name)
    tool._stop_server()
    print(" ".join(ids))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
