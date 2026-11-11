"""Edit test for the chart kit's data: opens an exhibit in the real viewer (so saving works),
edits a value in the Edit data panel in the top bar, checks the chart redraws, reloads to check the edit was
saved, then resets. Also saves screenshots with the table open, light and dark.

    python -X utf8 eval/chart_edit.py <store_dir> <out_dir> <exhibit_id> [...]
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
from chart_check import EDGE, TOOL, _free_port, _get  # noqa: E402


class Cdp:
    """A DevTools connection that can also talk to the exhibit's iframe (its own target)."""

    def __init__(self, ws):
        self.ws, self.n, self.pending, self.events = ws, 0, {}, []

    async def pump(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.pending:
                self.pending.pop(msg["id"]).set_result(msg)
            else:
                self.events.append(msg)

    async def send(self, method: str, session: str | None = None, **params):
        self.n += 1
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.n] = fut
        msg = {"id": self.n, "method": method, "params": params}
        if session:
            msg["sessionId"] = session
        await self.ws.send(json.dumps(msg))
        msg = await asyncio.wait_for(fut, 30)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get("result", {})


# In the exhibit's frame: the chart and the page around it.
STATE = r"""
(() => {
  const el = document.querySelector("#chart") || document.querySelector("[_echarts_instance_]");
  const inst = el && window.echarts && echarts.getInstanceByDom(el);
  const s = inst ? inst.getOption().series[0] : null;
  const first = s ? s.data[0] : null;
  const total = document.querySelector("#total");
  return JSON.stringify({
    first: first && typeof first === "object" && !Array.isArray(first) ? first.value : first,
    firstName: first && first.name,
    in_page_editor: !!document.querySelector(".exhibit-chart-data"),
    total: total ? total.textContent : null,
    page: document.body.innerText.replace(/\s+/g, " ").slice(0, 4000),
  });
})()
"""
# In the viewer around it: the Edit data button and panel in the top bar.
PANEL = r"""
(() => {
  const btn = document.getElementById("data-btn"), panel = document.getElementById("data-panel");
  const badge = panel.querySelector(".dp-badge");
  return JSON.stringify({
    button: !btn.hidden, open: !panel.hidden,
    rows: panel.querySelectorAll("tbody tr").length,
    cell: (panel.querySelector("tbody input.numin") || {}).value,
    note: (panel.querySelector(".dp-note") || {}).textContent,
    edited: badge ? !badge.hidden : null,
  });
})()
"""
OPEN = r"""(() => { const p = document.getElementById("data-panel"); if (p.hidden) document.getElementById("data-btn").click(); return "ok"; })()"""
EDIT = r"""
(() => {
  const p = document.getElementById("data-panel");
  if (p.hidden) document.getElementById("data-btn").click();
  const cell = p.querySelector("tbody input.numin");
  cell.value = "99"; cell.dispatchEvent(new Event("input", { bubbles: true }));
  return "ok";
})()
"""
RESET = r"""(() => { document.querySelector("#data-panel .dp-reset").click(); return "ok"; })()"""


async def frame_session(cdp: Cdp, timeout: float = 8) -> str:
    """Session id of the exhibit iframe's target (out of process, since the frame is sandboxed)."""
    end = time.time() + timeout
    while time.time() < end:
        for e in reversed(cdp.events):
            if e.get("method") == "Target.attachedToTarget" and e["params"]["targetInfo"]["type"] == "iframe":
                return e["params"]["sessionId"]
        await asyncio.sleep(0.2)
    raise RuntimeError("the exhibit frame never attached")


async def evaluate(cdp: Cdp, session: str, expression: str):
    result = await cdp.send("Runtime.evaluate", session=session, expression=expression, returnByValue=True)
    value = result["result"].get("value")
    return json.loads(value) if isinstance(value, str) and value.startswith("{") else value


async def load(cdp: Cdp, url: str) -> str:
    cdp.events.clear()
    await cdp.send("Page.navigate", url=url)
    session = await frame_session(cdp)
    await cdp.send("Runtime.runIfWaitingForDebugger", session=session)
    await asyncio.sleep(3.5)
    return session


async def run(store: Path, out: Path, ids: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="exhibit-edit-"))
    shutil.copytree(store / "exhibits", home / "exhibits")
    os.environ["EXHIBIT_HOME"] = str(home)
    os.environ["EXHIBIT_NO_BROWSER"] = "1"
    spec = importlib.util.spec_from_file_location("exhibit_tool", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    base = tool._ensure_server()
    port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="exhibit-edit-edge-"))
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--site-per-process",
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
            await cdp.send("Page.enable")
            await cdp.send("Target.setAutoAttach", autoAttach=True, waitForDebuggerOnStart=False, flatten=True)
            await cdp.send("Emulation.setDeviceMetricsOverride", width=1200, height=1000, deviceScaleFactor=1, mobile=False)
            for exhibit_id in ids:
                url = f"{base}e/{exhibit_id}"
                steps = {}
                session = await load(cdp, url)
                async def both():
                    return {**await evaluate(cdp, session, STATE), "panel": await evaluate(cdp, None, PANEL)}
                steps["start"] = await both()
                await evaluate(cdp, None, EDIT)
                await asyncio.sleep(1.5)
                steps["edited"] = await both()
                session = await load(cdp, url)
                steps["reloaded"] = await both()
                for scheme in ("light", "dark"):
                    await cdp.send("Emulation.setEmulatedMedia", media="", features=[{"name": "prefers-color-scheme", "value": scheme}])
                    session = await load(cdp, url)
                    await evaluate(cdp, None, OPEN)
                    await asyncio.sleep(0.5)
                    shot = await cdp.send("Page.captureScreenshot", format="png")
                    (out / f"{exhibit_id}-table-{scheme}.png").write_bytes(base64.b64decode(shot["data"]))
                await cdp.send("Emulation.setEmulatedMedia", media="", features=[])
                await evaluate(cdp, None, RESET)
                await asyncio.sleep(1)
                steps["reset"] = await both()
                session = await load(cdp, url)
                steps["reset_reloaded"] = await both()
                saved = json.loads(((home / "exhibits" / exhibit_id / "data.json").read_text(encoding="utf-8"))
                                   if (home / "exhibits" / exhibit_id / "data.json").exists() else "{}")
                steps["saved_keys_after_reset"] = sorted(saved)
                report[exhibit_id] = steps
                print("edited", exhibit_id, flush=True)
            pump.cancel()
    finally:
        tool._stop_server()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(edge.pid)], capture_output=True)
    (out / "edit.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]))
