"""Tests for the exhibit tool.

Run with plugin\\run_tests.ps1: they need Python 3.11 with the real openjiuwen framework, like WorkSwarm.
"""

import asyncio
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


def _load_module():
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

    def test_duplicate_names_get_numbered(self):
        first = self.show(title="Benchmark results")
        second = self.show(title="Benchmark results")
        third = self.show(title="benchmark RESULTS")  # case doesn't matter
        self.assertEqual(first["title"], "Benchmark results")
        self.assertEqual(second["title"], "Benchmark results (2)")
        self.assertEqual(third["title"], "benchmark RESULTS (3)")
        again = self.show(title="Benchmark results (2)")  # no "(2) (2)"
        self.assertEqual(again["title"], "Benchmark results (4)")
        # A new version keeping its own title isn't renumbered.
        kept = self.show(exhibit_id=second["exhibit_id"], title="Benchmark results (2)", html="<p>v2</p>")
        self.assertEqual(kept["title"], "Benchmark results (2)")
        # Renaming onto a taken name is numbered too; renaming to its own name isn't.
        self.assertEqual(MOD._rename_exhibit(first["exhibit_id"], "Benchmark results (3)")["title"], "Benchmark results (5)")
        self.assertEqual(MOD._rename_exhibit(second["exhibit_id"], "Benchmark results (2)")["title"], "Benchmark results (2)")
        self.assertEqual(MOD._rename_exhibit(second["exhibit_id"], "Something new")["title"], "Something new")
        long_title = "x" * MOD._MAX_TITLE_CHARS
        self.show(title=long_title)
        numbered = self.show(title=long_title)["title"]
        self.assertTrue(numbered.endswith(" (2)") and len(numbered) == MOD._MAX_TITLE_CHARS)

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
        self.assertEqual(self.call(action="show", title="t", html="  ")["error_code"], "missing_html")
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

    def test_show_accepts_a_saved_html_file(self):
        page = Path(self.tmp.name, "deck.html")
        page.write_text("<!doctype html><html><body>From a file</body></html>", encoding="utf-8")
        result = self.show(html=None, html_file=str(page))
        saved = Path(self.tmp.name, "exhibits", result["exhibit_id"], "v1.html").read_text(encoding="utf-8")
        self.assertIn("From a file", saved)
        both = self.show(html="<p>inline wins</p>", html_file=str(page))
        self.assertIn("inline wins", Path(self.tmp.name, "exhibits", both["exhibit_id"], "v1.html").read_text(encoding="utf-8"))

    def test_html_file_errors_say_what_to_do(self):
        def code(**extra):
            return self.call(action="show", title="t", **extra)

        missing = code()
        self.assertEqual(missing["error_code"], "missing_html")
        self.assertIn("html_file", missing["error"])  # tells the agent the other route
        self.assertEqual(code(html_file="deck.html")["error_code"], "invalid_input")  # not a full path
        self.assertEqual(code(html_file=str(Path(self.tmp.name, "deck.txt")))["error_code"], "invalid_input")
        not_there = code(html_file=str(Path(self.tmp.name, "nope.html")))
        self.assertEqual(not_there["error_code"], "file_not_found")
        self.assertIn("write_file", not_there["error"])

    def test_results_include_the_reference(self):
        exhibit = self.show(title="Benchmark scores by app")
        code = exhibit["exhibit_id"].rsplit("-", 1)[-1]
        self.assertEqual(exhibit["reference"], f"@exhibit(Benchmark scores by app #{code})")
        self.assertEqual(self.call(action="list")["exhibits"][0]["reference"], exhibit["reference"])
        self.assertEqual(self.call(action="read", exhibit_id=exhibit["exhibit_id"])["reference"], exhibit["reference"])

    def test_exhibit_id_accepts_codes_and_references(self):
        exhibit = self.show(title="Benchmark scores by app")
        full = exhibit["exhibit_id"]
        code = full.rsplit("-", 1)[-1]
        MOD._rename_exhibit(full, "Renamed since")
        for given in (full, code, "#" + code, f"@exhibit(Benchmark scores by app #{code})",
                      f"@exhibit(Old name #{code}, version 1)"):
            result = self.call(action="read", exhibit_id=given)
            self.assertTrue(result["success"], (given, result))
            self.assertEqual((result["exhibit_id"], result["title"]), (full, "Renamed since"))
        edited = self.show(exhibit_id="#" + code, title=None, html="<p>v2</p>")
        self.assertEqual((edited["exhibit_id"], edited["version"]), (full, 2))
        self.assertEqual(self.call(action="read", exhibit_id="#000000")["error_code"], "invalid_exhibit_id")

    def test_versions_are_cached_and_pages_are_not(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        _, headers, _ = _http(f"{base}/raw/{exhibit['exhibit_id']}/1")
        self.assertEqual(headers["Cache-Control"], "private, max-age=31536000, immutable")  # a version never changes
        for page in (exhibit["url"], base + "/"):
            self.assertEqual(_http(page)[1]["Cache-Control"], "no-store")  # pages show live state

    def test_thumbnails_load_a_calm_copy(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        gallery = _http(base + "/")[2]
        self.assertIn(f'src="/{base.split("/")[-1]}/raw/{exhibit["exhibit_id"]}/1?thumb=1&b={MOD._BUILD}"', gallery)
        calm = _http(f"{base}/raw/{exhibit['exhibit_id']}/1?thumb=1")[2]
        self.assertIn('Object.defineProperty(window, "Chart"', calm)
        self.assertIn("animation:none!important", calm)
        full = _http(f"{base}/raw/{exhibit['exhibit_id']}/1")[2]
        self.assertNotIn('Object.defineProperty(window, "Chart"', full)  # the exhibit itself keeps animations
        self.assertIn("window.exhibit", full)
        self.assertIn('channel: "exhibit-quote"', full)  # selections can be quoted in the viewer
        self.assertNotIn('channel: "exhibit-quote"', calm)  # but not in thumbnails

    def test_viewer_offers_copy_reference_and_quote(self):
        exhibit = self.show()
        page = _http(exhibit["url"])[2]
        self.assertIn('id="copy-ref"', page)
        self.assertIn('id="quote-btn"', page)
        self.assertIn(f'/raw/{exhibit["exhibit_id"]}/1?b={MOD._BUILD}"', page)  # a plugin update refetches pages
        self.assertIn('id="delete-exhibit"', page)  # delete is its own button in the bar
        self.assertNotIn('label: "Copy reference"', page)  # the bar's actions aren't repeated in the menu
        self.assertNotIn('label: "Delete"', page)
        self.assertIn('label: "Copy reference"', _http(exhibit["url"].split("/e/")[0] + "/")[2])

    def test_export_html_is_a_standalone_file_with_saved_data(self):
        exhibit = self.show(title='Budget: "Q1" / 2026', html="<html><head></head><body><p>v1</p></body></html>")
        exhibit_id = exhibit["exhibit_id"]
        self.show(exhibit_id=exhibit_id, title=None, html="<html><head></head><body><p>v2</p></body></html>")
        MOD._apply_data_op(exhibit_id, {"op": "set", "key": "note", "value": "</script><b>x</b>"})
        base = exhibit["url"].split("/e/")[0]
        status, headers, page = _http(f"{base}/api/{exhibit_id}/export")
        self.assertEqual(status, 200)
        self.assertIn("attachment;", headers["Content-Disposition"])
        self.assertIn("filename*=UTF-8''Budget%20Q1%202026.html", headers["Content-Disposition"])
        self.assertIn("<p>v2</p>", page)  # the latest version by default
        self.assertIn("window.exhibit", page)
        self.assertIn("\u003c/script>", page)  # saved data can't close the script early
        self.assertNotIn("</script><b>", page)
        self.assertNotIn("parent.postMessage", page)  # no viewer to talk to in a downloaded file
        self.assertIn("<p>v1</p>", _http(f"{base}/api/{exhibit_id}/export?v=1")[2])
        refused = _http(f"{base}/api/{exhibit_id}/export", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(refused[0], 403)
        viewer = _http(exhibit["url"])[2]
        self.assertIn('id="export"', viewer)
        self.assertIn('label: "HTML file (.html)"', viewer)

    def test_new_codes_are_unique(self):
        first = self.show(title="Alpha")["exhibit_id"]
        taken = first.rsplit("-", 1)[-1]
        codes = iter([taken, taken, "abcdef"])
        real = MOD.secrets.token_hex
        MOD.secrets.token_hex = lambda n: next(codes)
        try:
            second = self.show(title="Beta")["exhibit_id"]
        finally:
            MOD.secrets.token_hex = real
        self.assertEqual(second, "beta-abcdef")

    def test_records_the_chat_session_and_points_to_its_history(self):
        def session(sid, parent=None):
            return types.SimpleNamespace(get_session_id=lambda: sid, get_parent_session_id=lambda: parent)

        jw = Path(self.tmp.name, "jw")
        history = jw / "agent" / "sessions" / "web_a1" / "history.jsonl"
        history.parent.mkdir(parents=True)
        history.write_text("{}\n", encoding="utf-8")
        os.environ["JIUWENSWARM_HOME"] = str(jw)
        self.addCleanup(os.environ.pop, "JIUWENSWARM_HOME", None)

        inputs = {"action": "show", "title": "Chart", "html": "<p>1</p>"}
        exhibit_id = asyncio.run(self.tool.invoke(inputs, session=session("web_a1")))["exhibit_id"]
        # A sub-agent's call is recorded under the chat that owns it.
        edit = {"action": "show", "exhibit_id": exhibit_id, "html": "<p>2</p>"}
        asyncio.run(self.tool.invoke(edit, session=session("child_9", parent="web_b2")))
        self.show(exhibit_id=exhibit_id, html="<p>3</p>")  # no session: nothing recorded

        meta = json.loads(Path(self.tmp.name, "exhibits", exhibit_id, "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["session_id"], "web_a1")
        self.assertEqual([v.get("session_id") for v in meta["versions"]], ["web_a1", "web_b2", None])
        read = self.call(action="read", exhibit_id=exhibit_id)
        self.assertEqual(read["session_id"], "web_a1")
        self.assertEqual(read["sessions"], ["web_a1", "web_b2"])
        self.assertEqual(read["session_history"], {"web_a1": str(history)})
        self.assertEqual(self.call(action="list")["exhibits"][0]["session_id"], "web_a1")
        # Exhibits made before sessions were recorded just leave the fields out.
        self.assertNotIn("session_id", self.call(action="read", exhibit_id=self.show(title="Old")["exhibit_id"]))

    def test_old_duplicate_codes_resolve_to_the_most_recent(self):
        older = self.show(title="Older")["exhibit_id"]
        code = older.rsplit("-", 1)[-1]
        root = Path(os.environ["EXHIBIT_HOME"], "exhibits")
        newer = root / f"newer-{code}"  # made before 0.2.2, when codes could repeat
        newer.mkdir()
        meta = json.loads((root / older / "meta.json").read_text(encoding="utf-8"))
        (newer / "v1.html").write_text("<p>new</p>", encoding="utf-8")
        (newer / "meta.json").write_text(json.dumps({**meta, "id": newer.name, "title": "Newer"}), encoding="utf-8")
        os.utime(root / older / "meta.json", (1, 1))
        self.assertEqual(self.call(action="read", exhibit_id="#" + code)["exhibit_id"], newer.name)

    def test_gallery_updates_in_place_after_rename_or_delete(self):
        exhibit = self.show()
        gallery = _http(exhibit["url"].split("/e/")[0] + "/")[2]
        script = gallery.split("// More actions on each exhibit.")[1]
        self.assertIn("applyRename(id, result.title)", script)
        self.assertIn("applyDelete(id)", script)
        self.assertEqual(script.count("location.reload()"), 1)  # only when the last exhibit is deleted
        self.assertIn(f'class="card-wrap" data-id="{exhibit["exhibit_id"]}"', gallery)
        self.assertIn(f'class="file-wrap" data-id="{exhibit["exhibit_id"]}"', gallery)

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

    def test_column_lists_open_tabs_newest_first_with_new_button_and_search(self):
        first, second = self.show(title="First one"), self.show(title="Second one")
        status, _, body = _http(first["url"])
        self.assertEqual(status, 200)
        self.assertIn('id="new-exhibit"', body)
        self.assertIn('<input id="q" type="search"', body)
        self.assertLess(body.index(f'data-close="{second["exhibit_id"]}"'), body.index(f'data-close="{first["exhibit_id"]}"'))
        self.assertIn('class="row on"', body)  # the open exhibit is highlighted
        self.assertIn('"title": "Second one"', body)  # all exhibits embedded for search

    def test_panel_collapsed_state_is_remembered(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        put = json.dumps({"op": "panel", "collapsed": True}).encode()
        self.assertEqual(_http(base + "/api/tabs", "PUT", put, {"Content-Type": "application/json", "Origin": "null"})[0], 403)
        self.assertEqual(_http(base + "/api/tabs", "PUT", put, {"Content-Type": "application/json"})[0], 200)
        self.assertIn('<body class="collapsed">', _http(base + "/")[2])
        put = json.dumps({"op": "panel", "collapsed": False}).encode()
        _http(base + "/api/tabs", "PUT", put, {"Content-Type": "application/json"})
        self.assertIn('<body class="">', _http(base + "/")[2])

    def test_titles_cannot_break_out_of_the_inline_config(self):
        exhibit = self.show(title="</script><script>alert(1)</script>")
        body = _http(exhibit["url"])[2]
        self.assertNotIn("</script><script>alert(1)", body)

    def test_viewer_bar_has_editable_title_and_version_menu(self):
        exhibit = self.show(summary="Not shown in the bar")
        body = _http(exhibit["url"])[2]
        self.assertIn('<input class="title-input" id="title" value="Test exhibit"', body)
        self.assertNotIn("Not shown in the bar", body.split("<main")[1].split("<script")[0])
        self.assertNotIn("Sandboxed", body)
        self.assertNotIn('id="ver-btn"', body)  # a single version has nothing to pick
        for n in (2, 3):
            self.show(exhibit_id=exhibit["exhibit_id"], title=None, html=f"<p>v{n}</p>")
        latest = _http(exhibit["url"])[2]
        self.assertIn("Version 3 of 3", latest)
        self.assertIn('<span class="latest">Latest</span>', latest)
        self.assertNotIn('class="ver-btn old"', latest)
        older = _http(exhibit["url"] + "?v=1")[2]
        self.assertIn("Version 1 of 3", older)
        self.assertIn('class="ver-btn old"', older)  # stands out when not on the latest

    def test_delete_api_needs_confirm_and_same_origin(self):
        keep, gone = self.show(title="Keep"), self.show(title="Gone")
        base = gone["url"].split("/e/")[0]
        url = f"{base}/api/{gone['exhibit_id']}/delete"

        def delete(body, headers=None):
            return _http(url, "PUT", json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})

        self.assertEqual(delete({"confirm": True}, {"Origin": "null"})[0], 403)
        self.assertEqual(delete({})[0], 400)  # no confirm, nothing deleted
        self.assertEqual(delete({"confirm": "yes"})[0], 400)
        self.assertTrue(Path(self.tmp.name, "exhibits", gone["exhibit_id"]).is_dir())
        status, _, text = delete({"confirm": True})
        self.assertEqual((status, json.loads(text)["tabs"]), (200, [keep["exhibit_id"]]))
        self.assertFalse(Path(self.tmp.name, "exhibits", gone["exhibit_id"]).exists())
        self.assertEqual(delete({"confirm": True})[0], 404)

    def test_more_actions_buttons(self):
        exhibit = self.show(title="Q1 <plan>")
        base = exhibit["url"].split("/e/")[0]
        gallery = _http(base + "/")[2]
        self.assertEqual(gallery.count(f'class="more-btn" type="button" data-id="{exhibit["exhibit_id"]}"'), 2)  # card + row
        self.assertIn('data-title="Q1 &lt;plan&gt;"', gallery)  # escaped
        self.assertIn('{ label: "Rename"', gallery)
        self.assertIn('id="item-menu"', gallery)
        self.assertIn('id="modal"', gallery)
        viewer = _http(exhibit["url"])[2]
        self.assertIn('id="exhibit-more"', viewer)
        self.assertNotIn('label: "Rename"', viewer)  # only delete in the exhibit bar

    def test_rename_api(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        url = f"{base}/api/{exhibit['exhibit_id']}/title"

        def rename(title, headers=None):
            body = json.dumps({"title": title}).encode()
            return _http(url, "PUT", body, {"Content-Type": "application/json", **(headers or {})})

        self.assertEqual(rename("Hijacked", {"Origin": "null"})[0], 403)
        self.assertEqual(rename("   ")[0], 400)
        status, _, text = rename("  Benchmark   scores by app ")
        self.assertEqual((status, json.loads(text)["title"]), (200, "Benchmark scores by app"))
        self.assertEqual(MOD._load_meta(exhibit["exhibit_id"])["title"], "Benchmark scores by app")
        self.assertEqual(len(json.loads(rename("x" * 500)[2])["title"]), MOD._MAX_TITLE_CHARS)
        self.assertEqual(len(MOD._load_meta(exhibit["exhibit_id"])["versions"]), 1)  # no new version

    def test_gallery_action_returns_the_exhibits_page(self):
        self.show(summary="Shown in the gallery")
        result = self.call(action="gallery")
        self.assertTrue(result["success"], result)
        self.assertFalse(result["opened"])  # browser disabled in tests
        status, _, body = _http(result["url"])
        self.assertEqual(status, 200)
        self.assertIn("Shown in the gallery", body)
        self.assertEqual(self.call(action="list")["gallery_url"], result["url"])

    def test_server_from_older_code_is_not_reused(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        def fake_health(build):
            class Health(BaseHTTPRequestHandler):
                def do_GET(self):
                    body = json.dumps({"ok": True, "pid": os.getpid(), **({"build": build} if build else {})}).encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *args):
                    pass

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Health)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            self.addCleanup(httpd.server_close)
            self.addCleanup(httpd.shutdown)
            return httpd.server_address[1]

        old_port, same_port = fake_health(None), fake_health(MOD._BUILD)
        self.assertFalse(MOD._probe(old_port, "token"))  # no build id: an older version
        self.assertTrue(MOD._probe(same_port, "token"))

        MOD._atomic_write(Path(self.tmp.name, "server.json"),
                          json.dumps({"port": old_port, "token": "token", "pid": os.getpid()}))
        url = MOD._ensure_server()
        self.assertNotIn(f":{old_port}/", url)  # started a fresh server instead

    # Gallery, tabs and summaries ------------------------------------------
    def test_summary_is_stored_or_derived(self):
        given = self.show(summary="Scores   for 20 tests")
        self.assertEqual(MOD._load_meta(given["exhibit_id"])["summary"], "Scores for 20 tests")
        html = "<h1>Test exhibit</h1><p>Compares three apps across twenty tests</p><script>x()</script>"
        derived = self.show(html=html)
        self.assertEqual(MOD._load_meta(derived["exhibit_id"])["summary"], "Compares three apps across twenty tests")
        updated = self.show(exhibit_id=given["exhibit_id"], title=None, html="<p>v2</p>")
        self.assertEqual(MOD._load_meta(updated["exhibit_id"])["summary"], "Scores for 20 tests")  # kept

    def test_exhibits_are_sorted_by_created_date(self):
        older, newer = self.show(title="Older"), self.show(title="Newer")
        self.show(exhibit_id=older["exhibit_id"], title=None, html="<p>edited later</p>")  # updated, not created
        listed = [e["exhibit_id"] for e in self.call(action="list")["exhibits"]]
        self.assertEqual(listed, [newer["exhibit_id"], older["exhibit_id"]])

    def test_show_and_open_add_tabs_and_delete_removes_them(self):
        first, second = self.show(), self.show(title="Other exhibit")
        self.assertEqual(MOD._load_tabs(), [first["exhibit_id"], second["exhibit_id"]])
        self.call(action="open", exhibit_id=first["exhibit_id"])
        self.assertEqual(MOD._load_tabs(), [first["exhibit_id"], second["exhibit_id"]])  # no duplicates
        self.call(action="delete", exhibit_id=first["exhibit_id"], confirm=True)
        self.assertEqual(MOD._load_tabs(), [second["exhibit_id"]])

    def test_gallery_shows_cards_with_thumbnails_and_rail(self):
        exhibit = self.show(summary="A short description")
        MOD._apply_data_op(exhibit["exhibit_id"], {"op": "set", "key": "k", "value": 1})
        base = exhibit["url"].split("/e/")[0]
        status, headers, body = _http(base + "/")
        self.assertEqual(status, 200)
        self.assertIn("a short description", body)  # searchable, though not shown
        self.assertNotIn('class="desc"', body)
        self.assertNotIn("version", body.split("<main>")[1].split("<script")[0].lower())  # no version counts
        self.assertIn("Updated ", body)
        self.assertIn("<br>Created ", body)
        self.assertIn('class="card"', body)
        self.assertIn('class="file-row"', body)  # every exhibit also has a list row
        self.assertNotIn("Today<", body)  # no time-based groups
        self.assertNotIn("<h1>", body)  # no page title
        self.assertNotIn("More exhibits", body)
        self.assertNotRegex(body, r'class="ico[ "]')  # no letter icons (icon-btn is a button)
        self.assertNotIn('id="expand"', body)  # collapsed column comes back via the rail only
        self.assertIn(f'data-close="{exhibit["exhibit_id"]}"', body)  # open as a tab in the rail
        self.assertIn('class="thumb"><iframe loading="lazy"', body)
        self.assertIn('class="nav-row on"', body)  # All exhibits link, current page
        self.assertNotIn("allow-same-origin", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_tabs_api_closes_and_refuses_cross_site(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        body = json.dumps({"op": "close", "id": exhibit["exhibit_id"]}).encode()
        self.assertEqual(_http(base + "/api/tabs", "PUT", body, {"Content-Type": "application/json", "Origin": "null"})[0], 403)
        self.assertEqual(MOD._load_tabs(), [exhibit["exhibit_id"]])
        status, _, text = _http(base + "/api/tabs", "PUT", body, {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["tabs"], [])
        self.assertEqual(_http(exhibit["url"])[0], 200)  # visiting reopens the tab
        self.assertEqual(MOD._load_tabs(), [exhibit["exhibit_id"]])

    def test_logo_route_serves_svg_or_404(self):
        base = self.show()["url"].split("/e/")[0]
        status, headers, _ = _http(base + "/logo.svg")
        if MOD._workswarm_logo() is None:
            self.assertEqual(status, 404)
        else:
            self.assertEqual((status, headers["Content-Type"]), (200, "image/svg+xml"))
            self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

    def test_stamp_shows_local_date_and_time(self):
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 11, 5, 18, 0, tzinfo=timezone.utc)
        self.assertRegex(MOD._stamp(now.isoformat(), now), r"^[A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d\d (AM|PM)$")
        self.assertRegex(MOD._stamp((now - timedelta(days=400)).isoformat(), now), r", 20\d\d, ")  # older years
        self.assertEqual(MOD._stamp("not a date"), "")


if __name__ == "__main__":
    unittest.main()
