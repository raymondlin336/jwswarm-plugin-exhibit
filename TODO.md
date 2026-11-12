# Exhibit to-do

Last updated 2026-11-10.

## Released

- [x] 0.2.1 tested in WorkSwarm, committed, tagged `v0.2.1` and pushed
- [x] 0.2.2 committed, tagged `v0.2.2` and pushed (2026-11-09)
- [x] Untrack the stray framework logs: `git rm -r --cached logs` (already in .gitignore), done with 0.2.2

## Evidence so far

- Same prompt ("5 slide presentation on this repo"), same model (deepseek-v4-flash), repo reading excluded:
  exhibit deck 66 s / 3 tool calls vs PowerPoint (`ppt-creation`) 6 min 47 s / 54 tool calls.
  Most PowerPoint time went to specs, QA scripts and 7 build-check-fix rounds, not slide content.

## Pinned

### 0.3.0: interactive charts that feel like Claude's artifacts
Today the agent hand-writes every chart, usually Chart.js with default tooltips, so data exhibits feel flat. For example, hovering a line doesn't highlight it, and pie slices give no details. Claude's artifacts get this from a library with good defaults (Recharts), not from the model. Plan:
- [ ] Phase 1: bake-off of Chart.js vs Apache ECharts vs Vega-Lite, using what deepseek-v4-flash produces with each (`notes/chart-bakeoff.md`)
  - [x] Objective checks: reliability, correctness, robustness, cost (2026-11-10, `eval/chart_check.py`). ECharts matched Chart.js on reliability and gave clearly more interaction; Vega-Lite was weakest. Recommendation: ECharts.
  - [ ] Subjective judging, method 1: blind pairwise votes by the user and coworkers (WebDev Arena style)
  - [ ] Subjective judging, method 2: a vision-model judge with a checklist per prompt and scripted screenshots (ArtifactsBench style), calibrated against method 1
  - Details for both methods are in `notes/chart-bakeoff.md`, under "Judging the subjective part"
