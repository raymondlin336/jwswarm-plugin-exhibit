"""Tests for the exhibit tool. Run with: python -m unittest discover plugin/tests"""

import asyncio
import enum
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path

TOOL_FILE = Path(__file__).parents[1] / "exhibit" / "tools" / "exhibit_tool.py"


def _install_openjiuwen_stand_in() -> None:
    class ToolCard:
        def __init__(self, **fields):
            self.__dict__.update(fields)

    class Tool:
        def __init__(self, card):
            self.card = card

    class ToolExposure(str, enum.Enum):
        DIRECT = "direct"
        DEFERRED = "deferred"

    module = types.ModuleType("openjiuwen.core.foundation.tool")
    module.Tool = Tool
    module.ToolCard = ToolCard
    module.ToolExposure = ToolExposure
    for name in ("openjiuwen", "openjiuwen.core", "openjiuwen.core.foundation"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["openjiuwen.core.foundation.tool"] = module


def _load_module():
    try:
        importlib.import_module("openjiuwen.core.foundation.tool")
    except Exception:  # noqa: BLE001 - no real openjiuwen here (or another test's stand-in)
        _install_openjiuwen_stand_in()
    spec = importlib.util.spec_from_file_location("exhibit_tool", TOOL_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load_module()
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http(url, method="GET", body=None, headers=None):
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with _NO_PROXY.open(request, timeout=5) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8")


class ExhibitToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["EXHIBIT_HOME"] = self.tmp.name
        os.environ["EXHIBIT_NO_BROWSER"] = "1"
        self.tool = MOD.ExhibitTool()

    def tearDown(self):
        MOD._stop_server()
        self.tmp.cleanup()

    def call(self, **inputs):
        return asyncio.run(self.tool.invoke(inputs))

    def show(self, **extra):
        inputs = {"action": "show", "title": "Test exhibit", "html": "<p>Hello</p>"}
        inputs.update(extra)
        result = self.call(**inputs)
        self.assertTrue(result["success"], result)
        return result

    # Tool behavior ---------------------------------------------------------
    def test_card_lists_all_actions(self):
        self.assertEqual(self.tool.card.name, "exhibit")
        self.assertEqual(self.tool.card.input_params["properties"]["action"]["enum"], list(MOD._ACTIONS))

    def test_card_is_directly_visible(self):
        # Progressive tool loading hides tools that don't declare an exposure.
        self.assertIsNotNone(MOD.ToolExposure)
        self.assertEqual(self.tool.card.exposure, MOD.ToolExposure.DIRECT)

    def test_show_creates_exhibit_and_wraps_body_html(self):
        result = self.show()
        self.assertEqual(result["version"], 1)
        self.assertFalse(result["opened"])
        self.assertTrue(result["exhibit_id"].startswith("test-exhibit-"))
        saved = Path(self.tmp.name, "exhibits", result["exhibit_id"], "v1.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", saved)
        self.assertIn("<p>Hello</p>", saved)

    def test_show_with_exhibit_id_adds_a_version(self):
        first = self.show()
        second = self.show(exhibit_id=first["exhibit_id"], title=None, html="<!doctype html><html><body>v2</body></html>")
        self.assertEqual(second["version"], 2)
        listed = self.call(action="list")["exhibits"]
        self.assertEqual(listed[0]["versions"], 2)

    def test_full_documents_are_kept_as_is(self):
        doc = "<!DOCTYPE html><html><head></head><body>x</body></html>"
        result = self.show(html=doc)
        saved = Path(self.tmp.name, "exhibits", result["exhibit_id"], "v1.html").read_text(encoding="utf-8")
        self.assertEqual(saved, doc)

    def test_bad_inputs_return_error_codes(self):
        self.assertEqual(self.call(action="nope")["error_code"], "invalid_input")
        self.assertEqual(self.call(action="show", title="t", html="  ")["error_code"], "invalid_input")
        self.assertEqual(self.call(action="show", html="<p>x</p>")["error_code"], "invalid_input")
        self.assertEqual(self.call(action="read", exhibit_id="../etc")["error_code"], "invalid_exhibit_id")
        self.assertEqual(self.call(action="read", exhibit_id="missing-abc123")["error_code"], "exhibit_not_found")
        exhibit = self.show()
        self.assertEqual(self.call(action="open", exhibit_id=exhibit["exhibit_id"], version=5)["error_code"], "invalid_version")
        too_big = "x" * (MOD._MAX_HTML_BYTES + 1)
        self.assertEqual(self.call(action="show", title="t", html=too_big)["error_code"], "too_large")

    def test_delete_needs_confirmation(self):
        exhibit = self.show()
        self.assertEqual(self.call(action="delete", exhibit_id=exhibit["exhibit_id"])["error_code"], "confirmation_required")
        self.assertTrue(self.call(action="delete", exhibit_id=exhibit["exhibit_id"], confirm=True)["success"])
        self.assertEqual(self.call(action="list")["exhibits"], [])

    def test_read_returns_data_and_html(self):
        exhibit = self.show()
        MOD._apply_data_op(exhibit["exhibit_id"], {"op": "set", "key": "count", "value": 3})
        result = self.call(action="read", exhibit_id=exhibit["exhibit_id"], include_html=True)
        self.assertEqual(result["data"], {"count": 3})
        self.assertIn("<p>Hello</p>", result["html"])
        self.assertFalse(result["truncated"])

    def test_data_ops_and_size_limit(self):
        exhibit_id = self.show()["exhibit_id"]
        MOD._apply_data_op(exhibit_id, {"op": "set", "key": "a", "value": [1, 2]})
        MOD._apply_data_op(exhibit_id, {"op": "set", "key": "b", "value": {"x": True}})
        MOD._apply_data_op(exhibit_id, {"op": "delete", "key": "a"})
        self.assertEqual(MOD._read_data(exhibit_id), {"b": {"x": True}})
        MOD._apply_data_op(exhibit_id, {"op": "clear"})
        self.assertEqual(MOD._read_data(exhibit_id), {})
        with self.assertRaises(MOD._ToolFailure):
            MOD._apply_data_op(exhibit_id, {"op": "set", "key": "big", "value": "x" * (MOD._MAX_DATA_BYTES + 1)})
        with self.assertRaises(MOD._ToolFailure):
            MOD._apply_data_op(exhibit_id, {"op": "drop"})

    # Server ------------------------------------------------------------------
    def test_server_serves_shell_and_sandboxed_exhibit(self):
        exhibit = self.show()
        status, headers, body = _http(exhibit["url"])
        self.assertEqual(status, 200)
        self.assertIn('sandbox="allow-scripts', body)
        self.assertNotIn("allow-same-origin", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

        base = exhibit["url"].split("/e/")[0]
        status, headers, body = _http(f"{base}/raw/{exhibit['exhibit_id']}/1")
        self.assertEqual(status, 200)
        csp = headers["Content-Security-Policy"]
        self.assertTrue(csp.startswith("sandbox allow-scripts"))
        self.assertIn("connect-src 'none'", csp)
        self.assertNotIn("allow-same-origin", csp)
        self.assertIn("window.exhibit", body)
        self.assertLess(body.index("window.exhibit"), body.index("<p>Hello</p>"))

    def test_api_reads_and_writes_data(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        api = f"{base}/api/{exhibit['exhibit_id']}/data"
        body = json.dumps({"op": "set", "key": "k", "value": "v"}).encode()
        status, _, _ = _http(api, "PUT", body, {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        status, _, text = _http(api)
        self.assertEqual(json.loads(text), {"values": {"k": "v"}})

    def test_server_refuses_wrong_token_host_and_cross_site(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        port = base.split(":")[2].split("/")[0]
        api = f"{base}/api/{exhibit['exhibit_id']}/data"
        put = json.dumps({"op": "set", "key": "k", "value": 1}).encode()

        self.assertEqual(_http(f"http://127.0.0.1:{port}/wrongtoken/health")[0], 404)
        self.assertEqual(_http(f"{base}/health", headers={"Host": f"evil.example:{port}"})[0], 421)
        self.assertEqual(_http(api, headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(
            _http(api, "PUT", put, {"Content-Type": "application/json", "Origin": "null"})[0], 403
        )
        self.assertEqual(_http(api, "PUT", put, {"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(MOD._read_data(exhibit["exhibit_id"]), {})

    def test_stop_then_show_restarts_server(self):
        first = self.show()
        old_health = first["url"].split("/e/")[0] + "/health"
        self.assertTrue(self.call(action="stop")["stopped"])
        with self.assertRaises(OSError):
            _http(old_health)
        second = self.call(action="open", exhibit_id=first["exhibit_id"])
        self.assertTrue(second["success"], second)
        self.assertEqual(_http(second["url"])[0], 200)


if __name__ == "__main__":
    unittest.main()
