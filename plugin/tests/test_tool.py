"""Tests for the exhibit tool.

Run with plugin\\run_tests.ps1: they need Python 3.11 with the real openjiuwen framework, like WorkSwarm.
"""

import asyncio
import importlib.util
import json
import os
import re
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

    # Presets -----------------------------------------------------------------
    def test_preset_returns_the_starting_page(self):
        for name in ("document", "slides"):
            result = self.call(action="preset", name=name)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["preset"], name)
            self.assertRegex(result["html"], f'<meta name="exhibit-preset" content="{name}@\\d+">')
            self.assertIn("show", result["next"])
        freeform = self.call(action="preset", name="Freeform ")
        self.assertEqual((freeform["preset"], "html" in freeform), ("freeform", False))
        # "none" was the old name, and still works.
        self.assertEqual(self.call(action="preset", name="none")["preset"], "freeform")

    def test_preset_without_a_name_lists_them_and_bad_names_fail(self):
        listed = self.call(action="preset")
        self.assertEqual([p["name"] for p in listed["presets"]], ["document", "slides", "charts", "freeform"])
        bad = self.call(action="preset", name="poster")
        self.assertEqual((bad["success"], bad["error_code"]), (False, "invalid_preset"))
        self.assertEqual(self.tool.card.input_params["properties"]["name"]["enum"], ["document", "slides", "charts", "freeform"])

    def test_preset_files_follow_the_exhibit_rules(self):
        for name in ("document", "slides"):
            page = (MOD._PRESET_DIR / f"{name}.html").read_text(encoding="utf-8")
            self.assertTrue(page.startswith("<!doctype html>"), name)
            # Theme: light by default, dark only for the screen theme, and paper always light.
            self.assertIn("@media (prefers-color-scheme: dark)", page, name)
            self.assertIn("@media print", page, name)
            # CSP: nothing loaded from the network, so nothing for the page's CSP to block.
            self.assertNotRegex(page, r'(?:src|href)\s*=\s*"(?:https?:)?//', name)
            self.assertNotRegex(page, r"@import|url\(\s*['\"]?https?:", name)
            self.assertNotRegex(page, r"\bfetch\(|XMLHttpRequest|localStorage", name)
            # The guidance comment stays a single comment.
            comment = page.split("<!--", 1)[1].split("-->", 1)[0]
            self.assertNotIn("--", comment, name)
            # Served through the viewer with the saved-data bridge, like any exhibit.
            shown = self.show(title=f"Preset {name}", html=page)
            status, _, served = _http(shown["url"].replace("/e/", "/raw/") + "/1")
            self.assertEqual(status, 200)
            self.assertIn("window.exhibit", served)

    def test_titles_show_what_kind_of_exhibit_it_is(self):
        doc = self.show(title="Report", html=(MOD._PRESET_DIR / "document.html").read_text(encoding="utf-8"))
        deck = self.show(title="Deck", html=(MOD._PRESET_DIR / "slides.html").read_text(encoding="utf-8"))
        plain = self.show(title="Plain")
        kinds = {r["exhibit_id"]: MOD._exhibit_kind(MOD._load_meta(r["exhibit_id"])) for r in (doc, deck, plain)}
        self.assertEqual(list(kinds.values()), ["document", "slides", "freeform"])
        viewer = _http(doc["url"])[2]
        self.assertIn('class="kind kind-document"', viewer.split('id="title"')[0].rsplit("<header", 1)[1])
        # PDF export is offered for documents and slides only, by the kind of the version shown.
        self.assertIn('if (true) formats.push({ label: "PDF (.pdf)"', viewer)
        self.assertIn("if (false) formats.push", _http(plain["url"])[2])
        self.assertIn("if (true) formats.push", _http(deck["url"])[2])
        gallery = _http(doc["url"].split("/e/")[0] + "/")[2]
        self.assertEqual(gallery.count('class="kind kind-document"'), 3)  # card, list row, open tab
        self.assertIn('"kind": "freeform"', gallery)  # for search results

    def test_an_exhibit_never_changes_format(self):
        doc_page = (MOD._PRESET_DIR / "document.html").read_text(encoding="utf-8")
        deck_page = (MOD._PRESET_DIR / "slides.html").read_text(encoding="utf-8")
        doc = self.show(title="Report", html=doc_page)
        deck = self.show(title="Deck", html=deck_page)
        plain = self.show(title="Plain")
        self.assertEqual((doc["preset"], deck["preset"], plain["preset"]), ("document", "slides", "freeform"))
        meta = lambda r: MOD._load_meta(r["exhibit_id"])
        self.assertEqual(meta(doc)["versions"][0]["preset"], "document")  # recorded with the version
        # Versions saved before 0.2.3 stored freeform as "exhibit": they still read as freeform.
        self.assertEqual(MOD._exhibit_kind({"id": "x", "versions": [{"version": 1, "preset": "exhibit"}]}), "freeform")
        # An edit that keeps the format is fine.
        self.assertTrue(self.show(exhibit_id=doc["exhibit_id"], html=doc_page.replace("Q3 2026", "Q4"))["success"])
        # Any change of format is refused, in every direction, and nothing is saved.
        for exhibit, page in ((doc, "<h1>One long page</h1>"), (doc, deck_page), (deck, doc_page),
                              (deck, "<p>all slides in one page</p>"), (plain, doc_page), (plain, deck_page)):
            refused = self.call(action="show", exhibit_id=exhibit["exhibit_id"], html=page)
            self.assertEqual(refused["error_code"], "preset_locked", (exhibit["title"], page[:30]))
            self.assertIn("make a new exhibit in the format they want", refused["error"])
        self.assertEqual([len(meta(r)["versions"]) for r in (doc, deck, plain)], [2, 1, 1])
        # A page that claims a preset must have its structure.
        broken = doc_page.replace('<article class="sheet">', "<article>")
        self.assertEqual(self.call(action="show", exhibit_id=doc["exhibit_id"], html=broken)["error_code"],
                         "preset_structure")
        self.assertNotIn("convert_to", self.tool.card.input_params["properties"])  # no switching for now
        # The plugin's locked geometry for decks.
        raw = _http(deck["url"].replace("/e/", "/raw/") + "/1")[2]
        self.assertIn("@page{size:13.333in 7.5in!important", raw)
        self.assertIn(".slide{aspect-ratio:16/9!important}", raw)
        # Speaker notes were removed; any left in older decks stay hidden.
        self.assertIn("#notes-panel,.notes-panel,.slide .notes{display:none!important}", raw)

    def test_missing_page_error_says_what_the_call_had(self):
        # The agent kept insisting it sent html_file; the error now lists exactly what arrived.
        exhibit = self.show()
        missing = self.call(action="show", exhibit_id=exhibit["exhibit_id"], open=True)
        self.assertEqual(missing["error_code"], "missing_html")
        self.assertIn("Your call had only: action, exhibit_id, open.", missing["error"])
        self.assertIn("html_file", missing["error"])

    def test_slides_preset_has_no_controls_of_its_own_and_fits_its_text(self):
        page = (MOD._PRESET_DIR / "slides.html").read_text(encoding="utf-8")
        # Printing is in Export, and moving between slides is added by Exhibit, not written in the deck.
        self.assertNotIn('class="controls"', page)
        self.assertNotIn('class="edge', page)
        self.assertNotIn("print()", page)
        self.assertNotIn('bridge.set("slide"', page)
        self.assertIn("const fit = (slide)", page)
        self.assertIn(".slide.overfull > .in { overflow-y: auto; }", page)
        self.assertNotIn("40 words", page)

    def test_pages_and_slides_get_navigation_from_exhibit_not_the_page(self):
        deck = self.show(title="Deck", html=(MOD._PRESET_DIR / "slides.html").read_text(encoding="utf-8"))
        doc = self.show(title="Report", html=(MOD._PRESET_DIR / "document.html").read_text(encoding="utf-8"))
        plain = self.show(title="Plain")
        raw = lambda r, extra="": _http(r["url"].replace("/e/", "/raw/") + "/1" + extra)[2]
        # Decks get slide navigation (also in thumbnails, to show the first slide); documents get pages.
        self.assertIn("const standalone = parent === window, thumbnail = false", raw(deck))
        self.assertIn("thumbnail = true", raw(deck, "?thumb=1"))
        self.assertIn("const W = 816, H = 1056", raw(doc))
        for page in (raw(deck), raw(doc)):
            self.assertIn('channel: "exhibit-pages"', page)
        self.assertNotIn("exhibit-pages", raw(plain))
        # The scripts land in the real <head>, not in the preset's guidance comment (which mentions
        # <header>), so the saved-data bridge works in documents too.
        for page in (raw(deck), raw(doc)):
            comment_end = page.index("-->")
            self.assertGreater(page.index("window.exhibit = {"), comment_end)
        # The top bar has the page control for documents and slides only.
        self.assertIn('id="pager"', _http(deck["url"])[2])
        self.assertIn('aria-label="Current slide"', _http(deck["url"])[2])
        self.assertIn('aria-label="Current page"', _http(doc["url"])[2])
        self.assertNotIn('id="pager"', _http(plain["url"])[2])
        # An exported deck brings its own buttons; an exported document its pages.
        self.assertIn("exhibit-slide-nav", MOD._export_html(deck["exhibit_id"], None)[1])
        self.assertIn("exhibit-page-stage", MOD._export_html(doc["exhibit_id"], None)[1])
        self.assertNotIn("exhibit-slide-nav", MOD._export_html(plain["exhibit_id"], None)[1])

    @unittest.skipUnless(MOD._pdf_browser(), "needs Edge or Chrome")
    def test_pdf_of_a_document_is_letter_pages(self):
        doc = self.show(title="Report", html=(MOD._PRESET_DIR / "document.html").read_text(encoding="utf-8"))
        _, pdf = MOD._export_pdf(doc["exhibit_id"], None)
        self.assertEqual(set(re.findall(rb"/MediaBox\s*\[([^\]]*)\]", pdf)), {b"0 0 612 792"})

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

    def test_bulk_delete_removes_several_at_once(self):
        ids = [self.show(title=t)["exhibit_id"] for t in ("One", "Two", "Three")]
        keep = self.show(title="Keep")["exhibit_id"]
        names = [ids[0], "#" + ids[1].rsplit("-", 1)[1], ids[2], "gone-000000"]
        refused = self.call(action="delete", exhibit_ids=names)
        self.assertEqual(refused["error_code"], "confirmation_required")
        result = self.call(action="delete", exhibit_ids=json.dumps(names), confirm=True)  # a JSON string works too
        self.assertEqual(result["deleted"], ids)
        self.assertEqual(result["not_found"], ["gone-000000"])
        self.assertEqual([e["exhibit_id"] for e in self.call(action="list")["exhibits"]], [keep])
        self.assertEqual(self.call(action="delete", exhibit_ids=[], confirm=True)["error_code"], "invalid_input")
        self.assertIn("exhibit_ids", self.tool.card.input_params["properties"])

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

    def test_markdown_export_of_a_document(self):
        doc = self.show(title="Q3 report", html=(MOD._PRESET_DIR / "document.html").read_text(encoding="utf-8"))
        name, md, files = MOD._export_markdown(doc["exhibit_id"], None)
        self.assertEqual((name, files), ("Q3 report.md", {}))
        self.assertIn("# Support response times, Q3 2026", md)
        self.assertIn("## 1. Background", md)  # sections numbered like on the page
        self.assertIn("> [!note] Summary\n> - Median first response", md)  # Obsidian-style callouts
        self.assertIn("> [!warning] Risk", md)
        self.assertIn("| Channel | Tickets | Weekday | Weekend | Satisfaction |\n| --- | ---: |", md)
        self.assertIn("| **All channels** | **14,751** |", md)  # totals row
        self.assertIn("**Table 1.** Median hours", md)
        self.assertIn("**Figure 1.** Median hours", md)
        self.assertIn("![Median first response in hours, by month, 2025 and 2026](data:image/svg+xml;base64,", md)
        self.assertNotIn("Contents", md)  # the contents list is built by a script on the page
        # The embedded chart is a standalone SVG with the page's chart colors filled in.
        import base64
        svg = base64.b64decode(re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", md).group(1)).decode()
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn('viewBox="0 0 640 230"', svg)  # attribute case kept
        self.assertIn(".chart .bar { fill: #2b59c3; }", svg)
        # The .zip has the same text with the chart as a file.
        zip_name, data = MOD._export_markdown_zip(doc["exhibit_id"], None)
        import io
        import zipfile
        archive = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(zip_name, "Q3 report.zip")
        self.assertEqual(sorted(archive.namelist()), ["Q3 report.md", "images/figure-1.svg"])
        self.assertIn("](images/figure-1.svg)", archive.read("Q3 report.md").decode())
        # Served as downloads, and offered in the Export menu for documents only.
        base = doc["url"].split("/e/")[0]
        status, headers, body = _http(f"{base}/api/{doc['exhibit_id']}/export?format=md")
        self.assertEqual((status, headers["Content-Type"]), (200, "text/markdown; charset=utf-8"))
        self.assertIn("filename*=UTF-8''Q3%20report.md", headers["Content-Disposition"])
        with _NO_PROXY.open(urllib.request.Request(f"{base}/api/{doc['exhibit_id']}/export?format=md-zip"), timeout=10) as r:
            self.assertEqual(r.headers["Content-Type"], "application/zip")
        self.assertIn('label: "Markdown with images (.zip)"', _http(doc["url"])[2])
        self.assertIn("if (true) formats.push(\n    { label: \"Markdown (.md)\"", _http(doc["url"])[2])
        self.assertIn("if (false) formats.push(\n    { label: \"Markdown (.md)\"", _http(self.show(title="Plain")["url"])[2])

    def test_markdown_handles_memo_notes_and_brief_parts(self):
        page = """<!doctype html><html><head><meta name="exhibit-preset" content="document@2"></head><body>
<article class="sheet"><header class="top"><p class="eyebrow">Brief</p><h1>Launch</h1>
<ul class="meta"><li><b>For</b> Steering</li><li><b>Date</b> Nov</li></ul><span class="pill at-risk">At risk</span></header>
<section class="stats"><div class="stat"><div class="v">78%</div><div class="k">Done</div><div class="d up">+12 pts</div></div>
<div class="stat"><div class="v">3</div><div class="k">Blockers</div></div></section>
<dl class="memo-head"><dt>To</dt><dd>All staff</dd><dt>Subject</dt><dd>Rota</dd></dl>
<ul class="people"><li class="person">Ana</li><li class="person absent">Ben</li></ul>
<ul><li>Spent 40%<ul><li>Nested with <code>a|b</code> and a <a href="https://example.com">link</a></li></ul></li></ul>
<p class="decision">Keep it.</p>
<table class="actions"><tbody><tr data-id="a1"><td><input type="checkbox"></td><td>Publish</td><td>Ana</td><td>10 Nov</td></tr>
<tr data-id="a2"><td><input type="checkbox"></td><td>Book</td><td>Ben</td><td>12 Nov</td></tr></tbody></table>
<p>Costs $5 * 2 [not a link] and 50_000.</p></article></body></html>"""
        doc = self.show(title="Notes", html=page)
        MOD._exhibit_dir(doc["exhibit_id"]).joinpath("data.json").write_text('{"done": ["a1"]}', encoding="utf-8")
        md = MOD._export_markdown(doc["exhibit_id"], None)[1]
        for expected in ("*Brief*\n\n# Launch", "**For** Steering · **Date** Nov", "**At risk**",
                         "- **78%** Done (+12 pts)\n- **3** Blockers", "**To:** All staff  \n**Subject:** Rota",
                         "Ana · Ben (absent)", "- Spent 40%\n    - Nested with `a|b` and a [link](https://example.com)",
                         "**Decision:** Keep it.", "- [x] Publish (Ana, 10 Nov)\n- [ ] Book (Ben, 12 Nov)",
                         r"Costs $5 \* 2 \[not a link\] and 50\_000."):
            self.assertIn(expected, md)

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

    def test_chart_kit_is_added_only_to_pages_that_use_it(self):
        html = '<html><head></head><body><div id="c"></div><script>exhibit.chart("#c", {type: "line"})</script></body></html>'
        charted = self.show(title="Charted", html=html)
        plain = self.show(title="Plain")
        raw = lambda r, extra="": _http(r["url"].replace("/e/", "/raw/") + "/1" + extra)[2]
        page = raw(charted)
        self.assertIn("host.chart = ", page)
        self.assertIn(MOD._ECHARTS_URL, page)  # pinned ECharts, loaded from an allowed CDN
        self.assertTrue(MOD._ECHARTS_URL.startswith("https://cdn.jsdelivr.net/"))
        self.assertLess(page.index("window.exhibit = {"), page.index("host.chart = "))  # after the bridge
        self.assertNotIn("host.chart = ", raw(plain))
        # Thumbnails draw it calmly; exports bring it along.
        thumb = raw(charted, "?thumb=1")
        self.assertIn("host.chart = ", thumb)
        self.assertLess(thumb.index("window.__exhibitCalm = true"), thumb.index("host.chart = "))
        self.assertIn("host.chart = ", MOD._export_html(charted["exhibit_id"], None)[1])
        # Interactions are on by default: series focus, pie slice details, zoom for long series,
        # vector (SVG) drawing for the PDF, and the raw-options escape hatch.
        kit = MOD._CHART_KIT_SCRIPT
        for setting in ('focus: "series"', 'trigger: "item"', "p.percent", "dataZoom", 'renderer: "svg"',
                        "aria: { enabled: true }", "spec.options", "prefers-color-scheme"):
            self.assertIn(setting, kit)
        self.assertNotIn("</script", kit[len("<script>"):-len("</script>")])
        # Every chart's data can be edited, whatever its size (2026-11-10: the 100-value limit and table: false
        # went away), and only from the viewer's Edit data panel: the page has no editor of its own. The kit
        # reports its charts to the viewer and applies the edits, resets and PNG requests it sends back.
        self.assertNotIn("EDIT_LIMIT", kit)
        self.assertNotIn("spec.table", kit.replace("(spec.table is ignored)", ""))
        self.assertNotIn("exhibit-chart-data", kit)
        for setting in ("try { toTable(spec); editable = true; }", '"chart-data:"', "host.set(entry.key, { ...entry.table, base: entry.base })",
                        "host.remove(entry.key)", 'channel: "exhibit-charts"', '"exhibit-chart-edit"', '"exhibit-chart-reset"',
                        "notify(entry.spec.onChange, plainData(entry.table))",
                        "const inViewer = parent !== window && !window.__exhibitCalm;"):
            self.assertIn(setting, kit)

    def test_calling_the_chart_kit_again_on_an_element_replaces_its_chart(self):
        # Found 2026-11-10: a page that redrew its chart on every slider move went blank, with an
        # extra edit table each time. A repeat call now replaces the chart, drops slower earlier
        # calls, keeps an element's saved-data key, and edits come back only on the data they were made on.
        kit = MOD._CHART_KIT_SCRIPT
        for setting in ("live.set(el, ticket)", "if (!current()) return null;", "c.inst.dispose()",
                        "c.observer.disconnect()", "echarts.getInstanceByDom(el)", "numbers.set(el, ++chartCount)",
                        "edits.base === base"):
            self.assertIn(setting, kit)

    def test_chart_kit_runs_on_change_at_load_and_takes_colors_by_name(self):
        # Round 3: stat tiles filled only in onChange stayed empty ("—") until an edit, and
        # colors given by series name drew a black, dots-only line chart.
        kit = MOD._CHART_KIT_SCRIPT
        for setting in ("if (!nested) notify(spec.onChange, data());", "const nested = changing > 0;",
                        "base.color = colorsFor(spec, t, series.map((s) => s.name));",
                        "base.color = colorsFor(spec, t, data.map((d) => d.name));", "valid(c[n]) ? c[n]"):
            self.assertIn(setting, kit)
        self.assertNotIn("color: spec.colors ||", kit)

    def test_show_notes_a_table_of_its_own_next_to_the_chart_kit(self):
        chart = '<div id="c"></div><script>exhibit.chart("#c", {type: "line", x: [1], series: {A: [1]}%s})</script>'
        self.assertIn("Edit data button", self.show(title="T1", html=chart % "" + "<table><tr><td>1</td></tr></table>").get("note", ""))
        self.assertNotIn("note", self.show(title="T2", html=chart % ", table: false"))  # no longer turns the editor off
        self.assertNotIn("note", self.show(title="T3", html=chart % ", editable: false"))
        self.assertNotIn("note", self.show(title="T4", html="<table><tr><td>1</td></tr></table>"))  # no chart: fine
        self.assertIn("Fix it now, before you reply", MOD._OWN_TABLE_NOTE)  # round 4: later fixes never came

    def test_tool_description_keeps_what_the_rail_relies_on(self):
        # Shortened 2026-11-10; delete, references and gallery live in the parameter descriptions.
        text = MOD.ExhibitTool().card.description
        for phrase in ('skill_name "exhibit"', "call preset", "[USER_CHOSE_CHAT]", "html_file",
                       "send_file_to_user", "window.exhibit", "Skip it for short answers"):
            self.assertIn(phrase, text)
        self.assertLess(len(text.split()), 230)
        params = MOD.ExhibitTool().card.input_params["properties"]
        self.assertIn("the user confirms in a dialog", params["action"]["description"])
        self.assertIn("@exhibit(...)", params["exhibit_id"]["description"])
        self.assertIn("one dialog", params["exhibit_ids"]["description"])

    def test_charts_preset_is_drawn_from_its_data_block_and_checked(self):
        # Charts & Graphs (0.3.0): the agent fills in text and a JSON block; the plugin draws the charts.
        result = self.call(action="preset", name="charts")
        self.assertEqual(result["preset"], "charts")
        self.assertIn('id="exhibit-charts"', result["next"])
        self.assertEqual(self.call(action="preset", name="Charts & Graphs")["preset"], "charts")
        page = result["html"]
        shown = self.show(title="Sales charts", html=page)
        self.assertEqual(MOD._exhibit_kind(MOD._load_meta(shown["exhibit_id"])), "charts")
        raw = _http(shown["url"].replace("/e/", "/raw/") + "/1")[2]
        self.assertIn("host.chart = ", raw)  # the kit, though the page never calls exhibit.chart(
        self.assertIn('document.getElementById("exhibit-charts")', raw)
        self.assertLess(raw.index("host.chart = "), raw.index('document.getElementById("exhibit-charts")'))
        viewer = _http(shown["url"])[2]
        self.assertIn('class="kind kind-charts"', viewer)
        self.assertIn('label: "PDF (.pdf)"', viewer)  # PDF export, as for documents and slides
        self.assertNotIn("note", shown)  # its data block isn't "a table of its own"
        # A broken data block is refused, saying what's wrong; so is leaving the format.
        for broken, words in ((page.replace('"charts": [', '"chartz": [', 1), "has no charts"),
                              (page.replace('"type": "line"', '"type": "radar"', 1), "must be one of"),
                              (page.replace('"prefix": "$",', '"prefix": "$",,', 1), "isn't valid JSON")):
            failed = self.call(action="show", title="Broken", html=broken)
            self.assertEqual(failed.get("error_code"), "preset_structure")
            self.assertIn(words, failed["error"])
        locked = self.call(action="show", exhibit_id=shown["exhibit_id"], html="<p>plain</p>")
        self.assertEqual(locked.get("error_code"), "preset_locked")
        # Stat tiles (after round 5): declared in the block, drawn and recalculated by the plugin from
        # the chart's current data (onChange), and checked on show.
        self.assertIn('"stats": [', page)
        for setting in ('case "growth":', 'onChange: (data) => { latest[spec.id] = data; refresh(spec.id); }', '"exhibit-stats"'):
            self.assertIn(setting, MOD._CHARTS_SCRIPT)
        for broken, words in ((page.replace('"chart": "sales", "value": "sum"', '"chart": "nope", "value": "sum"', 1), "isn't in \"charts\""),
                              (page.replace('"value": "sum" }', '"value": "median" }', 1), "must be one of"),
                              (page.replace('"series": "North"', '"series": "South"', 1), "names series 'South'"),
                              (page.replace('"show": "both"', '"show": "all"', 1), "must be value, label or both")):
            failed = self.call(action="show", title="Bad stats", html=broken)
            self.assertEqual(failed.get("error_code"), "preset_structure", broken[:0] + words)
            self.assertIn(words, failed["error"])

    def test_viewer_has_the_edit_data_button_and_png_export(self):
        # Edit data lives in the viewer's top bar for every exhibit (shown once the page reports charts).
        viewer = _http(self.show(title="Any")["url"])[2]
        self.assertIn('id="data-btn"', viewer)
        self.assertIn('id="data-panel"', viewer)
        self.assertIn("window.exhibitDataCharts", viewer)
        # PNG is a picture of the whole page, for every exhibit (not of one chart): the page draws itself.
        self.assertIn('{ label: "PNG image (.png)", run: exportPng }', viewer)
        raw = _http(self.show(title="Png")["url"].replace("/e/", "/raw/") + "/1")[2]
        self.assertIn('m.channel !== "exhibit-snapshot"', raw)
        self.assertIn(MOD._HTML_TO_IMAGE_URL, raw)
        self.assertTrue(MOD._HTML_TO_IMAGE_URL.startswith("https://cdn.jsdelivr.net/"))
        self.assertNotIn("exhibit-snapshot", MOD._inject_bridge("<p>x</p>", thumbnail=True))
        # Edit data: values only. Labels and series names are text; a row the user adds gets a name field.
        self.assertIn('else first.appendChild(make("span", "dp-label", row.label));', viewer)
        self.assertIn('wrap.append(dot, make("span", "", name));', viewer)
        # Rows move by dragging a grip or with the arrow keys on it; the chart follows the new order.
        for setting in ('const moveRow = (from, to, focusGrip) => {', 'grip.addEventListener("keydown"', 'tr.addEventListener("drop"'):
            self.assertIn(setting, viewer)
        self.assertIn('"exhibit-chart-edit"', viewer)
        self.assertIn('"exhibit-chart-reset"', viewer)

    def test_new_exhibit_page_offers_formats_and_a_conversation(self):
        # New exhibit opens a page: a box to ask WorkSwarm and the four formats with previews.
        # Neither is connected (a plugin can't start a chat); both say so.
        shown = self.show(title="Any")
        base = shown["url"].split("/e/")[0] + "/"
        viewer = _http(shown["url"])[2]
        self.assertIn(f'href="{base.split("127.0.0.1:")[1].split("/", 1)[1]}new"'.replace('href="', 'href="/'), viewer)
        status, _, page = _http(base + "new")
        self.assertEqual(status, 200)
        self.assertIn('class="new-btn on"', page)
        for name in ("Document", "Slides", "Charts &amp; Graphs", "Freeform"):
            self.assertIn(name, page)
        self.assertEqual(page.count('class="card format-card"'), 4)
        self.assertIn('id="ask-text"', page)
        self.assertIn("Not connected yet", page)
        for kind in ("document", "slides", "charts"):
            status, _, preview = _http(base + "preset/" + kind)
            self.assertEqual(status, 200)
            self.assertIn("window.__exhibitCalm = true", preview)  # drawn like a thumbnail
        self.assertEqual(_http(base + "preset/freeform")[0], 404)

    def test_edit_data_panel_resizes_and_has_no_edited_dot(self):
        viewer = _http(self.show(title="Any")["url"])[2]
        self.assertIn('id="dp-resize" role="separator"', viewer)
        self.assertIn('const PANEL_WIDTH_KEY = "exhibit-data-panel-width";', viewer)
        self.assertIn("Math.max(320, Math.min(w, room - 320))", viewer)
        self.assertNotIn("data-dot", viewer)

    def test_a_made_up_id_says_to_leave_it_out_for_a_new_exhibit(self):
        result = self.call(action="show", exhibit_id="bakeoff-sales-echarts", title="Sales", html="<p>x</p>")
        self.assertFalse(result.get("success"))
        self.assertIn("leave exhibit_id out", json.dumps(result))

    def test_skill_makes_exhibits_interactive_and_uses_the_chart_kit(self):
        skill = (TOOL_FILE.parents[1] / "skills" / "exhibit" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Make it interactive, whether or not the user asked", skill)
        self.assertIn("#### Interactive by default", skill)
        self.assertIn("exhibit.chart(", skill)
        self.assertNotIn("100 values", skill)  # every chart has the Edit data table
        self.assertIn("every chart's data can be edited from the **Edit data** button in the exhibit's top bar", skill)
        self.assertIn('**Charts & Graphs** (`"preset": "charts"`)', skill)
        self.assertNotIn("chart.js@", skill)  # the kit replaced the hand-written Chart.js advice
        # Phase 4: the agent hand-wrote ECharts, so the skill says not to, and names onChange for linked parts.
        self.assertIn("Don't load Chart.js, ECharts or any other chart library for these", skill)
        self.assertNotIn("ECharts itself is fine", skill)
        self.assertIn("onChange(data)", skill)
        # Round 2: pages that saved the chart's data themselves broke Reset, and copies of the data went stale.
        self.assertIn("never a saved copy, and don't save the chart's data with `exhibit.set`", skill)
        self.assertIn("call `exhibit.chart` again on the same element", skill)
        # Round 3: read-only copies of chart data, and `table: false` used to hide the editor.
        self.assertIn("Never add a read-only table that repeats a chart's data", skill)
        self.assertNotIn("`table: false` hides the table", skill)
        self.assertIn("It runs once when the chart first draws", skill)
        # Skill trim (2026-11-10): preset before gathering data, scripted counts, which chart for what.
        self.assertIn("before you gather data or read files for it", skill)
        self.assertIn("count them with a script, not by reading", skill)
        self.assertIn("| Change over time |", skill)
        self.assertNotIn("Updates from elsewhere", skill)
        self.assertLess(len(skill.splitlines()), 220)  # 245 before the trim
        self.assertIn("never from the original count or positions", skill)

    def test_freeform_points_to_the_chart_kit_and_show_notes_own_chart_libraries(self):
        freeform = self.call(action="preset", name="freeform")["next"]
        self.assertIn("exhibit.chart(element, spec)", freeform)
        self.assertIn("pass it the original data and use onChange", freeform)
        own = ('<html><head><script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>'
               "</head><body><div id=c></div></body></html>")
        noted = self.show(title="Own chart", html=own)
        self.assertIn("exhibit.chart(element, spec)", noted.get("note", ""))
        kit = '<div id="c"></div><script>exhibit.chart("#c", {type: "line", x: [1], series: {A: [1]}})</script>'
        self.assertNotIn("note", self.show(title="Kit chart", html=kit))
        self.assertNotIn("note", self.show(title="No chart"))
        # Round 5: a line chart drawn with d3 had no Edit data; d3 counts, and the note asks for the fix now.
        d3 = self.show(title="D3 chart", html='<html><head><script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script></head><body></body></html>')
        self.assertIn("fix it now, before you reply", d3.get("note", ""))
        other = '<html><head><script src="https://cdn.jsdelivr.net/npm/dayjs@1.11.13/dayjs.min.js"></script></head><body></body></html>'
        self.assertNotIn("note", self.show(title="Dates", html=other))

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
        self.assertIn("if (false) formats.push", viewer)  # no PDF for an exhibit made without a preset
        # The page prints itself when the viewer asks.
        raw = _http(exhibit["url"].replace("/e/", "/raw/") + "/1")[2]
        self.assertIn('m.channel === "exhibit-print"', raw)

    @unittest.skipUnless(MOD._pdf_browser(), "needs Edge or Chrome")
    def test_pdf_export_prints_slides_at_slide_size(self):
        deck = self.show(title="Deck: Q3 / review", html=(MOD._PRESET_DIR / "slides.html").read_text(encoding="utf-8"))
        base = deck["url"].split("/e/")[0]
        url = f"{base}/api/{deck['exhibit_id']}/export?format=pdf"
        with _NO_PROXY.open(urllib.request.Request(url), timeout=60) as r:
            self.assertEqual(r.headers["Content-Type"], "application/pdf")
            self.assertIn("filename*=UTF-8''Deck%20Q3%20review.pdf", r.headers["Content-Disposition"])
            pdf = r.read()
        self.assertTrue(pdf.startswith(b"%PDF"))
        # Eight sample slides, each one 13.333 x 7.5 in page.
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), 8)
        self.assertEqual(set(re.findall(rb"/MediaBox\s*\[([^\]]*)\]", pdf)), {b"0 0 960 540"})

    def test_pdf_export_without_a_browser_says_so(self):
        exhibit = self.show()
        base = exhibit["url"].split("/e/")[0]
        real = MOD._pdf_browser
        MOD._pdf_browser = lambda: None
        try:
            status, _, body = _http(f"{base}/api/{exhibit['exhibit_id']}/export?format=pdf")
        finally:
            MOD._pdf_browser = real
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error_code"], "pdf_unavailable")
        viewer = _http(exhibit["url"])[2]
        self.assertIn('frame.contentWindow.postMessage({ channel: "exhibit-print" }', viewer)  # the fallback

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
        self.assertNotIn('id="exhibit-more"', viewer)  # the exhibit bar has no ⋯ menu
        self.assertNotIn('label: "Rename"', viewer)
        # Export is an icon button like the others, with no label or arrow.
        self.assertIn('<button class="bar-icon" id="export"', viewer)
        self.assertNotIn("<span>Export</span>", viewer)

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
