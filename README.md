<p align="center"><img src="docs/logo.svg" width="88" alt="Exhibit logo"></p>

<h1 align="center">Exhibits for WorkSwarm</h1>

A WorkSwarm plugin that lets the agent answer with a page instead of a chat message: a report, explainer, dashboard, calculator, tracker, etc. The same page can be read as one scrolling page, as slides, or as document pages. Exhibits open in your browser, keep their versions, can save what you enter, and can be exported.

Similar to artifacts in Claude and canvas in ChatGPT and Gemini.

**Status: 0.4.1** Recommended model: **deepseek-v4-pro**. It uses the prebuilt components where they fit and does better when it has to build its own. deepseek-v4-flash works, but uses the components less and its pages vary more.

![The Exhibits Gallery](docs/gallery.webp)

## How it's built

| Part | What it is |
|---|---|
| Tool | `exhibit`, Python standard library only. Actions: `show`, `preset`, `list`, `gallery`, `read`, `open`, `delete`, `stop` |
| Rail | `ExhibitAskRail`, on WorkSwarm's `ask_user` interrupt |
| Skill | `skills/exhibit/`: when to make an exhibit and how to write one |
| Server | Python `http.server` on `127.0.0.1` |
| Tests | 139 (91 tool, 48 rail), Python 3.11 with the real openjiuwen |

### Functions & Dependencies

| Used for | What |
|---|---|
| Charts | Apache ECharts 5.5.1, wrapped in the plugin's chart kit |
| Diagrams | Mermaid 12.3.0, wrapped in the plugin's diagram kit |
| PNG export | html-to-image 1.11.11 |
| Page check, PDF | Headless Edge or Chrome |
| Prebuilt UI Components | Standardized set that is easy to use, can be modified|

### Plugin - Tool

