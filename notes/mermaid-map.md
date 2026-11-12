# Mermaid map (for the diagram kit)

What Mermaid can do as of 12.3.0 (released 2026-11-03), what works inside an exhibit, and which part of Exhibit owns each kind of visual so the diagram kit, the chart kit and the planned widget modules don't overlap.

Sources: the Mermaid docs and changelog (researched 2026-11-11), plus a sandbox test. The test rendered 37 samples, one per diagram type plus feature and error cases, inside a real exhibit. That means Exhibit's sandbox and CSP, including `connect-src 'none'`. The script is `mermaid_check.py` in the session scratchpad.

## Decisions (2026-11-11)

1. **How the agent writes a diagram: markup.** The agent writes `<pre class="exhibit-diagram">` with the Mermaid source inside. The plugin adds the kit only to pages that contain one, and replaces each block with the drawn diagram. The kit reads the block's raw HTML rather than its plain text, so `<br>` line breaks in labels survive.
   - **Updated the same day, after the user's first tests:** without Mermaid, agents built interactive diagrams that often looked broken. With the first kit, diagrams were clean but static, partly because the skill called them "a picture". So the kit now adds interaction on top of Mermaid's layout:
     - **Hover, click and zoom:** hover a box to highlight it and its connections; click to pin that and show its `%% detail` text; zoom buttons appear when a diagram is drawn noticeably smaller than its natural size.
     - **Step-through:**
       - flowcharts, state, class and ER diagrams use `%% step A, A->B: caption` lines;
       - sequence diagrams step through each message automatically, and timelines through each period;
       - `%% step: caption` lines replace the automatic captions, and `%% steps: off` turns stepping off.
     - **`exhibit.diagram("#id")`** for the page's own controls: `highlight`, `goTo`, `clear`, `on("click" / "step")`, `redraw`.
     - **The skill** now requires a step-through whenever a diagram shows an order.
   - **How boxes and arrows are found** in Mermaid 12.3's SVG:
     - boxes are `g.node` elements whose id contains the name from the Mermaid text;
     - arrows are `path[data-edge]`, matched to the boxes at their two ends by position;
     - sequence messages carry `data-from` and `data-to`;
     - timeline periods carry a `section-N` class.
   - **Checked in headless Edge:** hover, click, details, listed and automatic steps, Play, zoom, the hook and redraw, print, and a stepped diagram on a later slide.
   - **Extended to every type** (the user's call, same day). Each type has a small rule for reading its drawing into parts, links and groups:

     | Type | Parts | Links | Groups | Automatic steps |
     |---|---|---|---|---|
     | Flowchart, state, class, ER, requirement, block, kanban, swimlane, use case, agentflow | `g.node` (name from id) | `path[data-edge]` | `g.cluster` (subgraph, lane, column, boundary) | – |
     | Mind map | `g.node` (`node_N`; steps can use the label) | branch edges, parent to child | – (hover lights a whole branch) | – |
     | C4 | `g.node` | the loose relationship lines | – | – |
     | Architecture | `g.architecture-service` | edges by position | `group-*` | – |
     | Sequence | participants, lifelines, bottom boxes | messages | – | each message |
     | Timeline | period plus its events | – | – | each period |
     | Gantt | `rect.task` plus its label | – | – | each task, by date |
     | Journey | task: rect, label, face, actors | – | sections (by x range) | each task |
     | gitGraph | commit circle plus its nearest label (custom ids land in `class`, so names come from labels) | arrows | branches | each commit |
     | Event modeling | `g.em-box` | relations | swimlanes | each box, left to right |
     | Packet, tree view, Venn, Fishbone, Wardley, Cynefin, railroad | their own classes; tree view folders light up their contents, fishbone categories their causes | Wardley links and trends | Cynefin domains, fishbone categories, railroad rules | – |
     | Anything else (Mermaid's charts, new types) | each innermost group with a shape and a label | – | – | – |

     Checked: every type recognizes its parts with no script errors. Screenshots reviewed for Gantt (step 2 of 4), gitGraph with custom commit ids (step 3 of 5) and a mind map branch on hover. The earlier flowchart, sequence, timeline and slide checks still pass.
2. **Look: B, the neo look with ELK layout,** in the exhibit's colours via `theme: "base"`. A hidden setting switches it to A (classic look, dagre layout) without a code change:
   - **Layout:** neo doesn't set `layout`. Mermaid 12 uses ELK by default where it can, and forcing `layout: "elk"` broke mind maps. Classic sets `layout: "dagre"`. All 35 types render through the kit in both looks.
   - **Where:** a `diagram_look` key in Exhibit's `ui.json` (`"neo"`, the default, or `"classic"`), overridable with the environment variable `EXHIBIT_DIAGRAM_LOOK`. Nothing in the UI shows it.
   - **What it controls:** the kit passes `look` and `layout` to `mermaid.initialize`, and lists them in Mermaid's `secure` config, so a diagram's own frontmatter can't override them. That keeps every exhibit consistent.
   - **When it applies:** diagrams are drawn when the page opens, so a switch changes every existing exhibit on its next load. Nothing is re-saved.
   - **The comparison it's based on:** the same four diagrams (flowchart, sequence, state, ER) were rendered in A, B and Mermaid's default, in light and dark. The script is `mermaid_looks.py` in the session scratchpad. B won on cleaner right-angle routing for larger diagrams. Mermaid's default was ruled out because its black outlines, pastel colours and grey label backgrounds clash with the exhibit theme.
   - **A rendering note for the kit:** the diagram's container needs a set width (`width:100%`). Inside a container that shrinks to fit, wide diagrams render at a fraction of their size.
3. **No Edit diagram panel.** This is a kit for now, and users change diagrams by asking the agent. An editing panel (source text or visual) belongs with a Diagrams preset, if there ever is one.
4. **No new preset.** Diagrams go inside Document, Slides, Charts & Graphs and Freeform pages, the same way charts work in Freeform.
5. **Licence: accepted as is.** Mermaid is MIT; its bundled layout engine, elkjs, is EPL-2.0 or GPL-3.0. Neither is shipped in the plugin zip. The README will name both licences.
6. **A local copy of the libraries, kept by the plugin.** Exhibit pages run in a sandboxed frame with no origin, and the browser gives such frames a fresh cache each load. Measured in headless Edge (`cache_check.py` in the session scratchpad):
   - **What was measured:** a chart page downloaded ECharts (334 KB) on every load, including repeat loads of the same exhibit, and a diagram page downloaded Mermaid (1.5 MB) on every load. This already applies to 0.3.0's charts.
   - **The fix:** the first time the agent uses the exhibit tool, the plugin downloads the pinned libraries (ECharts, Mermaid, html-to-image) in the background into Exhibit's folder, and checks each against a fixed SHA-256 fingerprint. Pages then load them from the plugin's local server: the same files, from the user's own machine.
   - **Until the copy exists:** pages fetch the same files from jsDelivr, as 0.3.0 does today, so nothing breaks while the download runs.
   - **What users get:** fast loads on every visit, and existing exhibits keep working offline once the copy exists.
   - **Unchanged:** licensing (the zip still contains no library copies) and exported HTML, which keeps pointing at jsDelivr because the local server doesn't exist on other machines.
   - **Still to check:** the test covered Edge only. Chrome uses the same engine; Firefox separates its cache even more strictly, so the result should hold there too.

### Diagrams in Document pages (fixed 2026-11-12)

The Document page applies every `@media print` rule on screen, so the screen shows the paper layout. It copied the diagram kit's print rules too, which hid every diagram's step and zoom controls in documents, showed the printed step list instead, and squeezed wide diagrams to unreadable text. The render check couldn't see it: it reported small text, not missing controls. The fix has three general parts:
- **Plugin kit styles stay off the screen.** Kit styles are marked `data-exhibit-kit`, and the Document page doesn't copy their print rules onto the screen. Any future kit can do the same.
- **Paper mode.** The kit's paper rules also apply under `html.exhibit-paper`. The PDF export sets that class from the start, and the Document page sets it around printing, so page breaks are measured on the printed form.
- **Page breaks follow changes in height.** The Document page lays its page breaks out again whenever a block changes height after layout: a late diagram or chart, zoom, step controls, or a section the page opens.

Checked in headless Edge on a Document with a wide stepped flowchart and a sequence diagram:
- **On screen:** controls are shown and the wide diagram is at a readable size.
- **After zoom and in paper mode:** no block crosses a page edge.
- **Export:** the PDF is 4 pages.

## Sandbox test result

- **All 35 bundled diagram types render** from the single-file build `https://cdn.jsdelivr.net/npm/mermaid@12.3.0/dist/mermaid.min.js`, with no CSP violations and no network requests after load.
- **ZenUML fails, as expected.** It's an external plugin and isn't in the bundle.
- **Features that render in the sandbox:**
  - flowchart step animation (12.3);
  - edge animation;
  - `handDrawn` look;
  - markdown labels;
  - `$$math$$` (MathML, no KaTeX fetch).
- **A syntax error comes back as a clear message,** for example `Parse error on line 2 ... got 'end'`. The kit can pass it straight back to the agent.
- **Size:** the full build is **5.5 MB, or 1.59 MB gzipped**, almost 5× ECharts (334 KB gzipped). Load it only on pages that draw a diagram, the same way the chart kit is added only to pages that call `exhibit.chart`.

## Every diagram type

**Owner** says which part of Exhibit should produce this kind of visual:
- **Diagram kit:** Mermaid through the planned diagram kit.
- **Chart kit:** `exhibit.chart` (ECharts), because the visual is driven by numbers the user should be able to edit.
- **Widget:** a planned interactive module.
- **Either:** Mermaid for a static view, a widget when the user needs to interact.

| Keyword | What it is | Status | Owner | Note |
|---|---|---|---|---|
| `flowchart` / `graph` | Nodes and edges, decisions, subgraphs; BPMN shapes (12.3) | stable | Diagram kit | The workhorse |
| `sequenceDiagram` | Messages between participants over time | stable | Diagram kit | |
| `classDiagram` | UML classes | stable | Diagram kit | |
| `stateDiagram-v2` | State machines | stable | Diagram kit | |
| `erDiagram` | Entity relationships, database schemas | stable in practice | Diagram kit | |
| `requirementDiagram` | SysML requirements | stable | Diagram kit | Rare |
| `C4Context` and related | C4 architecture model | stable, unfinished features | Diagram kit | |
| `architecture-beta` | Cloud and service diagrams with icons | beta | Diagram kit | Only 5 built-in icons; other icon packs must be inlined |
| `block` | Grid or block layout of boxes | stable | Diagram kit | |
| `packet` | Bit layout of a network packet | stable | Diagram kit | Niche |
| `gitGraph` | Branch and merge history | stable | Diagram kit | |
| `mindmap` | Mind map | experimental | Diagram kit | |
| `ishikawa-beta` | Fishbone, cause and effect | beta | Diagram kit | |
| `swimlane-beta` | Process split into responsibility lanes | beta | Diagram kit | |
| `usecase-beta` | UML use cases | beta (12.0) | Diagram kit | |
| `agentflow-beta` | Agent workflows: agents, tasks, tools, decisions | beta (12.0) | Diagram kit | |
| `eventmodeling` | Event Modeling frames | new (11.15) | Diagram kit | Niche |
| `railroad-*-beta` | Grammar railroad diagrams (EBNF, ABNF, PEG) | beta | Diagram kit | Niche |
| `cynefin-beta` | Cynefin domains | beta | Diagram kit | Niche |
| `wardley-beta` | Wardley value-chain maps | beta | Diagram kit | Positions are numbers, but they're layout, not data to edit |
| `timeline` | Events grouped by period | stable | Either | Static timeline: diagram kit. Steppable or filterable: widget |
| `treeView-beta` | File or folder tree | beta | Either | Static: diagram kit. Collapsible or explorable: widget |
| `kanban` | Board of columns and cards | stable | Either | Static picture of a board: diagram kit. A board the user moves cards on: widget, with saved state |
| `gantt` | Schedule bars on a date axis | stable | Diagram kit, for now | Dates and durations are data, but ECharts has no ready Gantt. Revisit if users want to edit schedules |
| `journey` | Steps scored 1 to 5 per actor | stable | Diagram kit | Scores are small and illustrative |
| `venn-beta` | Set overlaps | beta | Diagram kit | ECharts has no Venn; sets aren't numeric data |
| `pie` | Pie or donut | stable | **Chart kit** | Duplicate of `exhibit.chart` pie and donut. Never use Mermaid's |
| `xychart` | Bar and line chart | stable | **Chart kit** | Duplicate. Never use Mermaid's |
| `quadrantChart` | Points on a 2×2 grid | stable | **Chart kit** | A scatter with quadrant lines. Add quadrant support to the kit if needed |
| `sankey` | Flow magnitudes | stable | **Chart kit** | ECharts has sankey; add it to the kit when needed |
| `radar-beta` | Radar or spider chart | beta | **Chart kit** | ECharts has radar; add it to the kit when needed |
| `treemap-beta` | Nested rectangles sized by value | beta | **Chart kit** | ECharts has treemap; add it to the kit when needed |
| `zenuml` | Alternative sequence syntax | external | Not available | Not bundled; `sequenceDiagram` covers it |

**The rule for the agent:**
- **Numbers someone might edit:** chart kit.
- **Boxes, arrows, structure and processes:** diagram kit.
- **Anything the user operates** (drag, step, filter, collapse, move cards): widget module.

The skill should state this, and `show` can add a note when a page uses Mermaid's `pie`, `xychart`, `quadrantChart`, `sankey`, `radar-beta` or `treemap-beta`. That's the same treatment as a page loading its own chart library.

## Interactivity: what Mermaid has and what the kit must add

| Feature | Mermaid | Diagram kit or widget |
|---|---|---|
| Click on a node | `click id callback` in flowchart, class, state and gantt; `link`/`links` in sequence. Disabled under `securityLevel: "strict"` and needs `bindFunctions()` after `render()` | **Kit:** keep `strict` (HTML stays escaped) and attach its own click handlers by node id, for example `exhibit.diagram(el, source, { onClick(id) {...} })`. Works in every diagram type, not just four |
| Tooltips | Text on `click` lines, in four types | Kit: the same tooltip as the chart kit, for consistency |
| Edge animation | `e1@{ animate: true }` (11.5): dashes flowing along an edge | Diagram kit: allowed as is |
| Step animation | `e1@{ step: n }` (12.3): a dot travels the edges in order and **loops on its own**. No play, pause or scrub; hidden under reduced motion | **Overlap with the planned stepper.** Mermaid's is automatic. Walkthroughs the user controls belong to the stepper, which can drive a Mermaid diagram by highlighting nodes (via classes) per step. Mermaid's own step animation is fine for a decorative "how it flows" loop |
| Collapse a subgraph | `sg@{ view: collapsed }` (11.17), set by the author only, with no click to toggle | Widget territory if the user should expand and collapse |
| Zoom and pan | **Not built in** | Kit: add pan and zoom for large diagrams |
| Highlight a path or node | Only by restyling (`classDef`, `style`) and re-rendering | Kit: `highlight(ids)` that toggles classes without re-rendering; the stepper builds on it |
| Edit the diagram | Not a Mermaid feature | Kit: an "Edit diagram" panel in the top bar, editing the source text, like Edit data |

## Styling and theme

- **v12 changed the defaults:**
  - ELK layout;
  - the `neo` look;
  - the `redux-color` theme for most types.
  The kit should pin one combination so exhibits don't change look when Mermaid updates. The recommendation is `theme: "base"`, with `themeVariables` set from the exhibit's theme colours.
- **`themeVariables` accept hex colours only.** The kit converts CSS variables to hex before calling `initialize`.
- **No automatic dark mode.** The kit re-renders on theme change, as the chart kit redraws.
- **Fonts:** Mermaid uses the page's font if `fontFamily` is set. It loads no web fonts itself.
- **Avoid in exhibits:**
  - `img:` shapes, which fetch the image and are blocked;
  - icon packs that need a fetch loader (pass the icons inline instead);
  - legacy KaTeX math, which needs CSS and fonts from the network.
- **`look: handDrawn`** renders fine. Allow it as a style choice.
- **Accessibility:** `accTitle` / `accDescr` work in every type. The kit can fill them from the diagram's name.

## Packaging

- **Use the single file** `mermaid.min.js` (IIFE, `window.mermaid`, every bundled type, ELK included). Pin the version, as with ECharts.
- **The ESM build** is 31 KB but lazy-loads about 105 chunks from the CDN. That works under Exhibit's CSP, which allows CDN script loads, but it means more requests and more ways to fail.
- **`@mermaid-js/tiny`** is smaller but drops mindmap, architecture and ELK. Not worth the gaps.
- **Licence:** Mermaid is MIT. Its bundled elkjs is EPL-2.0 or GPL-3.0-or-later; check this before shipping, since Exhibit would load it from a CDN rather than redistribute it.

## Pitfalls for the agent (for the skill)

- **Lowercase `end`** as a node name or text breaks flowcharts and sequences. Capitalise or quote it.
- **`A---oB` and `A---xB`** make circle and cross edges. Put a space before a node starting with o or x.
- **Labels with special characters** (`( ) [ ] { } | : ; # "`) must be quoted: `id["text (x)"]`. Use `#quot;` for a quote inside a label.
- **Beta keywords must include `-beta`:** `architecture-beta`, `radar-beta`, `treemap-beta`, `venn-beta`, `ishikawa-beta`, `wardley-beta`, `treeView-beta`, `cynefin-beta`, `swimlane-beta`, `usecase-beta`, `agentflow-beta`, `railroad-ebnf-beta`. `xychart`, `block`, `packet` and `sankey` no longer need it.
- **Indentation matters** in mindmap, kanban, treemap, treeView, ishikawa and timeline.
- **Frontmatter** (`---` `config:`) must start on line 1.
- **Gantt needs a valid `dateFormat`.**
- **Limits:** 50,000 characters and 500 edges per diagram.
- **Validate before showing:** `mermaid.parse()` throws with a line number on bad syntax. The kit should report that to the agent rather than show Mermaid's "Syntax error" bomb image.
