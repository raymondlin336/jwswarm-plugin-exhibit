"""Objective checks for chart exhibits (the 0.3.0 chart bake-off, see notes/chart-bakeoff.md).

For each exhibit it copies the exhibit into a temporary store, serves it through Exhibit's own server
(so the real sandbox and CSP apply), drives headless Microsoft Edge over the DevTools Protocol, and
reports:
- reliability: script errors on load, whether a chart is actually drawn;
- correctness: the chart's data, read from the library's own chart object, against the prompt's data;
- robustness: overflow at 400 px and 1400 px wide, text contrast in light and dark mode, chart kept in print;
- cost: page size, chart code lines, bytes downloaded from CDNs;
- interactivity: an inventory of what the chart has (tooltip, legend toggle, zoom, hover focus...).
Screenshots (light and dark) are saved next to the report.

Usage (AgentStudio's Python 3.11, which has websockets):
    python -X utf8 eval/chart_check.py <out_dir> <exhibit_id> [<exhibit_id> ...]
Real exhibits in ~/.exhibit are only read, never changed.
"""
from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "plugin" / "exhibit" / "tools" / "exhibit_tool.py"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
REAL_STORE = Path(os.environ.get("EXHIBIT_SOURCE") or (Path.home() / ".exhibit")) / "exhibits"