- Declares itself directly visible, so WorkSwarm's progressive tool loading doesn't hide it behind `tool_search`.
- **Views:** the agent writes one page under headings. The plugin cuts it into slides or document pages (Pandoc's slide level, Paged.js-style page breaks), so the agent never writes a format.
- **Page check:** before the agent replies, the page is opened in headless Edge.
  - Refused: read-only tables of numbers, navigation menus / sticky headers / "back to top" on freeform pages, emojis in headings, buttons and labels.
  - Notes back to the agent: script errors, diagrams that didn't draw, text too small to read, a value axis with no name, prose put in boxes, a heading that repeats the chart title, a score bar on its own, page CSS restyling the page parts, reference lists numbered twice, freeform pages wider than 960px.
- **Libraries:** downloaded once from jsDelivr at pinned versions into `~/.exhibit/lib`, checked against SHA-256 hashes in the plugin, and served locally. Works offline after that.

### Plugin - Rail

- Asks how a new exhibit should open (Document, Slides, Freeform). Confirms every delete.
- One question at a time (WorkSwarm takes one answer at a time).
- Makes the agent load the skill before showing anything.
- Fills in the page the agent just saved when `show` arrives without one.
- Keeps `.html` files with scripts out of the file preview panel.
- Stops an identical failing call after 3 tries in a turn.
- Runs just before the permission rail and removes its answer after reading it, otherwise the permission rail denies the resumed call.

### Storage and server

- `~/.exhibit/exhibits/<exhibit_id>/`: `v1.html`, `v2.html`, …, `meta.json`, `data.json`. Set `EXHIBIT_HOME` to move it.
- Server starts in the agent process on first use: `127.0.0.1`, random port, secret token in every URL (`/<token>/e/<exhibit_id>`).
- The outer page (title, page control, versions, export) is trusted. The exhibit runs in `<iframe sandbox="allow-scripts …">` without `allow-same-origin`, and its own response has a CSP `sandbox` too.
- Saved data: `window.exhibit.get/set/remove/all/clear`, sent by `postMessage` to the outer page, which is the only caller of the data API. 1 MB per exhibit.

## Using it

Ask for something that suits a page. Before a new exhibit, a dialog asks how it should open: Document, Slides, Freeform, or Answer in chat (if you didn't ask for an exhibit). This only picks the first view; you can switch any time. Edits to an existing exhibit aren't asked about and become new versions. The agent replies with a link that opens in your browser.

![The format dialog in WorkSwarm](docs/format-dialog.webp)

### Views

| | Page | Slides | Document |
|---|---|---|---|
| Looks like | One scrolling page, up to 960px wide | 16:9 slides | US Letter pages |
| Cut at | Nothing | Headings | Pages, without splitting blocks |
| Export | HTML, PNG | PDF | PDF |

- Switch views from the top bar. Each view remembers where you were.
- Slides and Document get a thumbnail panel on the left to scroll through and jump to a slide or page.
- Export only offers the current view's format: switch to Slides first to get a slide PDF.
- The gallery icon shows the view an exhibit was last seen in.

#### Page

![A freeform exhibit: an RRSP vs TFSA calculator with sliders, stat tiles and charts](docs/freeform.webp)

Any single HTML page: widgets, calculators, checklists, step-throughs, drawn pictures, plus the charts, diagrams and page parts below. Results vary most here.

#### Slides

![A slide deck exhibit, slide control in the top bar](docs/slides.webp)

- A new slide at each heading, with a title slide from the page's title and first paragraph.
- Crowded slides shrink text down to 60%, then continue on a "(continued)" slide.

#### Document

![A document exhibit: a report with key findings and contents, page control in the top bar](docs/document.webp)

- Same pages on screen and in the PDF. Paragraphs, tables, figures and side-by-side blocks aren't split; headings stay with what follows.

### Beside each item

On the Page view, a narrow column of buttons sits right of the page, next to the item it acts on:

- **Charts:** Export (PNG, PDF, HTML), Edit data, Reference.
- **Diagrams:** Export (PNG, PDF, HTML), Reference.
- **Callouts, panels, code blocks:** Copy, as plain text.

Hovering the buttons outlines their item.

### Charts, diagrams and page parts

Available in every view, light and dark.

- **Charts:** line, area, bar, pie, donut, scatter, dot plot, histogram, box plot, heatmap, calendar heatmap, waterfall, funnel, treemap, sunburst, sankey, radar. Bars go sideways for long labels and stacked data. Value axes show units and which direction is better.
- **Diagrams:** flowcharts, sequence and state diagrams, Gantt charts, timelines, mind maps, database schemas, architecture, etc. Hover highlights and step-throughs.
- **Page parts:** callouts, panels, stat tiles, quotes, captions, sources, citations, tags, comparisons, term lists, numbered steps, meta rows, score bars. The agent can write its own when none fit.
- **Visuals that move:** explainers (sorting, graph search, simulations) are drawn by the agent in its own SVG or canvas, running the real steps, with Play, Step, Reset and speed. A Mermaid diagram can only light up boxes.

### When the agent uses what

The agent plans each section before writing: its point, and the fastest way to show it.

| Content | Form |
|---|---|
| Explanation, reasoning, findings | Plain paragraphs under headings. No cards, boxes or badges around prose; bold a phrase instead |
| Numbers | A chart, type picked by the question (change over time → line, ranking → sorted bar, parts of a whole → pie/treemap, two measures → scatter, etc). Breakdowns stay stacked or grouped |
| A process, structure or states | A diagram, with a step-through if there's an order |
| A plan or history | Gantt chart or timeline |
| Something physical (planets, a device, a place) | A drawn SVG picture, labelled, with scale stated |
| Something the reader can change | A widget, only if there's an input and an output that follows it |
| A list the user works through | Saved checkboxes |
| Tables | Only when asked, and editable |

Page parts each have one job:

- **Callout:** the one thing not to miss in a section, or key takeaways.
- **Panel:** a short set of related items.
- **Stat tiles:** 2 to 4 headline numbers.
- **Comparison:** strengths vs weaknesses, or A vs B.
- **Score bars:** only to compare 2+ items on one scale, never one alone.
- **Numbered steps, term lists, quotes, sources, citations, tags:** what their names say.

The agent shouldn't write CSS for page parts. If the user asks for a different look, its own CSS or the part variables (`--ex-accent`, `--ex-radius`, `--ex-soft`, `--ex-pad`) override them.

### Look and style

- **Colours:** WorkSwarm's logo orange (`#ff8821`) is the accent, with a darker orange (`#b85500`) for small text on white. Yellow = warning, green = good, red = bad.
- **Theme:** follows the system's light/dark setting. Every colour is a CSS variable; the agent doesn't pick dark itself.
- **Font:** the system sans (monospace for code), set by the plugin; a page can still pick its own.
- **Width:** freeform pages are one centred column, at most 960px.
- **Shapes:** square corners by default. Numbered steps are orange hexagons, like the WorkSwarm logo. Stat tiles and panels share the same soft background.
- **Charts:** titles centred, legend gets its own room, axis names kept inside the chart, stacked bars rounded only on the outer end.
- **No emojis** unless the user asks.

### Gallery, versions, data, export

- **Gallery:** previews, search, open exhibits as tabs, view icons, pinning. Rename, delete, copy reference from the ⋯ menu. The side panel collapses when an exhibit opens.
- **Versions:** every change is a new version, pick older ones from the top bar.
- **Saved data:** ticks, inputs, current slide, etc. The agent can read it.
- **Export:** in the current view's format (see Views), or one chart or diagram from the buttons beside it. PDFs are printed by headless Edge or Chrome, no print dialog.

### In chat

- **Reference an exhibit:** link icon in the top bar (or Copy reference in the gallery), then paste. The agent gets its versions, summary and saved data.

  ```
  @exhibit(Monthly budget #8d02e7) why is rent so high?
  ```

- **Quote part of one:** select text, click Quote, paste.

  ```
  @exhibit(Monthly budget #8d02e7)
  > Rent | $1,500 | Fixed
  ```

- Each exhibit records the chat it was made in, so the agent can look it up.
- Deletes are confirmed in a dialog. Deleting several shows one dialog.

## Plugin, and potential future integration with WorkSwarm

A plugin can't change WorkSwarm's frontend. WorkSwarm's HTML preview blocks scripts and its built-in browser refuses `localhost`, so exhibits open in the default browser. 9 of the 11 Hub plugins with interfaces we checked run their own `127.0.0.1` servers for the same reason.

The plan is for this to move into WorkSwarm:

- **Show exhibits inside the app** in a side panel, scripts enabled, isolated origin. The gallery already follows WorkSwarm's UI so it can become a side menu entry.
- **Support MCP Apps** (SEP-1865), the MCP extension for interactive UI that several AI clients already support, so plugins and connectors don't each need a server.
- **Keep the rest:** views, chart and diagram kits, page parts, page check, versions, saved data, export.

Current limits:

- Exhibits open in the browser. The way back is the chat link or the gallery.
- PDF export needs Edge (built into Windows 10/11) or Chrome.
- No web images; the agent draws pictures instead.
- The New exhibit panel isn't connected to the chat yet. Page labels are English only.

## Build and install

Download `exhibit-0.4.1.zip` and add it in WorkSwarm under Extensions.