- [ ] Small tool fix found in the bake-off: when the agent passes a made-up `exhibit_id` for a new exhibit, make `exhibit_not_found` say to leave `exhibit_id` out for a new exhibit
- [x] Phase 2: `exhibit.chart(el, spec)` on ECharts 5.5.1, added by the plugin to pages that call it, with interactions on by default (2026-11-10):
  - series focus on hover, tooltips with every series, legend toggles;
  - pie slice details (value, %), zooming past 24 points, transitions (off in thumbnails);
  - theme colors (page accent first), light/dark redraw, resizing;
  - SVG drawing, so PDFs get vector charts;
  - `spec.options` as the escape hatch for raw ECharts options;
  - a data table if ECharts can't load.
  - an editable data table under every chart (edit, add, remove, reset; saved in the exhibit's data), added on 2026-11-10 at the user's request. First only up to 100 values; since 2026-11-10 on every chart, with no way to turn it off.
  Checked with `eval/chart_samples.py` (8 samples), `eval/chart_check.py` and `eval/chart_hover.py`; results in `notes/chart-bakeoff.md`.
- [ ] Phase 3: skill guidance. Started 2026-11-10:
  - [x] "Interactive by default": every exhibit is interactive whether or not the user asked (editable data, tables only when wanted and then editable, inputs for assumptions);
  - [x] a "Charts: `exhibit.chart`" section with an example, replacing the Chart.js advice;
  - [ ] still to do: an example per chart type, and the rest of the plan below.
  Original plan: a "Data and charts" section in the skill, with an example per chart type and an interaction checklist (hover detail, sortable tables, linked highlights, visible filters). Adapt ideas from LibreChat's open-source artifact instructions (MIT, credited). Move the document preset's SVG chart to `exhibit.chart`.
- [ ] Phase 4: rerun the bake-off prompts and the "Tasks Completed Per Day" dashboard with the kit; add them to the test prompts
  - [x] Round 1 (2026-11-10, dev build): only 1 of 9 runs used `exhibit.chart`; the others hand-wrote ECharts. Data editing was missing or poor in places. Fixed in dev2 (agent pointed to the kit, redesigned editor, `onChange`).
  - [x] Round 2 (dev2): 9 of 9 used `exhibit.chart`, rubric 0.89. New issues: pages that save the chart's data themselves break Reset (2 of 9); duplicate or unlinked parts (2 of 9).
  - [x] Skill fix for those two: the kit saves edits, so always pass the original data and use `onChange` only to update the page; don't repeat the chart's data in another table (0.3.0 build).
  - [x] Kit fix (0.3.0 build): the tracker dashboard went blank after a slider move because it called `exhibit.chart` again on the same element. Repeat calls now replace the chart, and saved edits stay with the data they were made on.
  - [x] Round 3 (12 runs): 12 of 12 used the kit, rubric 0.79. Read-only copies of the chart's data in 6 of 12 (never wanted, says the user), empty stat tiles in 2 (`onChange` only ran at load after edits), dots-only lines in 1 (`colors` by name). Fixed in the kit, skill and `show` note.
  - [x] Round 4 (10 runs): rubric 0.95, nothing broken after controls, edits, deleted rows and Reset. Read-only tables in 2 of 10 final pages (3 added, 1 removed after the `show` note).
  - [x] The `show` note about an extra table now asks for the fix right away, before replying (the user's call, 2026-11-10). It also says to reread the file before editing it, after Sales 10's failed edit.
  - [ ] Check it in the next round: tables left in final pages, and how many extra calls the fixes cost
  - [x] Skill trimmed and aligned (2026-11-10): shorter description, Errors section cut to two entries, one way to change a chart's data, an `onChange` example that fills stat tiles, export formats, `preset` before gathering data, scripted counts, a which-chart table. About 20% fewer words. The tool description was shortened the same day (about 390 words to 200).
  - [x] "Edit data" on every chart: the 100-value limit and `table: false` are gone. A 365-row table opens in about 40 ms.
  - [x] Charts & Graphs preset (2026-11-10, the user's call, part of 0.3.0): a fourth option in the picker. The agent fills in text and a JSON block of chart specs; the plugin draws the charts. PDF, HTML and PNG export.
  - [x] Edit data moved into the viewer's top bar (2026-11-10): one panel for every chart on the page, in every exhibit; the only way to edit a chart's data. The in-page editor is gone. PNG export of each chart from the Export menu.
  - [x] Round 5 (12 runs, 3 as Charts & Graphs): rubric 0.85. Store 6 drew its chart with d3 (no Edit data): d3 now counts for the `show` note, which asks for the fix now. Labels are now read-only in Edit data, and PNG export is the whole page.
  - [x] Charts & Graphs stat tiles that follow edits (2026-11-10, the user's call): declared in the data block, recalculated by the plugin from the chart's current data; checked on show. The preset now rules out charts worked out from another chart, and numbers from the data in the text.
  - [x] Edit data rows can be moved by dragging a grip or with the arrow keys, old rows and new (2026-11-10, the user's call, instead of sorting added rows automatically). The picker's descriptions are the user's wording.
  - [ ] Round 6: prompts E to L (new kinds of chart and data, in `notes/chart-bakeoff.md`), each once as Freeform and once as Charts & Graphs; watch the chart type picked, stats, derived charts, nulls, negatives, d3 and read-only tables
  - [ ] Check in WorkSwarm that the picker shows all five options (four kinds and "Answer in chat") well
  - [x] No "Custom" in the picker or the delete dialog (2026-11-10, the user's call). WorkSwarm's `_build_multi_questions` (in `jiuwenswarm.agents.harness.common.rails.interrupt.interrupt_helpers`) appends "Other" to every question with options, with no setting; the rail wraps it and drops "Other" from our two dialogs only. Check it in WorkSwarm. For the core proposal: a per-question flag to leave out the custom answer.

### More built-in kits, after the chart kit (version to decide)
Same approach as `exhibit.chart`: the plugin supplies the tool with good defaults and the skill points the agent to it, so quality doesn't depend on the model remembering. This is how Claude's artifacts get their polish (React with shadcn/ui, Tailwind, lucide, Recharts), adapted to plain HTML. Start after phase 4 shows how well the agent picks up `exhibit.chart`.
- [x] Diagram kit (0.4.0, 2026-11-11): `<pre class="exhibit-diagram">` with Mermaid 12.3.0 text, added only to pages that have one. Decisions and the full Mermaid map in `notes/mermaid-map.md`.
  - Done: theme colors light and dark (redrawn on a switch), the neo look with ELK (hidden `diagram_look` setting for classic), fit to width, `<br>` labels, error message in place, `show` notes (own Mermaid, Mermaid charts, unknown type), skill section, PDF and PNG checked in headless Edge.
  - Done, same day: interaction (hover focus, click details, zoom, step-through listed or automatic, `exhibit.diagram` hook), and the skill asks for a step-through whenever a diagram shows an order.
  - [x] Hover, click and steps for every diagram type, with automatic steps for Gantt, journey, gitGraph and event modeling too (2026-11-11)
  - [ ] Baseline and kit rounds: prompts M to T in the vault note "Exhibit diagram prompts"
    - Round 1 (2026-11-11) ran the 14:50 build (`727c828d8a4e`), not the interactive kit, so it doesn't count as the kit round. From it: timelines step per event, `show` notes flowcharts and state diagrams with no `%% step` lines, and the skill tells agents to hand-build visuals that move with real state (explainers, like the BFS/DFS page).
    - Round 2 (2026-11-11, build `8a39a8a81616`): 5 of 8 at 1. Order states failed (quoted state names), the timeline chat stopped after `preset` with no page. Decision (the user's call): no more per-type syntax patches. Instead `show` opens the saved page in headless Edge (about 1 s) and returns a `note` with Mermaid's exact error, empty diagrams and script/console errors, plus `page_text` (what the user will see). The round-1 `;` and `:` rewrites were removed; the source block is `display:none`; any step line counts as a caption on ordered types.
    - [x] Rerun M to T on the rebuilt `exhibit-0.4.0.zip`, after reinstalling it in WorkSwarm, and screenshot every page
    - Round 3 (2026-11-11 17:15, build `6cf7299d3b23`): 7 of 8 at 1, traffic 0.75. All 8 drew and every step-through worked. No `show` returned a note. Traffic's first version had 1,300 visitors and "undefined" labels; the agent read `page_text`, fixed it and showed v2 without being told. Open, measured at 1280 px wide:
      - [x] Diagram text too small to read: order states 8.4 px, timeline 7.5 px, login 10.9 px (refund, schema, mind map 14 px). Wide diagrams were shrunk to fit the column. Fixed both ways (build `b685eae2a94a`): the kit starts a wide diagram at the size where its labels are 11 px and scrolls sideways (Zoom out still fits it; print fits), and the render check reports any drawing, kit or hand-made SVG, whose text is under 10 px.
      - [x] Step focus can be off-screen: on the slide deck's tall flowchart, step 3 highlights Web App above the visible area while the controls stay below. Fixed: Back, Next, Play and `goTo` scroll the lit parts into view (inside a scrolling diagram, then the page or slide), with the controls too when both fit.
      - [ ] Rerun M to T on build `b685eae2a94a` in WorkSwarm and screenshot every page
      - [ ] Not caught by any check: traffic's per-source tiles wrap badly; the refund flowchart sits right of the column; several pages repeat "use the buttons above" under the controls.
  - [ ] Check in WorkSwarm
- [x] Local copy of the libraries (0.4.0): ECharts, Mermaid and html-to-image downloaded on first use into `~/.exhibit/lib`, checked by SHA-256, served by the plugin, CDN as the fallback. Sandboxed pages never reuse the browser cache (measured: ECharts re-downloaded on every load in 0.3.0).
  - [ ] Check in WorkSwarm, and in Chrome and Firefox (only headless Edge so far)
- [x] Page rules and form guidance (0.4.0, 2026-11-12), after the JWMemory capstone (WorkSwarm vs Claude on the same notes) and the Generative UI paper (`notes/generative-ui-paper.md`):
  - Skill: "Interactive by default" and its table-of-contents line replaced by "Choosing the form" (a one-line plan per section; text by default, charts for numbers, a widget only when the reader has an input to change; no page navigation, no emojis; three short examples). `--card` dropped from the starter CSS.
  - `show` refuses with `page_rules` and saves nothing: read-only tables of numbers and page-built navigation (freeform only; documents keep printed tables and the preset's contents), emojis in headings, buttons and labels (every format). Prose in a box or card gets a note.
  - Checked on the capstone pages: WorkSwarm's two are refused (tables, top bar, emojis), and so is Claude's (side menu, two tables).
  - Capstone rerun on build `fcc83d378b24` (2026-11-12, the user): emojis and page navigation gone, tables no longer overused, no unneeded interaction, better organised. Open: few chart types, and no horizontal bars even for long labels.
  - [x] Chart kit, same day: 11 more types (dot, histogram, boxplot, heatmap, calendar, waterfall, funnel, treemap, sunburst, sankey, radar), picked by the reader's question (FT Visual Vocabulary); each fits one of four Edit data shapes (grid, slices, pairs, values). Bars lie down by themselves for long or many labels; values below zero take a second colour. The skill's 4-row chooser became a 12-row one. All 17 types drawn in headless Edge, light, dark and 390 px, no errors.
    - [ ] Edit data on the new types checked in the viewer (only the table shapes were tested, through the kit)
  - Capstone rerun on build `9181aa828c07` (2026-11-12): fixing the refused nav, the agent ran `sed -i '168,200d'` "to test" and saved a page missing 33 lines; the page it meant (rebuilt from its session) had 9 of 9 bar charts, every chart under a heading repeating its title, a half-width bar chart hiding labels, and three wrong numbers (model reasoning, not checked).
  - [x] Same day: `show` remembers a refused page's text (by id, file and title) and notes prose missing from the next attempt; the render check notes headings that repeat a chart's title; a bar label fits only with 24 px to spare. Replayed on the capstone attempts: both notes fire where they should.
  - Tried and reverted the same day (the user's call): notes on pages whose charts are 80% one type, and on paragraphs reciting a chart's numbers. On the next run the agent did switch chart types, but the charts it changed came out poorly.
  - [ ] Rerun the capstone, M to T and W1 to W10 in WorkSwarm on the new build; measure read-only tables, boxed prose, navigation, emojis, widgets per mechanism and unsupported conclusions; screenshot every page
- [x] Page parts (0.4.0, 2026-11-12): 13 `ex-` parts designed with the user in `notes/page-parts-preview.html` (square corners, one borderless surface tint, WorkSwarm orange `#ff8821` as the accent with `#b85500` for small text, yellow warnings, hexagon steps after the WorkSwarm mark). Styles added only to pages that use a part, as plain class rules at the top of `<head>` (a cascade layer was tried first, but one `* { padding:0 }` reset flattened the parts); page CSS for a part still wins. The render check doesn't count them as text in a box, and notes page CSS that restyles them and self-numbered reference items. Starter CSS accent is now orange.
  - [ ] Document and slides presets still use their own blue accent and amber warning; decide whether they move to orange and yellow
  - [ ] Try in WorkSwarm: does the agent pick parts for their jobs, and keep paragraphs the default? (End-game runs of 2026-11-12: it still builds its own cards for planet profiles, team roles and milestones.)
- [x] Forms guidance (0.4.0, 2026-11-12): "Choosing the form" names drawn pictures (SVG, labelled, scale stated) and Gantt/timeline schedules, gives what the request asks to see its own section, and has varied examples (water cycle, kitchen renovation, coffee makers) outside the test topics. Charts take `better` and the render check notes unnamed value axes and lone score bars. End-game prompts in the vault note "Exhibit end-game prompts".
  - First run on build 15:27: the solar system drew its planets and an age slider, the launch plan had a Gantt chart and a saved checklist, nutrition had the protein-vs-calories scatter.
  - [ ] Gantt styling in the diagram kit: gridlines cross the task labels, bars read as empty outlines, and the red "today" line shows at the edge when today is outside the plan (hide it then; accent-filled bars; gridlines behind labels)
  - [ ] Render check: overlapping labels in the page's own SVGs (the solar system's inner planets: "MercuryVenusEarth", distances run together); measure text boxes like the small-text check and note collisions
  - [ ] Skill: `better` only where one direction is clearly better (scores, accuracy, savings: higher; cost, time, errors: lower); none for neutral measures like size, distance or counts (the solar system marked all four "higher is better")
  - [ ] Run E1–E6 two or three times each, and S1–S3, on the 0.4.0 release; record the range of forms per page
  - [ ] Try a round on DeepSeek Pro to see how much of what's left is the model (layout of improvised pictures, home-made cards)
- [ ] UI kit: a small set of ready-made parts for plain HTML, written into the plugin (no CDN, works offline, about 15 to 25 KB), with class names prefixed `ex-` and following the page's color variables.
  - Start with:
    - `exhibit.table(el, rows)`: sortable columns, search past about 15 rows, number formatting, and optional editable cells saved with the exhibit;
    - stat tiles: a headline number with a label and a change;
    - filter buttons that filter tables and charts on the page together.
  - Then: tabs, sections that open and close, inputs and sliders that recalculate linked numbers and charts, cards, callouts, and a small inline icon set (for example a lucide subset, MIT).
  - It must fit inside the document and slides presets without restyling them.
  - Skill guidance with short examples. Measure with the test prompts before and after.
- Not planned: React, Tailwind or shadcn themselves. Compiling JSX in the page is heavier and gives a fast model more ways to fail.

### Exhibit formats and routing
- [ ] A diverse set of exhibit presets, each a ready-made renderer the agent fills with content instead of writing the whole page:
  chart / dashboard, document / report, slides, table / data, calculator / tool, tracker / checklist, mockup / prototype, diagram; free-form HTML stays as the fallback. Document and slides are done (0.2.2); Charts & Graphs (0.3.0)
- [ ] Routing: pick the preset from the request's intent, then load only that preset's instructions (today the user always picks)
- [x] Start with one preset and compare it with hand-written exhibits: document and slides built in 0.2.2
- [ ] Compare preset exhibits with free-form ones on the same prompts (time, tool calls, rubric score)
- [ ] Switching an exhibit's preset (document ↔ slides ↔ free-form). For now an exhibit's format is locked: the tool refuses a version in another format (`preset_locked`), and the agent offers a new exhibit instead. A first version was built and removed on 2026-11-09. What we learned:
  - Out of a preset should be done by the tool, not the agent. Given only a `convert_to` flag, the agent (deepseek-v4-flash) expected the tool to convert and sent no page; when it did write the page, it repeatedly dropped `html_file`. The tool can do this reliably: a document → one continuous page (drop the preset tag); a deck → all slides stacked in a scrolling page (drop the tag, add a stacking style).
  - Into a preset needs the content moved into the preset's structure (the agent fetches the preset page, fills it, saves it). The tool should accept it only if the page really has that structure.
  - Leaving a preset loses the page control and PDF/Markdown export, so the user should confirm in a dialog. Remember the answer for the turn, so retries after a failed save don't ask again.
  - Each version records its preset (already in place), so older versions keep their own controls and exports.
- [ ] Rethink the formats around freeform (the user's idea, 2026-11-12): the document and Charts & Graphs presets, maybe all presets, may be deprecated. Instead, everything is written as freeform, and a separate module takes the page's components (sections, charts, diagrams, widgets, parts), measures them, and lays them into "molds" with the dimensions of document pages or slides, for export (PDF, deck, document) without locking the exhibit's format. Would also replace preset switching above.

### Export to traditional file formats
- [x] Download from the exhibit bar (Export menu), 0.2.2
- [ ] Download from the gallery's ⋯ menu too
- [x] Self-contained HTML, with saved data baked in, 0.2.2
- [x] PDF for documents and slides, printed by a hidden Edge or Chrome, 0.2.2
- [x] Markdown for documents (.md with embedded charts, or .zip with images/), 2026-11-09
- [ ] Per-preset formats: Word for documents, PowerPoint for slides, Excel / CSV for tables, SVG for charts, PNG / SVG for diagrams (PNG of charts done in 0.3.0)
- [ ] Per-item rail (the user's idea, 2026-11-12): a small rail on the right of each chart, diagram and widget with Export (PNG, SVG, data), Copy, and Edit (Edit data for a chart, the source for a diagram). The buttons move from the exhibit's top bar, where they depend on the whole page's preset, to the item they act on.

### Referring to and quoting exhibits
- [x] Refer to an exhibit in chat (`@exhibit(Name #code)`, Copy reference) so the agent knows which one you mean and can read it, 0.2.2
- [x] Quote part of an exhibit into the conversation (select text, Quote), 0.2.2
- [x] Link each exhibit to the chat that made it (session id and history path), 0.2.2

## Next

- [ ] Let the agent write an exhibit's saved data (refresh numbers without a new version)
- [ ] Look into "Continue in chat" from an exhibit, which also hooks up the New exhibit page (built 2026-11-10: an ask box and the four formats with previews, not connected; needs WorkSwarm to let a plugin start a chat)
- [ ] An exhibit button that sends a message to the agent (may wait for the core feature)
- [ ] Measuring: about ten test prompts scored with the 1 / 0.75 / 0.5 / 0 rubric, run before and after changes

## Exhibit quality

- [ ] Real photos in exhibits. Today exhibits can only show images embedded in the page (`img-src data: blob:`), and the skill says images must be inline. So the agent hand-draws SVG, and its pictures come out poor: the flat-tire how-to on 2026-11-09 had 8 rough SVG drawings and no photos.
  - Tool-side embedding: `show` takes `images` (name → https URL), and the HTML uses `<img src="exhibit-image:name">`. The tool downloads each image (https only, size limit per image) and inlines it as a `data:` URL before saving. The page's CSP stays as strict as it is.
  - Skill guidance: use real photos for how-tos and physical things, preferring freely licensed sources (e.g. Wikimedia Commons) with a credit in the caption. Keep SVG for diagrams and charts.
  - Raise the page size limit to allow for embedded photos (2 MB now).
  - Finding the photo stays with the agent (`fetch_webpage`, search); the plugin only embeds it safely.
- [ ] A built-in look: theme variables and Chart.js defaults injected by the tool, charts that redraw when the theme changes
- [ ] Self-made visuals follow the style guide (2026-11-12): the agent's own SVGs, drawings and widgets use the page's font, readable sizes, the theme colours (accent, muted, line) and work in light and dark, like the kits do. Candidates: a small style block for the agent's SVG (font, text fill, stroke), skill lines, and render-check notes for text that's hard to see (low contrast, too small) in the page's own drawings.
- [ ] Speed (2026-11-12):
  - [ ] The Exhibits Gallery is laggy (many live thumbnails?); measure what's slow first
  - [ ] Some interactive elements flash repeatedly while a value changes (sliders, inputs) instead of updating smoothly: likely whole charts or sections redrawn on every input event; find whether it's the kit (`exhibit.chart` called again per input) or the agent's code, then update in place or throttle
- [ ] Test on a stronger model (2026-11-12): run the end-game prompts (E1–E6, S1–S3) and the capstone on DeepSeek Pro or similar, to separate what's left that's the model (layout of improvised pictures, home-made cards, reasoning errors) from what's Exhibit's
- [ ] Concrete design rules in the skill (lead with the answer, summarize before plotting, show each fact once)
- [ ] In-app preview: a script-free snapshot in WorkSwarm's artifact panel with an "Open exhibit" link

## Small, any time

- [x] New screenshots for the README (`docs/*.webp`, 2026-11-09); the old `docs/demo.png` is no longer used
- [ ] GitHub releases with the zips attached
- [ ] Check the agent reliably fills in `summary` and `chat_alternative` (it did in the last deck run)
- [x] The agent wrote the full HTML before the user was asked "Exhibit or answer in chat?": fixed in 0.2.2, the user now picks the preset (or chat) before anything is written

## Set aside for now

- Chinese labels on the Exhibits pages
- Reporting platform issues to the WorkSwarm team, and the core proposal (exhibits in the artifact panel, MCP Apps)
- Until Exhibit is a core feature: channels beyond the desktop and remote access, patch edits, lifecycle and scale, the remaining security gaps
