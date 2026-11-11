"""Hover test for chart-kit exhibits: moves a real mouse over a data point (or pie slice) in headless
Edge, then records the tooltip text and saves a screenshot (light and dark).

    python -X utf8 eval/chart_hover.py <store_dir> <out_dir> <exhibit_id> [...]
<store_dir> is a store made by eval/chart_samples.py (it's copied; nothing in it is changed).
"""
from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).parent))
from chart_check import EDGE, TOOL, Cdp, _free_port, _get  # noqa: E402

# Where to point: the 7th point of the first series, or the middle of the first pie slice.
TARGET = r"""
(() => {
  const el = document.querySelector("#chart"), inst = echarts.getInstanceByDom(el);
  const box = el.getBoundingClientRect(), opt = inst.getOption(), s = opt.series[0];
  let x, y;
  if (s.type === "pie") {
    const l = inst.getModel().getSeriesByIndex(0).getData().getItemLayout(0);
    const a = (l.startAngle + l.endAngle) / 2, r = (l.r + l.r0) / 2;
    x = l.cx + r * Math.cos(a); y = l.cy + r * Math.sin(a);
  } else {
    const i = Math.min(6, s.data.length - 1);
    const point = Array.isArray(s.data[i]) ? s.data[i] : (opt.yAxis[0].type === "category" ? [s.data[i], i] : [i, s.data[i]]);
    [x, y] = inst.convertToPixel({ seriesIndex: 0 }, point);
  }
  return JSON.stringify({ x: box.left + x, y: box.top + y });
})()
"""
TOOLTIP = r"""
(() => {
  const tips = [...document.querySelectorAll("#chart div")].filter((d) => d.style.position === "absolute" && getComputedStyle(d).display !== "none" && d.textContent.trim());
  return tips.length ? tips[tips.length - 1].innerText : "";
})()
"""


async def run(store: Path, out: Path, ids: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="exhibit-hover-"))
    shutil.copytree(store / "exhibits", home / "exhibits")
    os.environ["EXHIBIT_HOME"] = str(home)
    os.environ["EXHIBIT_NO_BROWSER"] = "1"
    spec = importlib.util.spec_from_file_location("exhibit_tool", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    base = tool._ensure_server()
    port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="exhibit-hover-edge-"))
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", f"--remote-debugging-port={port}",
                             f"--user-data-dir={profile}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            await cdp.send("Page.enable")
            await cdp.send("Emulation.setDeviceMetricsOverride", width=1100, height=560, deviceScaleFactor=1, mobile=False)
            for exhibit_id in ids:
                for scheme in ("light", "dark"):
                    await cdp.send("Emulation.setEmulatedMedia", media="", features=[{"name": "prefers-color-scheme", "value": scheme}])
                    await cdp.send("Page.navigate", url=f"{base}raw/{exhibit_id}/1")
                    await asyncio.sleep(3)
                    point = json.loads((await cdp.send("Runtime.evaluate", expression=TARGET, returnByValue=True))["result"]["value"])
                    for dx in (8, 0):  # arrive, then settle on the point
                        await cdp.send("Input.dispatchMouseEvent", type="mouseMoved", x=point["x"] + dx, y=point["y"])
                        await asyncio.sleep(0.4)
                    await asyncio.sleep(0.6)
                    tip = (await cdp.send("Runtime.evaluate", expression=TOOLTIP, returnByValue=True))["result"]["value"]
                    shot = await cdp.send("Page.captureScreenshot", format="png")
                    (out / f"{exhibit_id}-hover-{scheme}.png").write_bytes(base64.b64decode(shot["data"]))
                    report.setdefault(exhibit_id, {})[scheme] = tip
                print("hovered", exhibit_id, flush=True)
            pump.cancel()
    finally:
        tool._stop_server()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)], capture_output=True)
    (out / "hover.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]))
