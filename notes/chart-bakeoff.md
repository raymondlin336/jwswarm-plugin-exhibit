# Chart library bake-off (0.3.0, phases 1 and 2)

Goal: pick the library for the plugin's built-in chart kit (`exhibit.chart`) by seeing what deepseek-v4-flash actually produces with each one. The candidates are Chart.js (what the agent uses today), Apache ECharts and Vega-Lite.

## How to run it

- Run each prompt below in a **new WorkSwarm chat**, with deepseek-v4-flash.
- When asked what kind of exhibit, pick **Freeform**. In the 0.2.2 build used for this test, that option is called "No preset".
- Use `plugin/dist/exhibit-0.2.2.zip`, the released 0.2.2 build. Nothing in 0.2.3 affects charts.
- Don't add anything to the prompt, and don't ask for fixes afterwards. If the first exhibit is broken, that's a result.
- The titles start with "Bake-off", so the exhibits are easy to find afterwards.

The prompts are identical except for the library name. They ask for an interactive chart without saying which interactions, so the result shows what the model does with each library on its own.

### Prompt A: multi-line trend

Run three times, replacing LIBRARY with `Chart.js`, then `Apache ECharts`, then `Vega-Lite`:

```
Make an exhibit titled "Bake-off: Sales trend (LIBRARY)" with an interactive line chart of monthly sales by region for 2025. Use LIBRARY for the chart. Data (thousands of dollars), Jan to Dec:
North: 42, 45, 48, 51, 55, 60, 63, 61, 58, 62, 68, 74
South: 38, 37, 41, 44, 43, 47, 52, 55, 53, 50, 54, 59
East: 25, 29, 33, 31, 36, 40, 39, 44, 48, 51, 49, 55
West: 50, 48, 46, 47, 45, 44, 46, 49, 52, 56, 60, 63
```

### Prompt B: breakdown

Run three times, the same way:

```
Make an exhibit titled "Bake-off: Budget breakdown (LIBRARY)" with an interactive pie chart of our 2026 operating budget by category. Use LIBRARY for the chart. Data (dollars): Salaries 412000, Rent 96000, Software 58000, Marketing 74000, Travel 31000, Equipment 27000, Training 18000, Other 12000.
```

## Scoring

Phase 1 measures how reliably the model gets a correct, working chart out of each library. It doesn't measure specific interactions: those are design targets for phase 2, not the yardstick here. Every check below is objective, and most are measured automatically in headless Edge.

**Headline:** the 1 / 0.75 / 0.5 / 0 rubric, where 0.75 means it worked, but only after retries.

**Reliability** (from the chat history and the page):

| Check | How |
|---|---|
| Worked on the first `show` | Yes or no |
| Failed tool calls | Count |
| Script errors on load | Console errors in headless Edge |
| Chart drawn | A chart canvas or SVG with non-zero size is on the page |