# The bake-off prompts' data.
EXPECTED = {
    "sales": {
        "North": [42, 45, 48, 51, 55, 60, 63, 61, 58, 62, 68, 74],
        "South": [38, 37, 41, 44, 43, 47, 52, 55, 53, 50, 54, 59],
        "East": [25, 29, 33, 31, 36, 40, 39, 44, 48, 51, 49, 55],
        "West": [50, 48, 46, 47, 45, 44, 46, 49, 52, 56, 60, 63],
    },
    "budget": {
        "Salaries": 412000, "Rent": 96000, "Software": 58000, "Marketing": 74000,
        "Travel": 31000, "Equipment": 27000, "Training": 18000, "Other": 12000,
    },
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Runs before the page's own scripts: keeps hold of Vega views and specs, which aren't global.
HOOK = r"""
(() => {
  let real;
  window.__vega = [];
  try {
    Object.defineProperty(window, "vegaEmbed", {
      configurable: true,
      set(f) { real = f; },
      get() {
        if (!real) return undefined;
        const wrapped = (...args) => real(...args).then((r) => { window.__vega.push({ spec: r.spec, view: r.view }); return r; });
        Object.assign(wrapped, real);
        return wrapped;
      },
    });
  } catch (e) {}
})();
"""

# Runs in the page after load: what library, which charts, their data and interaction settings.
PROBE = r"""
(() => {
  const out = { libs: {}, charts: [], drawn: [], title: document.title, h1: (document.querySelector("h1") || {}).textContent || "" };
  out.libs = { chartjs: typeof Chart !== "undefined", echarts: typeof echarts !== "undefined", vega: (window.__vega || []).length > 0 || typeof vegaEmbed !== "undefined" };
  // Drawn: visible canvases/SVGs of real size, and for canvases, enough non-empty pixels.
  for (const el of document.querySelectorAll("canvas, svg")) {
    const r = el.getBoundingClientRect();
    if (r.width * r.height < 20000) continue;
    let ink = null;
    if (el.tagName === "CANVAS") {
      try {
        const d = el.getContext("2d").getImageData(0, 0, el.width, el.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 16) if (d[i] > 0) n++;
        ink = n;
      } catch (e) { ink = -1; }
    } else { ink = el.querySelectorAll("path, rect, line, circle, text").length; }
    out.drawn.push({ tag: el.tagName, w: Math.round(r.width), h: Math.round(r.height), ink });
  }
  if (typeof Chart !== "undefined" && Chart.instances) {
    for (const c of Object.values(Chart.instances)) {
      const o = c.options || {}, p = o.plugins || {};
      out.charts.push({
        lib: "chart.js", type: c.config.type, labels: c.data.labels,
        series: c.data.datasets.map((d) => ({ name: d.label, data: d.data })),
        tooltip: !(p.tooltip && p.tooltip.enabled === false),
        legend: !(p.legend && p.legend.display === false),
        legendToggle: !(p.legend && p.legend.onClick && String(p.legend.onClick).length < 20),
        hoverMode: (o.interaction && o.interaction.mode) || (o.hover && o.hover.mode) || "nearest",
        zoom: !!(p.zoom),
        hoverOffset: (c.data.datasets[0] || {}).hoverOffset || null,
        // Only when the chart draws text itself (axes or its own legend); an HTML legend isn't chart text.
        textColor: (o.scales && o.scales.x && o.scales.x.display !== false && Object.keys(o.scales).length)
          ? ((o.scales.x.ticks && o.scales.x.ticks.color) || Chart.defaults.color)
          : (!(p.legend && p.legend.display === false) ? ((p.legend && p.legend.labels && p.legend.labels.color) || Chart.defaults.color) : null),
      });
    }
  }
  if (typeof echarts !== "undefined") {
    for (const el of document.querySelectorAll("[_echarts_instance_]")) {
      const inst = echarts.getInstanceByDom(el); if (!inst) continue;
      const o = inst.getOption() || {};
      const x = (o.xAxis || [])[0] || {};
      out.charts.push({
        lib: "echarts", type: (o.series || []).map((s) => s.type).join(","), labels: x.data || null,
        series: (o.series || []).map((s) => ({ name: s.name, data: s.data })),
        tooltip: !!(o.tooltip && o.tooltip.length && o.tooltip[0].show !== false),
        legend: !!(o.legend && o.legend.length && o.legend[0].show !== false),
        legendToggle: !!(o.legend && o.legend.length),
        hoverMode: (o.tooltip && o.tooltip[0] && o.tooltip[0].trigger) || null,
        zoom: !!(o.dataZoom && o.dataZoom.length),
        focus: (o.series || []).map((s) => s.emphasis && s.emphasis.focus).filter(Boolean),
        // ECharts' own defaults when nothing is set: axis labels #6E7079, legend and other text #333.
        textColor: (x.axisLabel && x.axisLabel.color) || (o.legend && o.legend[0] && o.legend[0].show !== false
          && o.legend[0].textStyle && o.legend[0].textStyle.color) || (o.textStyle && o.textStyle.color)
          || (o.xAxis && o.xAxis.length ? "#6E7079" : (o.legend && o.legend.length && o.legend[0].show !== false ? "#333333" : null)),
        background: typeof o.backgroundColor === "string" && o.backgroundColor !== "transparent" ? o.backgroundColor : null,
      });
    }
  }
  for (const v of window.__vega || []) {
    const s = v.spec || {};
    out.charts.push({ lib: "vega-lite", type: JSON.stringify(s.mark || (s.layer || []).map((l) => l.mark)), spec: s,
      params: JSON.stringify(s.params || (s.layer || []).map((l) => l.params) || null),
      tooltip: JSON.stringify(s).includes("tooltip"), legend: true, legendToggle: JSON.stringify(s).includes("\"bind\":\"legend\""),
      zoom: JSON.stringify(s).includes("\"bind\":\"scales\""),
      // Vega's defaults when the config sets nothing: black-ish labels on a transparent background.
      textColor: ((s.config || {}).axis || {}).labelColor || ((s.config || {}).legend || {}).labelColor || ((s.config || {}).text || {}).color || "#000000",
      background: typeof s.background === "string" && s.background !== "transparent" ? s.background : ((s.config || {}).background || null) });
  }
  const bg = getComputedStyle(document.body).backgroundColor, fg = getComputedStyle(document.body).color;
  out.colors = { bg, fg, h1: document.querySelector("h1") ? getComputedStyle(document.querySelector("h1")).color : null };
  out.overflow = document.documentElement.scrollWidth > window.innerWidth + 1;
  return JSON.stringify(out);
})()
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, method: str = "GET") -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, method=method), timeout=5) as r:
        return json.loads(r.read().decode())


class Cdp:
    def __init__(self, ws):
        self.ws, self.n, self.pending, self.events = ws, 0, {}, []

    async def pump(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.pending:
                self.pending.pop(msg["id"]).set_result(msg)
            else:
                self.events.append(msg)

    async def send(self, method: str, **params):
        self.n += 1
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.n] = fut
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        msg = await asyncio.wait_for(fut, 30)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get("result", {})


def _luminance(css: str | None) -> float | None:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", css or "")
    if not m:
        h = re.match(r"#([0-9a-f]{3}|[0-9a-f]{6})$", (css or "").strip(), re.I)
        if not h:
            return None
        hexes = h.group(1) if len(h.group(1)) == 6 else "".join(c * 2 for c in h.group(1))
        rgb = [int(hexes[i:i + 2], 16) for i in (0, 2, 4)]
    else:
        rgb = [int(x) for x in m.groups()]
    lin = [(c / 255 / 12.92) if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str | None, b: str | None) -> float | None:
    la, lb = _luminance(a), _luminance(b)
    if la is None or lb is None:
        return None
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _check_data(kind: str, charts: list[dict]) -> dict:
    """Compare the chart's data with the prompt's: how many expected values are present and unchanged."""
    expected = EXPECTED[kind]
    found = {}
    for c in charts:
        if c.get("lib") == "vega-lite":
            values = ((c.get("spec") or {}).get("data") or {}).get("values") or []
            for row in values if isinstance(values, list) else []:
                if not isinstance(row, dict):
                    continue
                strs = [v for v in row.values() if isinstance(v, str)]
                nums = [v for v in row.values() if isinstance(v, (int, float))]
                if kind == "budget" and strs and nums:
                    found[strs[0]] = nums[0]
                if kind == "sales" and nums:
                    region = next((s for s in strs if s in expected), None)
                    month = next((s for s in strs if s[:3] in MONTHS), None)
                    if region and month:
                        found.setdefault(region, {})[month[:3]] = nums[0]
            continue
        for s in c.get("series") or []:
            data = s.get("data") or []
            if kind == "sales":
                found[str(s.get("name"))] = [d.get("value") if isinstance(d, dict) else d for d in data]
            else:  # a pie: values per label
                labels = c.get("labels") or []
                for i, d in enumerate(data):
                    name = d.get("name") if isinstance(d, dict) else (labels[i] if i < len(labels) else None)
                    value = d.get("value") if isinstance(d, dict) else d
                    if name is not None:
                        found[str(name)] = value
    right = total = 0
    if kind == "sales":
        for region, values in expected.items():
            got = found.get(region)
            if isinstance(got, dict):
                got = [got.get(m) for m in MONTHS]
            for i, v in enumerate(values):
                total += 1
                right += bool(got and i < len(got) and got[i] is not None and float(got[i]) == v)
    else:
        for name, v in expected.items():
            total += 1
            got = found.get(name)
            right += got is not None and float(got) == v
    return {"right": right, "total": total}


def _script_lines(page: str) -> int:
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page, re.S | re.I)
    return sum(1 for b in blocks for line in b.splitlines() if line.strip())


async def _check(cdp: Cdp, url: str, out: Path, name: str, kind: str) -> dict:
    result: dict = {}
    for scheme in ("light", "dark"):
        cdp.events.clear()
        await cdp.send("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)
        await cdp.send("Emulation.setEmulatedMedia", media="", features=[{"name": "prefers-color-scheme", "value": scheme}])
        await cdp.send("Page.navigate", url=url)
        await asyncio.sleep(4)  # load, CDN scripts, chart animation
        probe = json.loads((await cdp.send("Runtime.evaluate", expression=PROBE, returnByValue=True))["result"]["value"])
        shot = await cdp.send("Page.captureScreenshot", format="png")
        (out / f"{name}-{scheme}.png").write_bytes(base64.b64decode(shot["data"]))
        errors = [e["params"]["exceptionDetails"].get("exception", {}).get("description", e["params"]["exceptionDetails"].get("text", ""))[:200]
                  for e in cdp.events if e.get("method") == "Runtime.exceptionThrown"]
        errors += [" ".join(str(a.get("value", a.get("description", ""))) for a in e["params"].get("args", []))[:200]
                   for e in cdp.events if e.get("method") == "Runtime.consoleAPICalled" and e["params"].get("type") == "error"]
        cdn = sum(e["params"].get("encodedDataLength", 0) for e in cdp.events if e.get("method") == "Network.loadingFinished")
        chart = probe["charts"][0] if probe["charts"] else {}
        text = chart.get("textColor")
        chart_bg = chart.get("background")
        bg = chart_bg if chart_bg and _luminance(chart_bg) is not None else probe["colors"]["bg"]
        result[scheme] = {
            "errors": errors,
            "drawn": probe["drawn"],
            "contrast_text": _contrast(text, bg) if text else None,
            "contrast_title": _contrast(probe["colors"]["h1"], probe["colors"]["bg"]),
            "bytes_loaded": cdn,
        }
        if scheme == "light":
            result["data"] = _check_data(kind, probe["charts"])  # before the specs are dropped below
            result["probe"] = {k: v for k, v in probe.items() if k != "drawn"}
            result["probe"]["charts"] = [{k: v for k, v in c.items() if k != "spec"} for c in probe["charts"]]
    # Narrow and wide: overflow and the chart still drawn.
    for width in (400, 1400):
        await cdp.send("Emulation.setDeviceMetricsOverride", width=width, height=900, deviceScaleFactor=1, mobile=width < 600)
        await asyncio.sleep(1.5)
        probe = json.loads((await cdp.send("Runtime.evaluate", expression=PROBE, returnByValue=True))["result"]["value"])
        result[f"w{width}"] = {"overflow": probe["overflow"], "drawn": probe["drawn"]}
    # Print: the chart is still shown.
    await cdp.send("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)
    await cdp.send("Emulation.setEmulatedMedia", media="print", features=[])
    await asyncio.sleep(1)
    probe = json.loads((await cdp.send("Runtime.evaluate", expression=PROBE, returnByValue=True))["result"]["value"])
    result["print"] = {"drawn": probe["drawn"]}
    await cdp.send("Emulation.setEmulatedMedia", media="", features=[])
    return result


async def main(out: Path, ids: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="exhibit-eval-"))
    (home / "exhibits").mkdir()
    for exhibit_id in ids:
        shutil.copytree(REAL_STORE / exhibit_id, home / "exhibits" / exhibit_id)
    os.environ["EXHIBIT_HOME"] = str(home)
    os.environ["EXHIBIT_NO_BROWSER"] = "1"
    spec = importlib.util.spec_from_file_location("exhibit_tool", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    base = tool._ensure_server()

    port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="exhibit-eval-edge-"))
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                             f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    report = {}
    try:
        for _ in range(60):
            try:
                _get(f"http://127.0.0.1:{port}/json/version")
                break
            except OSError:
                time.sleep(0.25)
        target = _get(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None) as ws:
            cdp = Cdp(ws)
            pump = asyncio.create_task(cdp.pump())
            for domain in ("Page", "Runtime", "Network"):
                await cdp.send(f"{domain}.enable")
            await cdp.send("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
            for exhibit_id in ids:
                meta = json.loads((home / "exhibits" / exhibit_id / "meta.json").read_text(encoding="utf-8"))
                version = len(meta["versions"])
                page = (home / "exhibits" / exhibit_id / f"v{version}.html").read_text(encoding="utf-8")
                kind = "sales" if "sales" in exhibit_id else "budget"
                checks = await _check(cdp, f"{base}raw/{exhibit_id}/{version}", out, exhibit_id, kind)
                checks["page_bytes"] = len(page.encode("utf-8"))
                checks["script_lines"] = _script_lines(page)
                checks["title"] = meta["title"]
                report[exhibit_id] = checks
                print("checked", exhibit_id, flush=True)
            pump.cancel()
    finally:
        tool._stop_server()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)], capture_output=True)
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", out / "report.json")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2:]))