**Correctness** (read from the library's own chart object, not from screenshots):

| Check | How |
|---|---|
| Data | Every value in the prompt is in the chart, unchanged: 48 for A, 8 for B |
| Labels | Series or category names, month labels, units ($ / thousands) |
| Title | Matches the prompt |

**Robustness:**

| Check | How |
|---|---|
| Resizes | No horizontal overflow, and the chart redraws at 400 px and 1400 px wide |
| Theme | Text stays readable in dark mode (contrast of axis labels against the background) |
| PDF / print | The chart appears in a print render |

**Cost:**

| Check | How |
|---|---|
| Chart code | Lines of chart-related code the model wrote |
| Page size | Size of the saved page |
| Library download | Size loaded from the CDN |

**Interactivity (counted, not graded against examples):** which interactions the produced chart actually has. For example: a tooltip on hover, legend clicks, zoom, focus on hover. I'll list them as found, with no extra credit for any particular one.

## Judging the subjective part (planned, not built yet)

The objective checks above show whether a chart works. For how it *feels* (spacing, colours, overall look, how good the interactions are), we'll use two methods together. Background research is in the conversation of 2026-11-10; sources are listed below.

### Method 1: blind pairwise votes by people (the user, with coworkers)

- **The format:** two exhibits side by side, without library names and in random order. Voters interact with both (hover, click, resize), then pick A, B or tie.
  - 3 libraries × 2 prompts = 6 pairs per round.
  - Several voters, each seeing the pairs in a different order.
- **The ranking:** win rates per library; with enough votes, a Bradley-Terry ranking (the method behind Elo-style leaderboards).
- **The model:** WebDev Arena (LMArena). People are more consistent saying which of two is better than giving scores.
- **Who runs it:** the user, with coworkers. A small comparison page that shows the pairs unlabeled and records the votes would make it easier; build it when we pick this back up.

### Method 2: a vision model judging with a checklist per task

- **The model:** ArtifactsBench (Tencent). Render the exhibit, script interactions, capture screenshots over time, and have a multimodal model score them against a checklist written for each task.
- **Capture:** a script drives headless Edge through the DevTools Protocol (Python `websockets`, which the AgentStudio venv already has; no Playwright needed). For each exhibit:
  - a screenshot on load;
  - the mouse moved across a fixed grid of points over the chart, with a screenshot at each;
  - hovering and clicking legend items;
  - resizing to 400 px and 1400 px wide.

  The same steps for every library, so none gets special treatment.
- **Checklist:** about 8–10 items per prompt, mostly neutral, scored yes/no or 1–5. For example: readable labels, colours that stay distinct (including for colour-blind viewers), no overlap, exact values on hover, a working legend, a balanced layout. Written **before** seeing any results.
- **The judge:**
  - For the bake-off: Claude in a Claude Code session, reading the screenshots. This costs nothing extra, but it's a single judge, who also wrote the checklist.
  - For the repeatable test suite (phase 4 and later releases): a vision API model, so it runs unattended. That's roughly 10–25k tokens per exhibit, so small, but check current prices and use an API key the user is happy with. deepseek-v4-flash probably can't read images.
- **Calibration:** compare the judge's ranking with method 1's blind votes. If they agree, use the judge for the test suite. If not, adjust the checklist or drop the judge.
- **Effort:** about half a day for the capture script and two checklists. The script is reusable for later judges.

### Related ideas kept for later

- **Readability as a target:** VisEval (Microsoft, IEEE VIS 2024) splits chart quality into validity, legality (correct type and data) and readability. Asking "can you read it easily?" is less subjective than "aesthetics".
- **Automatic proxies:** WCAG contrast, label and text overlap, colour-blind-safe series colours, consistent spacing values. All measurable in headless Edge.
- **Examples help judges:** UICrit (UIST 2024) found that model critiques of UI improve a lot with worked examples and with the problem region marked on the screenshot. Worth doing if the judge disagrees with people.

### Sources

- WebDev Arena: https://news.lmarena.ai/webdev-arena
- ArtifactsBench: https://artifactsbenchmark.github.io, paper https://arxiv.org/abs/2507.04952, code https://github.com/Tencent-Hunyuan/ArtifactsBenchmark
- VisEval: https://github.com/microsoft/viseval, paper https://arxiv.org/abs/2407.00981
- UICrit: https://arxiv.org/abs/2407.08850
- A sceptical view of LLM judges for web quality: https://www.getmaxim.ai/blog/can-llms-actually-judge-web-development-quality-spoiler-not-really/

## Phase 2: the chart kit (2026-11-10)

`exhibit.chart(target, spec)` is in `plugin/exhibit/tools/exhibit_tool.py` (`_CHART_KIT_SCRIPT`). These are samples I wrote, not agent runs; phase 4 measures what the agent does with the kit.

Spec: `type` (line, area, bar, pie, donut, scatter), `x`, `series` (`{name: values}` or `[{name, data}]`), `data` for pie/donut (`{label: value}`), plus `title`, `prefix`, `suffix`, `decimals`, `stack`, `horizontal`, `smooth`, `height`, `zoom`, `colors`, `xLabel`, `yLabel` and `options` (raw ECharts settings, merged last).

How to repeat the checks:
```
python -X utf8 eval/chart_samples.py <store>
set EXHIBIT_SOURCE=<store>
python -X utf8 eval/chart_check.py <out> sales-line sales-area sales-bar budget-pie budget-donut budget-hbar sales-scatter sales-daily
python -X utf8 eval/chart_hover.py <store> <out> <same ids>
```

Results for the 8 samples:

- **Reliability:** no script errors in light or dark mode; all 8 charts drawn.
- **Correctness:**
  - all data correct where the checker can compare it: line, area and bar 48/48; pie and donut 8/8.
  - The horizontal bar, scatter and daily samples show 0 only because the checker reads labels from the x axis and expects the prompts' shapes. Their data is right.
- **Robustness:**
  - no overflow at 400 or 1400 px wide;
  - chart text contrast 4.9 (light) and 7.1 (dark) for axis labels, 15+ for legends and slice labels;
  - all 8 still drawn in print.
  - PDFs (via `_export_pdf`) contain vector paths for the chart, not an image.
- **Cost:**
  - one line of chart code per page, against 30 to 60 hand-written lines in rounds 1 and 2;
  - ECharts is about 343 KB from the CDN, loaded only on pages that call `exhibit.chart(`.
- **Interaction inventory (hover test, a real mouse over the 7th point or the first slice):**
  - line, area and bar: the tooltip lists all 4 regions for the month (for example "Jul: North $63k, South $52k, East $39k, West $46k"), and the hovered line stays bright while the others fade;
  - pie and donut: the slice pops out, and the tooltip shows "Salaries $412,000 56.59%";
  - scatter: the tooltip shows both axes;
  - legend toggles on every chart; zoom (inside plus slider) on the 365-point sample.
- **Fixed during the checks:**
  - in dark mode the page's accent and the kit's own blue were side by side, so the kit now drops colours close to the accent;
  - slice borders now use the colour behind the chart (the card), not the page;
  - the scatter tooltip showed only y.

### Editable data (added 2026-11-10)

At the user's request, charts of up to 100 values get a collapsible table under them. It is built into the kit, not left to the agent. `eval/chart_edit.py` opens a sample in the real viewer, so saving works. It edits the first value, reloads, then resets.

| Sample | After edit | After reload | After reset (and reload) | Saved data after reset |
|---|---|---|---|---|
| sales-line | 42 → 99 (chart redrawn, "Saved") | 99 | 42 | empty |
| budget-donut | 412000 → 99 | 99 | 412000 | empty |
| sales-scatter | 42 → 99 | 99 | 42 | empty |

The 365-point sample has no table (zooming instead). With the table added, the samples still show no errors, no overflow at 400 px wide, and charts drawn in print, where the table is hidden.

## Phase 4: does the agent use the kit?

**Setup**
- Rounds 1 and 2 used the test builds `exhibit-0.3.0-dev.zip` and `exhibit-0.3.0-dev2.zip`. Since 2026-11-10 there is one 0.3.0 build, `plugin/dist/exhibit-0.3.0.zip`, rebuilt in place, and the dev zips are gone. It's the test build with the chart kit, the editable data table, the new skill guidance, and the clearer message for a made-up `exhibit_id`; WorkSwarm shows it as version 0.3.0-dev.
- Run each prompt in a **new WorkSwarm chat** with deepseek-v4-flash, **three times**. Pick **Freeform** when asked what kind of exhibit.
- Don't add anything to the prompt, and don't ask for fixes afterwards. If the first exhibit is broken, that's a result.
- No library is named, the same as round 1, so the round 1 Chart.js runs are the "before".
- The dashboard prompt doesn't say "interactive", so it also tests the new "interactive by default" rule.

**Prompt A: multi-line trend**
```
Make an exhibit titled "Kit: Sales trend" with an interactive line chart of monthly sales by region for 2025. Data (thousands of dollars), Jan to Dec:
North: 42, 45, 48, 51, 55, 60, 63, 61, 58, 62, 68, 74
South: 38, 37, 41, 44, 43, 47, 52, 55, 53, 50, 54, 59
East: 25, 29, 33, 31, 36, 40, 39, 44, 48, 51, 49, 55
West: 50, 48, 46, 47, 45, 44, 46, 49, 52, 56, 60, 63
```

**Prompt B: breakdown**
```
Make an exhibit titled "Kit: Budget breakdown" with an interactive pie chart of our 2026 operating budget by category. Data (dollars): Salaries 412000, Rent 96000, Software 58000, Marketing 74000, Travel 31000, Equipment 27000, Training 18000, Other 12000.
```

**Prompt C: your dashboard** (the original request from 2026-11-09, word for word)
```
C:\Users\A2306101770\Documents\Obsidian Vaults\HW Notes\Daily can you create a visualization in freeform exhibit to show how many tasks I completed a day over time
```

**What gets measured**
- The same objective checks as rounds 1 and 2: `eval/chart_check.py` for A and B, and the parts that apply for C, plus the rubric.
- Whether the agent used `exhibit.chart`, or wrote its own chart code.
- Tool calls, and how many failed.
- The interaction inventory, including the data table.
- For C: what interactivity it added without being asked.

### Phase 4 results (2026-11-10, `exhibit-0.3.0-dev.zip`, 9 runs)

Nine chats and nine exhibits were found (three per prompt). The installed build was 0.3.0-dev, and the agent loaded the full skill, including the `exhibit.chart` section, in every run.

| Run | Rubric | Used `exhibit.chart` | Tool calls (failed) | Script errors | Data correct | Overflow 400 / 1400 | In print | Contrast light / dark | Script lines | Interactions (inventory) |
|---|---|---|---|---|---|---|---|---|---|---|
| Sales 1 | 1 | no (own ECharts 5.5.0) | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 145 | axis tooltip, series focus, zoom, legend |
| Sales 2 | 1 | no (own ECharts) | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 219 | same, plus summary and an edit-data table |
| Sales 3 | 1 | no (own ECharts) | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 172 | axis tooltip, zoom, legend, number input |
| Budget 1 | 1 | no (own ECharts) | 4 (0) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 234 | item tooltip, legend, inputs, sort buttons |
| Budget 2 | 1 | no (own ECharts) | 4 (0) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 194 | item tooltip, legend, inputs, buttons |
| Budget 3 | 0.75 | **yes** (pie and donut) | 7 (1: `write_file` before reading) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 66 | kit defaults, data tables, stat tiles |
| Dashboard 1 | 0.5 | no (own ECharts) | 43 (1 bash) | 0 | **no**: 31 of 36 days, 116 of 151 tasks, newest first | no / no | yes | 5.4 / 6.8 | 171 | view select, sortable table |
| Dashboard 2 | 1 | no (own ECharts) | 10 (0) | 0 | yes: 36 days, 151 tasks | no / no | yes | 5.4 / 6.8 | 172 | view select, buttons, table |
| Dashboard 3 | 1 | no (own ECharts) | 43 (1 bash) | 0 | yes: 36 days, 151 tasks | no / no | yes | 4.9 / **3.5** | 246 | stat tiles, view select, min-tasks filter, sortable table, zoom |

Notes on the scores and checks:
- **Rubric average:** 0.92 (8.25 of 9).
  - Budget 3 needed a retry: a `write_file` was refused because the file hadn't been read first.
  - Dashboard 1 has incomplete data.
- **Dashboard data** was checked against the daily notes: 36 days, 151 completed tasks, 255 tasks in total.
- **Dark contrast 3.5** in Dashboard 3 is below the 4.5 minimum: the page set its own axis colours.
- **Not verified by hand:** whether the edit tables in the hand-written pages actually work.

**What this says**
- **The kit was ignored: 1 of 9 runs used `exhibit.chart`.** The other 8 loaded ECharts themselves (versions 5.5.0, 5.5.1 and 5.6.0) and wrote 145 to 246 lines of script. In round 1, the agent wrote Chart.js. The skill moved the agent to ECharts but not to the kit. A likely cause is that the skill names ECharts twice ("Exhibit adds it (and Apache ECharts)", "ECharts itself is fine"), and the freeform preset's reply says "write the page yourself".
- **"Interactive by default" worked.** All 3 dashboard runs added interactivity without being asked: view selects, filters, sortable tables, stat tiles. All 6 sales and budget pages added number inputs for the data. Round 1 had no zoom and no series focus on any line chart; now 3 of 3 have zoom and 2 of 3 have series focus.
- **Reliability is unchanged.** There were no script errors, and data was correct in every sales and budget run, as in round 1.
- **Kit gap found by the one kit run:** the page tried to keep its pie, donut and summary cards in step when a table is edited. With no change callback in the kit, it polled the saved data every 400 ms. It expected `{Salaries: …}`, but the kit saves its own table format, so the sync silently does nothing, though the page says it does. The kit needs an `onChange` callback, and a documented format for what it saves.

**Also found by the user:** data editing was visually poor in places, and sometimes missing. Full-page screenshots confirm it:
- Sales 1 has no way to edit the data at all, only series checkboxes.
- Sales 3's "Edit data" button sits jammed against the chart card.
- The kit's own editor was only a small grey "Data (8 rows) · edit" line, easy to miss.
- Only Budget 2's hand-built editor looked good: bordered inputs, a share column, add and reset.

### Fixes after phase 4 (2026-11-10), in `exhibit-0.3.0-dev2.zip`

- **The reply after the user picks Freeform** now says to call `exhibit.chart` for the six chart types, with a one-line example, and not to load Chart.js or ECharts.
- **The skill** no longer names ECharts as something to use, says plainly not to load a chart library for these charts or build an edit table for a chart's data, and documents `onChange`.
- **`show` adds a note** when a page loads its own chart library and doesn't call `exhibit.chart`. It points to `exhibit.chart` for the next version and says not to redo the page just for this.
- **The kit's editor has been redesigned:**
  - an "Edit data · N rows" button with a pencil icon, and an "Edited" badge once the data differs from the original;
  - a bordered panel whose header stays in place while scrolling, with inputs that look like inputs, colour dots matching the chart, and a Share column for pie and donut;
  - Add row, a Reset button that's active only after changes, and a "Saved" note.
- **`onChange(data)` and `data()`:**
  - `onChange(data)` is called after every edit, after Reset, and at load when there are saved edits.
  - `data()` returns the current data in the same shapes as the spec.
  - Tested with a total that follows the table: $728,000 → $316,099 after an edit, kept after reload, $728,000 after Reset.
- **Rechecked:** the 9 samples have no errors, no overflow at 400 or 1400 px, readable contrast, and charts drawn in print. The edit test passes on line, pie and scatter. 106 unit tests pass.

### Phase 4, round 2 results (2026-11-10, `exhibit-0.3.0-dev2.zip`, 9 runs)

Same prompts, same model, three runs each. The installed build was 0.3.0-dev2.

| Run | Rubric | Used `exhibit.chart` | Tool calls (failed) | Script errors | Data correct | Overflow 400 / 1400 | In print | Contrast light / dark | Script lines | Page |
|---|---|---|---|---|---|---|---|---|---|---|
| Sales 1 | 0.75 | yes, with `onChange` | 7 (1: `write_file` before reading) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 67 | 4.4 KB |
| Sales 2 | 1 | yes, with `onChange` | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 72 | 5.4 KB |
| Sales 3 | 1 | yes, with `onChange` | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 59 | 3.8 KB |
| Budget 1 | 1 | yes, with `onChange` | 4 (0) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 43 | 3.2 KB |
| Budget 2 | 1 | yes, with `onChange` | 4 (0) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 61 | 3.6 KB |
| Budget 3 | 1 | yes, with `onChange` | 4 (0) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 40 | 4.2 KB |
| Dashboard 1 | 0.5 | yes, with `onChange` | 14 (0) | 0 | **no**: 176 tasks instead of 151, wrong on 12+ days (counted by a subagent) | no / no | yes | 5.4 / 6.8 | 155 | 9.3 KB |
| Dashboard 2 | 0.75 | yes, with `onChange` | 14 (3: 2 bash, 1 `show` before `preset`) | 0 | yes (completed 151; its "Total" leaves out nested subtasks) | no / no | yes | 5.4 / 6.8 | 117 | 7.5 KB |
| Dashboard 3 | 1 | yes, with `onChange` | 43 (0) | 0 | yes: 36 days, 151 tasks | no / no | yes | 5.4 / 6.8 | 85 | 5.1 KB |

**Edit test on the agent's own pages** (`eval/chart_edit.py`, on copies, in the real viewer):

| Run | Edit, redraw, save, reload | Rest of the page follows the edit (`onChange`) | Reset restores the original |
|---|---|---|---|
| Sales 1 | yes | yes (totals, best month) | **no** |
| Sales 2 | yes | **no** (its extra read-only data table stays stale) | yes |
| Sales 3 | yes | yes | yes |
| Budget 1 | yes | yes (total, category cards) | yes |
| Budget 2 | yes | yes | **no** |
| Budget 3 | yes | yes | yes |
| Dashboard 1 | yes | **no** (its summary doesn't follow) | yes |
| Dashboard 2 | yes | yes (total, best day, average) | yes |
| Dashboard 3 | yes | yes | yes |

**Round 1 vs round 2**

| | Round 1 (dev) | Round 2 (dev2) |
|---|---|---|
| Used `exhibit.chart` | 1 of 9 | **9 of 9** |
| Loaded its own chart library | 8 of 9 | 0 of 9 |
| Rubric average | 0.92 | 0.89 |
| Script lines, sales and budget | 66 to 234 | 40 to 72 |
| Script lines, dashboard | 171 to 246 | 85 to 155 |
| Way to edit the data | missing in 1 of 6 sales/budget pages; mixed look | every page, the same editor |
| Series focus on hover | 2 of 3 line charts | every chart |
| Dark contrast below 4.5 | 1 run (3.5) | none |

**What this says**
- **Pointing the agent to the kit worked.** The reply after the user picks Freeform and the clearer skill took kit use from 1 of 9 to 9 of 9. The `show` note never had to fire.
- **The rubric dips are not about charts.** One dashboard counted wrong (its subagent), and there were two retries: `write_file` before reading, and `show` before `preset`.
- **Two new problems come from how pages use the kit:**
  - **Double saving breaks Reset** (2 of 9). The page saves the chart's data itself and passes its saved copy back as the spec. After a reload the kit treats the edited data as the original. The skill should say the kit already saves edits: always pass the original data, and use `onChange` only to update the page.
  - **Duplicate or unlinked parts** (2 of 9). Sales 2 added a second, read-only copy of the data table that doesn't update. Dashboard 1's summary doesn't follow edits. The skill should say not to repeat the chart's data in another table, and that every number derived from the data belongs in `onChange`.
- **Fewer controls of the agent's own.** Round 1 dashboards had view selectors and sortable tables. In round 2 only 2 of 3 have a selector, and Dashboard 3 has nothing beyond the kit. The agent now leans on the kit, which argues for the UI kit (tables, filters) on the to-do list.

### Fixes after round 2 (2026-11-10), in `exhibit-0.3.0.zip`

**Found by the user: the "Daily Completed Tasks Tracker" (Dashboard 1) went blank after one slider move.** The page clears `#chart` and calls `exhibit.chart` again on every slider `input`. The kit assumed one call per element. On a repeat call, ECharts handed back the old instance, whose drawing had just been cleared, so nothing redrew. Each call also stacked another "Edit data" box, and slow earlier calls could finish after newer ones. Reproduced on a copy: after a quick drag the chart had no SVG and there were 6 editors; after one more move, 7.

Kit fixes:
- **A repeat call on the same element replaces the chart.** The kit disposes the old instance (including one ECharts still holds for the element), removes its editor and stops its resize watcher.
- **A slower earlier call that finishes later is dropped.**
- **An element without an id keeps its saved-data key across calls**; before, each call got a new `chart-N`.
- **Saved edits remember the data they were made on** (a fingerprint of the original table), and come back only on that data. Edits made while filtered to "≥ 9" no longer replace other filters' data after a reload, and a new version with new data isn't overwritten by old edits. Older saves without a fingerprint still load.

The same check after the fix:
- A drag across five values leaves one chart (SVG drawn) and one editor.
- An edit made at "≥ 9" disappears at "≥ 2" (original data, no Edited badge), comes back at "≥ 9", and survives a reload.
- On the samples, edit, save, reload, Reset and the linked total behave as before.

Skill fixes (the two from round 2, plus filters):
- **The kit saves edits itself.** Always pass the data you started with, never a saved copy, and don't save the chart's data with `exhibit.set`, or Reset can't go back to the original. The reply after the user picks Freeform says this too.
- **Every number from a chart's data is updated in `onChange`.** Don't repeat a chart's data in a second table.
- **Filters and views:** call `exhibit.chart` again on the same element with the new data; there's no need to clear it first.


### Round 3 setup (2026-11-10, `exhibit-0.3.0.zip`)

- Same rules as rounds 1 and 2: deepseek-v4-flash, a new chat per run, Freeform, three runs per prompt, no follow-ups.
- Prompts A, B and C as above, plus prompt D. D asks for a filter, to check the repeat-call fix on a page built for it:

**Prompt D: filtered chart**
```
Make an exhibit titled "Kit: Store sales" with weekly sales for three stores over 12 weeks, where I can pick which store to look at. Data (units), weeks 1 to 12:
Downtown: 120, 132, 128, 140, 151, 149, 160, 158, 171, 168, 180, 192
Airport: 88, 91, 95, 90, 99, 104, 101, 110, 108, 115, 119, 117
Mall: 140, 138, 135, 142, 139, 145, 150, 147, 153, 149, 158, 161
```

What's measured: the round 2 checks, plus, on copies, moving every filter and slider, then editing, Reset and reload while filtered, checking the chart stays drawn with one "Edit data" box and every linked number follows.


### Round 3 results (2026-11-10, `exhibit-0.3.0.zip`, 12 runs)

All 12 runs used `exhibit.chart`, loaded no chart library, and had no failed tool calls. Sales, budget and store runs took the shortest path (skill, preset, write, show). All three dashboards counted right (36 days, 151 tasks).

Checks: the load probe, full-page screenshots, every control pressed (both ends of each slider and dropdown), then on every page an edit, a deleted row and a Reset, all on copies. The probe looked for charts with nothing drawn, empty elements, empty tables, extra editors, "NaN" or "undefined" on the page, and exceptions.

| Run | Score | Problem |
|---|---|---|
| Sales 7 | 1 | |
| Sales 8 | 0.5 | Read-only copy of the data table; after a row is deleted the page shows NaN and undefined (its `onChange` assumes 12 months) |
| Sales 9 | 0.5 | Stat tiles show "—" and the totals box is empty (filled only in `onChange`) |
| Budget 7, 8, 9 | 1, 1, 1 | Each adds a read-only table of the chart's data |
| Dashboard 1 | 0.5 | `table: false` turned off "Edit data"; a 36-row read-only table instead |
| Dashboard 2, 3 | 1, 1 | |
| Store 1 | 0.5 | Stat tiles show "—" (filled only in `onChange`) |
| Store 2 | 1 | |
| Store 3 | 0.5 | Line chart drew black dots and no lines (`colors` given by series name); read-only table |

Rubric average 0.79 (9.5 of 12). Read-only tables of a chart's data: 6 of 12.

**Also found by the user:** read-only data tables are never wanted next to a chart: the chart already shows the data, and they don't make it editable. Only when the user asks for a table, or a table is the main and only way to show the data.

**Why**
- **Empty stat tiles and totals (2 runs): the kit.** It called `onChange` at load only when there were saved edits, so numbers filled only in `onChange` stayed empty until the first edit.
- **Dots only (1 run): the kit.** `colors` took only a list; `{Downtown: "#2563eb"}` left ECharts without colors, so it drew black points and no lines.
- **Read-only tables (6 runs): the skill, and the agent's habit.** "Interactive by default" said "Tables: sortable columns…", which reads as an invitation, and the skill documented `table: false`. "Don't repeat a chart's data" sat deep in the chart section.
- **NaN after a deleted row (1 run): the agent's `onChange`**, which assumed the original 12 rows.

### Fixes after round 3 (2026-11-10), in `exhibit-0.3.0.zip`

Kit:
- `onChange` runs once after the chart first draws, always (with saved edits if any). A call to `exhibit.chart` made from inside an `onChange` doesn't call `onChange` back, so a page that rebuilds its chart there can't loop.
- `colors` takes a list, one color, or colors by series or slice name; anything missing takes the theme's colors.

Skill:
- Tables: only when the user asked, or a table is the main and only way to show the data. Never a read-only table that repeats a chart's data. A table that stays has editable cells.
- `table: false` is no longer documented; the "Edit data" table stays.
- `onChange` runs at load, so numbers from the data are written once there.
- The user can add and remove rows, so `onChange` works from the data it's given, never the original count or positions.
- `colors` documented, including by name. The reply after picking Freeform says not to add a table of a chart's data.

Tool: `show` adds a note when a chart-kit page builds its own table or passes `table: false`. On round 3's pages it flags exactly the 6 with a table.

Checked on copies of the round 3 pages: Sales 9 and Store 1 now fill every tile at load, and Store 3 draws its lines in its own colors. Pressing every control still breaks nothing. The slider test and the sample edit test still pass.


### Round 4 results (2026-11-10, rebuilt `exhibit-0.3.0.zip`, 10 runs)

Ten exhibits: three each for A, B and C, and one for D. Prompt D was sent several times in one chat instead of new chats. The user picked Document for it, and on the repeat the agent pointed back to the exhibit it had made.

The same checks as round 3, on copies:
- At load: every chart drew, no exceptions, and no empty visible parts. Sales 11 has an empty placeholder element that is never shown.
- Every control pressed, then an edit, a deleted row and a Reset on every page: nothing broke, and no "NaN" or "undefined".
- Dashboard data: all three total 151 tasks. Dashboard 2 lists 32 days, leaving out the 4 days with no completed tasks; the others list all 36.

| Run | Score | Note |
|---|---|---|
| Sales 10 | 0.75 | The `show` note about its table made it remove the table right away: an `edit_file` failed and was retried, then version 2 |
| Sales 11, 12 | 1, 1 | |
| Budget 10, 11, 12 | 1, 1, 1 | No tables |
| Dashboard 1 | 0.75 | Called `show` before `preset` and was sent back (the same slip as round 2) |
| Dashboard 2, 3 | 1, 1 | Dashboard 2 has a read-only table, folded away under "View full data table" |
| Store 4 (Document) | 1 | Read-only table of the full data |

Rubric average 0.95 (9.5 of 10), up from 0.79.

Read-only tables of a chart's data: 3 of 10 pages added one, against 6 of 12 in round 3. The `show` note fired on all three. Sales 10 removed its table at once; the other two kept theirs, as the note allows ("fix this when you next change this exhibit"). So 2 of 10 final pages still have one, and the user noticed one of them.

What could close the gap: make the note ask for the fix now. That would have removed both, at the cost of one more write and `show` each time (as in Sales 10).

**Change after round 4 (the user's call):** the note now asks for the fix right away, before the agent replies. It says to read the file again before editing it, or to write it whole, then call `show` again with the same `exhibit_id`. If the user asked for the table, the agent leaves it.


### Changes after round 4 (2026-11-10, rebuilt `exhibit-0.3.0.zip`)

- **The `show` note about an extra table now asks for the fix right away**, before the agent replies (the user's call).
- **"Edit data" is on every chart.** The 100-value limit and `table: false` are gone (the user's call): the editor is part of every chart, not an option. Checked on the 365-day sample: the table opens in about 40 ms, a typed value redraws the chart in about 1 ms, the table scrolls inside a fixed-height panel, and edit, reload and Reset work. The remaining limit is saved data (1 MB per exhibit), so edits to a chart with tens of thousands of points may not save; the editor then says so.
- **Tool description shortened** from about 390 words to about 200. Delete, references and gallery details live in the parameter descriptions; a test keeps what the rail relies on.
- **Skill trimmed and aligned**, about 20% fewer words (about 3,430 to 2,650):
  - The front matter description is one line (it's always loaded).
  - "Decide if an exhibit helps" is gone (the tool description covers it), and so is most of the Errors section (each error and refusal says what to do).
  - Charts: one way to change what a chart shows (call `exhibit.chart` again; `update()` is no longer taught). The example fills stat tiles in `onChange`. A table of which chart to use for what. "Don't repeat a chart's data" is said once.
  - It now says which formats exhibits export (HTML; PDF for documents and slides; Markdown for documents).
  - It says to call `preset` before gathering data (2 dashboards had called `show` first), and to count data from files with a script (the one wrong dashboard counted by reading).


### Charts & Graphs preset and Edit data in the top bar (2026-11-10, rebuilt `exhibit-0.3.0.zip`)

The user's call, for three reasons: a clearer choice for users than "Freeform" when they want a chart; consistent exports (PNG, PDF); and one place in the exhibit's own UI to edit data, instead of relying on the generated page.

- **Edit data moved to the viewer's top bar**, for every exhibit with charts, and it's the only way to edit a chart's data (the in-page editor is gone). The kit reports the page's charts to the viewer (name, data as a table, the original, colors); the viewer's panel sends edits and resets back, and the kit redraws, calls `onChange` and saves, as before. A chart picker appears when the page has several charts. Checked:
  - `eval/chart_edit.py` (now driving the panel) on 3 samples: edit, save, reload, Reset and the linked total all work, light and dark.
  - The slider tracker (a chart redrawn on every filter move): one chart in the panel's list after a drag, and edits stay with the filtered data they were made on.
- **PNG export** of each chart from the Export menu: the page draws the chart's SVG onto a canvas at twice its size, on the chart's own background. Fixed on the way: the page's font names in double quotes broke the standalone SVG, so the kit now quotes them with single quotes.
- **Charts & Graphs preset** (`charts`): a page with a title, a one-sentence takeaway, an optional source line, and a `<script type="application/json" id="exhibit-charts">` block of chart specs (with `caption` and `"width": "half"`). The plugin draws the charts, so the agent writes no chart code. `show` refuses a page whose block is missing, isn't valid JSON, has no charts, or has an unknown type, saying which. Checked: three charts (two side by side), light and dark, the panel and its picker, PNG, and PDF.
  - PDF: half-width charts stack on paper. Side by side in print, the charts didn't resize to the narrower boxes reliably (cut off or drawn mid-animation), so on paper there's one chart per row: 2 clean letter pages for the sample.
  - On narrow charts (under 480 px wide) pie labels are hidden, since they were cut off; the legend and tooltip still give names and shares.


### Round 5 results (2026-11-10, 12 runs)

Prompts A to D: 8 runs as Freeform and 3 as Charts & Graphs (one each of sales, budget and dashboard); all 3 store runs were Freeform. The 3 runs at 18:49 (Sales 13, Budget 14, Dashboard 1) loaded the old skill (its old description), so they ran on an earlier install, before the trimmed skill and the new preset.

Checked on copies with the current code: the load probe, screenshots, every control pressed, then an edit, a deleted row and a Reset through the Edit data panel. Dashboard data compared day by day with the notes: all three are right for when they ran (today's note gained 6 ticked tasks between runs, 151 then 157).

| Run | Kind | Score | Note |
|---|---|---|---|
| Sales 13 (old install) | Freeform | 0.5 | Kept a read-only summary table despite the `show` note; NaN on the page after a row is deleted |
| Budget 14 (old install) | Freeform | 1 | |
| Dashboard 1 (old install) | Freeform | 1 | |
| Sales 14, Budget 15 | Freeform | 1, 1 | |
| Dashboard 2 | Freeform | 1 | |
| Store 5 | Freeform | 1 | |
| Store 6 | Freeform | 0.5 | Drew its line chart with d3: no Edit data, no kit interactions. The skill's CDN example was d3, and the `show` note didn't list d3 |
| Store 7 | Freeform | 0.75 | Removed its table after the `show` note (4 edits, no failures), then a second `show` |
| Sales 15 | Charts & Graphs | 1 | Static stat row above the charts (stale after an edit) |
| Budget 16 | Charts & Graphs | 0.75 | `preset` before loading the skill was refused, then retried |
| Dashboard 3 | Charts & Graphs | 0.75 | 3 failed `bash` calls (`head` in PowerShell, then `Get-Content`), then right: 157 tasks, 36 days. Static stat tiles; a "bar view" chart repeating the line chart's data; a monthly totals chart that doesn't follow edits to the daily data |

Rubric average 0.85 (10.25 of 12); 0.86 without the old-install runs.

Found by the user: label cells in Edit data looked editable, and editing one didn't work (Store 7 saved "W2" as "W20"); PNG export showed only the chart.

Fixes after round 5 (in `exhibit-0.3.0.zip`):
- Edit data edits values only. Labels (the x axis, slice names) and series names are plain text; a row the user adds gets a name field.
- PNG export is a picture of the whole exhibit as shown (title, legends, captions, notes), for every exhibit, made by the page with html-to-image (jsDelivr, loaded on demand). The per-chart PNG is gone.
- d3 (and Recharts, NVD3, C3) count as chart libraries for the `show` note, which now asks for the fix right away. The skill's CDN example is dayjs instead of d3.
- Pie labels hide only below 420 px wide (was 480, which hid them in every half-width card).

Open: on Charts & Graphs pages, numbers derived from the data (stat tiles, totals in the takeaway, charts of totals) are static, so they go stale after an edit.

Then, at the user's call, **stat tiles that update** (preset charts v2): the data block takes `"stats"`, each naming a chart and a calculation (sum, average, max, min, count, first, last, change, growth), optionally one series, with `"show": "label"` or `"both"` for the row behind a max or min. The plugin draws them above the charts and recalculates them in each chart's `onChange` (at load, after every edit, after Reset). `show` refuses a stat that names a missing chart or series, or an unknown calculation. The preset now says each chart shows its own data (no charts of totals worked out from another chart) and keeps numbers from the data out of the takeaway and captions. Checked on the new sample: the four tiles are right at load, after setting North's January to 120 (total +78, best month Jan, growth −38.3%), after deleting December (growth to November), after a reload, and after Reset; light and dark, PNG and PDF.


### After the stats (2026-11-10)

- **Moving rows in Edit data**, the user's call: added rows went to the end (a new month after December, a new slice after the others), and guessing an order (dates, months, size) is unreliable, so every row has a grip to drag it, or to move it with the up and down arrow keys. The chart, stats and saved edits follow. Checked: June added at the end (North growth briefly measured to June, +42.9%), moved up 6 places by keyboard (growth back to +76.2%), a donut slice dragged, both orders kept after a reload.
- **Pie labels** now re-check on resize: opening the panel narrows a donut below 420 px and its labels hide instead of being cut off.
- **The picker's descriptions** are the user's wording: Document "Page by page document, export as PDF or .md"; Slides "A slide deck for presentations, export as PDF"; Charts & Graphs "Dynamic visualizations of data, export as PDF or PNG."; Freeform "Written from scratch, no standard formats or templates."
- **Viewer additions** (the user's calls): the divider between the exhibit and the Edit data panel can be dragged (or moved with the arrow keys) and the width is remembered, the exhibit keeping at least 320 px; no "edited" dot on the Edit data button; and a New exhibit page with an ask box and the four formats (live previews of the preset samples), not connected.

### Round 6 prompts (2026-11-10): more kinds of chart and data

Eight prompts, E to L, each covering a kind of chart or data the first four didn't. The prompt never names the chart type (except where noted), so the agent's choice is part of the test. Run each in a new chat with deepseek-v4-flash, twice: once with Freeform and once with Charts & Graphs. The expected values are for checking.

**E: two measures (scatter)**
```
Make an exhibit titled "Kit: Ads and signups" showing how our weekly ad spend relates to new signups. Weeks 1 to 15:
Ad spend ($k): 2.0, 3.5, 1.2, 4.8, 2.9, 5.5, 3.1, 6.2, 0.8, 4.1, 5.0, 2.4, 6.8, 3.8, 4.5
Signups: 118, 171, 90, 224, 138, 246, 160, 281, 72, 198, 205, 131, 302, 196, 207
```
Expect: a scatter with ad spend on x and signups on y (one point per week). Total spend $56.6k, 2,739 signups. On Charts & Graphs, stats can't use a scatter, so `show` should refuse a stat on it, or the agent should leave stats out or put them on another chart.

**F: many long category labels, percentages**
```
Make an exhibit titled "Kit: Feature survey" with the results of our survey "Which improvement do you want most?" (percent of 1,240 answers):
Faster load times 18, Better search results 15, Offline access to saved items 12, Clearer pricing and billing pages 11, Dark mode across every screen 9, More keyboard shortcuts 8, Shared team workspaces 8, Integration with calendar apps 7, Simpler onboarding for new users 6, Other 6
```
Expect: a horizontal bar chart (long labels, 10 categories), sorted as given, suffix %. The values add up to 100. Not a pie (more than 8 parts).

**G: parts of a total over time**
```
Make an exhibit titled "Kit: Energy mix" showing how our country's electricity generation changed from 2018 to 2025 (TWh):
Coal: 410, 395, 360, 350, 320, 290, 255, 220
Gas: 300, 310, 305, 320, 315, 310, 300, 295
Wind: 90, 105, 125, 140, 165, 190, 215, 245
Solar: 20, 30, 45, 60, 80, 105, 135, 170
```
Expect: a stacked area (or stacked bar) by year. Totals 820 (2018) to 930 (2025); wind and solar go from 13.4% to 44.6% of the total.

**H: negative values**
```
Make an exhibit titled "Kit: Monthly profit" with our 2025 profit by product, in thousands of dollars (negative means a loss), Jan to Dec:
Basic: 12, 8, -4, -9, 3, 15, 21, 18, 6, -2, 10, 25
Pro: -15, -11, -6, 2, 9, 14, 19, 23, 27, 31, 30, 38
```
Expect: bars (or lines) crossing zero, with losses shown below the axis. Year totals: Basic $103k, Pro $161k; 3 loss months each.

**I: too many parts for a pie**
```
Make an exhibit titled "Kit: Screen time" showing where my phone time goes on an average day (minutes):
Messaging 94, Video 81, Social 67, Games 45, Music 38, News 22, Maps 15, Shopping 14, Email 12, Fitness 9, Banking 6, Other 11
```
Expect: a horizontal bar chart, not a pie (12 parts). Total 414 minutes (6 h 54 min).

**J: a long daily series with decimals and missing days**
```
Make an exhibit titled "Kit: October temperatures" with our daily high and low temperatures for October 1 to 30 (°C). A dash means the sensor was down that day.
Highs: 23.6, 25.0, 25.3, 24.6, 24.7, 24.6, –, 23.5, 23.7, 22.4, 22.1, 20.6, 17.8, 17.3, 16.4, 17.2, 16.9, –, –, 17.8, 18.8, 20.2, 19.4, 20.3, 20.8, 21.1, 19.1, 17.6, 16.2, 16.7
Lows: 14.9, 15.4, 16.7, 17.4, 17.3, 16.3, –, 15.4, 16.2, 13.7, 11.6, 11.0, 9.4, 10.3, 9.1, 8.3, 7.5, –, –, 10.2, 10.2, 11.8, 12.0, 13.0, 11.5, 10.7, 11.7, 10.1, 9.5, 8.0
```
Expect: a line chart over 30 days with gaps (null) on Oct 7, 18 and 19, not zeros; one decimal; zooming (more than 24 points). Highest high 25.3 on Oct 3, lowest low 7.5 on Oct 17, average high 20.5 (27 days).

**K: two measures in different units**
```
Make an exhibit titled "Kit: Revenue and margin" with our quarterly revenue and gross margin for 2024 and 2025:
Revenue ($M): 12.4, 13.1, 13.8, 15.2, 15.9, 16.4, 17.8, 19.5
Gross margin (%): 41.2, 42.0, 40.5, 43.1, 44.0, 43.6, 45.2, 46.8
```
Expect: revenue and margin not drawn on one axis as if they were the same unit. The kit has no second axis, so two charts (or margin as a separate series chart) is right. Revenue total $124.1M, up 57.3% from the first quarter to the last.

**L: counted from files, grouped by category**
```
C:\Users\A2306101770\Documents\Obsidian Vaults\HW Notes\Daily can you show which day of the week I complete the most tasks on
```
Expect (as of 2026-11-10, file names are dates in 2026): Mon 50, Tue 34, Wed 23, Thu 32, Fri 18, Sat 0, Sun 0 (157 in all; no notes fall on a weekend). A bar chart by weekday, counted with a script. Showing tasks per note (Mon 7.1, Tue 4.3, Wed 3.3, Thu 4.0, Fri 3.0) is a reasonable extra. If notes change before the run, recount.

What to check, besides the usual: the chart type picked; for Charts & Graphs, whether stats are used and correct; no charts worked out from another chart; nulls kept as gaps in J; negatives in H; d3 or other libraries; read-only tables.

## Sample size

One run per prompt and library is a small sample, and a single bad run can mislead. If the results are close, run the closest pair once or twice more before deciding.

## Results

### Round 1 (2026-11-10): the baseline, with no library named

The first six chats were run with the prompts exactly as written, still containing "Use LIBRARY for the chart". So the model chose its own library, and **all six used Chart.js** (4.4.1, one 4.4.7). That makes this round the "how it works today" baseline: three runs per prompt. It's not yet the library comparison.

How it was measured: `eval/chart_check.py` copies each exhibit into a temporary store, serves it through Exhibit's own server (real sandbox and CSP), and drives headless Edge over the DevTools Protocol. The tool-call counts come from the WorkSwarm chat histories. Screenshots: light and dark for each exhibit, saved next to the report.

| Run | Rubric | First `show` worked | Tool calls (failed) | Script errors | Data correct | Overflow at 400 / 1400 px | Chart in print | Chart text contrast, light / dark | Chart code lines | Page | CDN download |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sales trend 1 | 1 | yes | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 64 | 4.5 KB | 79 KB |
| Sales trend 2 | 1 | yes | 5 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 86 | 5.4 KB | 80 KB |
| Sales trend 3 | 1 | yes | 4 (0) | 0 | 48/48 | no / no | yes | 5.4 / 6.8 | 93 | 5.6 KB | 80 KB |
| Budget 1 | 1 | yes | 4 (0) | 0 | 8/8 | no / no | yes | 16.9 / 14.6 | 138 | 7.9 KB | 82 KB |
| Budget 2 | 1 | yes | 4 (0) | 0 | 8/8 | no / no | yes | no chart text (HTML table legend) | 82 | 5.5 KB | 80 KB |
| Budget 3 | 1 | yes | 4 (0) | 0 | 8/8 | no / no | yes | no chart text (HTML table legend) | 78 | 5.4 KB | 80 KB |

Notes:
- Tool calls are skill, preset, write_file, show; one run also used bash.
- Contrast is the chart's own text against the page background, as a WCAG ratio, where 4.5 is the minimum for normal text.

**Interactions found** (an inventory, not graded), from each chart's settings:
- **Every chart:** a hover tooltip, and a legend that toggles series (the Chart.js default).
- **Line charts:** a tooltip showing all four regions at the hovered month (`interaction.mode: "index"`).
- **Pies:** one of three makes the hovered slice pop out (`hoverOffset: 14`).
- **None** has zoom, or highlights the hovered line while dimming the others.

**What this says:**
- **Reliability is not the problem.** Chart.js with deepseek-v4-flash worked 6 of 6 times on the first try, with correct data, no script errors, good resizing and print, and readable text in both themes.
- **The gap you described is real, but it's about interaction depth, not correctness.** The model sets the basics (tooltips, sometimes a pop-out) and stops there.
- **Consequence for the comparison:** ECharts and Vega-Lite have to match this reliability, not just add interactions.

### Round 2 (2026-11-10): ECharts and Vega-Lite, three runs per prompt

All 12 chats used the library they were asked for: ECharts 5.5.x, and Vega 5.25–5.30 with Vega-Lite 5.16–5.21. The data and the measurements are the same as round 1.

| Run | Rubric | First `show` worked | Tool calls (failed) | Script errors | Data correct | Chart width at 400 / 1280 / 1400 px | Chart text contrast, light / dark | Chart code lines | Page | CDN download |
|---|---|---|---|---|---|---|---|---|---|---|
| ECharts, sales 1 | 1 | yes | 4 (0) | 0 | 48/48 | 336 / 1068 / 1068 | 5.4 / 6.8 | 97 | 6.2 KB | 343 KB |
| ECharts, sales 2 | 1 | yes | 4 (0) | 0 | 48/48 | 326 / 1058 / 1058 | 5.4 / 6.8 | 181 | 7.0 KB | 344 KB |
| ECharts, sales 3 | 1 | yes | 4 (0) | 0 | 48/48 | 358 / 1058 / 1058 | 5.4 / 6.8 | 90 | 6.4 KB | 344 KB |
| ECharts, budget 1 | 0.75 | no (see note) | 5 (1) | 0 | 8/8 | 304 / 732 / 732 | 16.9 / 14.6 | 89 | 4.6 KB | 342 KB |
| ECharts, budget 2 | 1 | yes | 4 (0) | 0 | 8/8 | 352 / 980 / 980 | 16.9 / 14.6 | 75 | 4.9 KB | 342 KB |
| ECharts, budget 3 | 1 | yes | 4 (0) | 0 | 8/8 | 320 / 816 / 816 | 16.9 / 14.6 | 90 | 4.8 KB | 342 KB |
| Vega-Lite, sales 1 | 1 | yes | 4 (0) | 0 | 48/48 | 304 / 812 / 812 | 16.9 / 14.6 | 166 | 8.0 KB | 265 KB |
| Vega-Lite, sales 2 | 0.5 | yes | 4 (0) | 0 | 48/48 | 350 / 350 / 350 (fixed) | 21 / **1.2** | 55 | 3.0 KB | 275 KB |
| Vega-Lite, sales 3 | **0** | yes | 4 (0) | **2** | **chart not drawn** | — | — | 161 | 8.1 KB | 292 KB |
| Vega-Lite, budget 1 | 0.5 | yes | 4 (0) | 0 | 8/8 | 341 / 341 / 341 (fixed) | 21 / **1.2** | 69 | 4.0 KB | 288 KB |
| Vega-Lite, budget 2 | 1 | yes | 4 (0) | 0 | 8/8 | 452 / 452 / 452 (fixed) | 5.4 / 6.8 | 89 | 5.5 KB | 259 KB |
| Vega-Lite, budget 3 | 0.5 | yes | 4 (0) | 0 | 8/8 | 291 / 291 / 291 (fixed) | 21 / **1.2** | 84 | 5.6 KB | 290 KB |

Notes:
- **ECharts, budget 1:** the first `show` failed for a reason that has nothing to do with the library. For a new exhibit, the agent filled in every parameter, including a made-up `exhibit_id` (also `exhibit_ids` and `confirm`). The tool rejected the id, and the agent retried without it.
- **Vega-Lite, sales 3:** the page throws "Unrecognized signal name: interactive_legend" and draws nothing. `show` reported success, so the user would see an empty chart.
- **Vega-Lite rated 0.5:**
  - In dark mode, the chart's labels stay Vega's default near-black on the dark page: a contrast of 1.2, so effectively unreadable. The dark screenshot confirms it.
  - The chart is drawn at a fixed small size (about 300–450 px wide) at every window width.
  - Rating these 0.5 ("works but clearly broken in part") is my reading of your rubric. The raw measurements are in the table either way.

**Interactions found** (inventory, not graded):

| | Chart.js (round 1) | ECharts | Vega-Lite |
|---|---|---|---|
| Hover tooltip | 6/6 | 6/6 | 5/5 drawn |
| Legend toggles series | 6/6 (default) | 6/6 (default) | 2/5 |
| Tooltip with all series at a point (line) | 3/3 | 3/3 (`trigger: "axis"`) | — |
| Hovered line highlighted, others dimmed | 0/3 | 2/3 (`emphasis.focus: "series"`) | 0/3 |
| Zoom (line) | 0/3 | 3/3 (zoom slider) | 0/3 |
| Hovered slice pops out (pie) | 1/3 | 3/3 (ECharts default) | — |

### Comparison (three runs per prompt per library, so six per library)

| | Chart.js | ECharts | Vega-Lite |
|---|---|---|---|
| Average rubric | 1.0 | 0.96 | 0.58 |
| Worked on the first `show` | 6/6 | 5/6 (failure unrelated to the library) | 6/6, but 1 drew nothing |
| Script errors | 0 | 0 | 1 run |
| Data correct | 6/6 | 6/6 | 5/6 |
| Resizes with the window | 6/6 | 6/6 | 1/5 |
| Readable text in dark mode | 4/4 measurable | 6/6 | 2/5 |
| Chart in print | 6/6 | 6/6 | 5/5 drawn |
| Chart code lines (average) | 90 | 104 | 104 |
| CDN download | about 80 KB | about 343 KB | about 260–290 KB |

**Conclusion:**
- **ECharts is as reliable as Chart.js** on everything measured: data, errors, resizing, dark mode, print. Its one retry was a tool-usage mistake, not a library problem.
- **It produces clearly more interaction with no extra effort from the model:** series focus on hover, zoom, and slice pop-out came out of the same prompt.
- **Vega-Lite is the weakest** for this model: one broken chart, unreadable dark-mode labels, and fixed sizes.
- **Cost:** ECharts downloads about 4 times as much as Chart.js (about 343 KB). That's acceptable for a local tool, but worth a note.
- **Recommendation:** build the 0.3.0 chart kit on ECharts.

**Caveats:**
- Three runs per prompt, one model, two chart types.
- The user's first impression ("ECharts clearly look better") agrees, but the blind pairwise votes (method 1) and the vision-model judge (method 2) haven't been run yet.
- Fixed sizes and dark-mode defaults are things a chart kit would fix for any library. The comparison shows what the model does on its own.

**Side finding, for the tool:** the agent sometimes fills in `exhibit_id` (and other fields) for a new exhibit. The `exhibit_not_found` error could say "leave exhibit_id out for a new exhibit" to save a retry.

### Round 2 prompts (as run)

Each was run three times: a new chat each, deepseek-v4-flash, Freeform ("No preset").

**A, ECharts:**
```
Make an exhibit titled "Bake-off: Sales trend (ECharts)" with an interactive line chart of monthly sales by region for 2025. Use Apache ECharts for the chart. Data (thousands of dollars), Jan to Dec:
North: 42, 45, 48, 51, 55, 60, 63, 61, 58, 62, 68, 74
South: 38, 37, 41, 44, 43, 47, 52, 55, 53, 50, 54, 59
East: 25, 29, 33, 31, 36, 40, 39, 44, 48, 51, 49, 55
West: 50, 48, 46, 47, 45, 44, 46, 49, 52, 56, 60, 63
```

**A, Vega-Lite:**
```
Make an exhibit titled "Bake-off: Sales trend (Vega-Lite)" with an interactive line chart of monthly sales by region for 2025. Use Vega-Lite for the chart. Data (thousands of dollars), Jan to Dec:
North: 42, 45, 48, 51, 55, 60, 63, 61, 58, 62, 68, 74
South: 38, 37, 41, 44, 43, 47, 52, 55, 53, 50, 54, 59
East: 25, 29, 33, 31, 36, 40, 39, 44, 48, 51, 49, 55
West: 50, 48, 46, 47, 45, 44, 46, 49, 52, 56, 60, 63
```

**B, ECharts:**
```
Make an exhibit titled "Bake-off: Budget breakdown (ECharts)" with an interactive pie chart of our 2026 operating budget by category. Use Apache ECharts for the chart. Data (dollars): Salaries 412000, Rent 96000, Software 58000, Marketing 74000, Travel 31000, Equipment 27000, Training 18000, Other 12000.
```

**B, Vega-Lite:**
```
Make an exhibit titled "Bake-off: Budget breakdown (Vega-Lite)" with an interactive pie chart of our 2026 operating budget by category. Use Vega-Lite for the chart. Data (dollars): Salaries 412000, Rent 96000, Software 58000, Marketing 74000, Travel 31000, Equipment 27000, Training 18000, Other 12000.
```
