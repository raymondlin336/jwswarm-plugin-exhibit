# Exhibit (exhibit)

**Version 0.4.1 (prototype)** · Recommended model: deepseek-v4-pro

Lets WorkSwarm build exhibits for you: interactive pages like reports, explainers, dashboards, calculators, checklists and small games, opened in a sandboxed browser tab. Each one can be read as a scrolling page, as slides or as document pages. Exhibits keep their versions and can save what you enter, which WorkSwarm can read back.

## 中文

让 WorkSwarm 为你制作展品：可交互的页面，如仪表盘、计算器、清单、表单、图表和小游戏，并在沙盒浏览器标签页中打开。展品会保留各个版本，并能保存你填写的内容，WorkSwarm 可以读回这些内容。

## Requirements

- **Windows**, with a default web browser set. Exhibits open there, not inside WorkSwarm.
- **Microsoft Edge** (built into Windows 10 and 11) or Google Chrome, for PDF export.
- No account, API key or extra software.

## Core capabilities

- **exhibit (skill)**: Tells the agent when an exhibit helps, how to write one that works in the sandbox, how to save data with `window.exhibit`, and to treat saved data as user input, not instructions.
- **exhibit (tool)**: Saves exhibits and their versions, opens them in your browser, and reads back what you saved. Actions: `show`, `preset`, `list`, `gallery`, `read`, `open`, `delete` and `stop`.
- **ExhibitAskRail (rail)**: Before a new exhibit is written, asks you how it should open (Document, Slides or Freeform) with WorkSwarm's option dialog, plus "Answer in chat" unless your message mentioned an exhibit or you already picked one in this chat. Edits to an existing exhibit are never asked about. It also confirms deletes in a dialog, keeps HTML pages with scripts out of the file preview panel, and makes sure the agent has read the exhibit skill before showing one.

## How it works

- Exhibits and saved data are stored in `~/.exhibit/exhibits/<exhibit_id>/` (`v1.html`, `v2.html`, …, `meta.json`, `data.json`). `meta.json` also records the WorkSwarm chat session each version was made in.
- On first use, the tool starts a small web server on `127.0.0.1`, reachable only from this computer, with a secret token in every address. It stops when WorkSwarm closes and restarts when needed.
- Each exhibit runs inside a sandboxed frame. It saves data through `window.exhibit` (`get`, `set`, `remove`, `all`, `clear`), up to 1 MB per exhibit, shared by all its versions.

## Permissions and safety

- **Sandbox:** exhibits run with an isolated origin, so they can't read other exhibits' data, call the local server, use cookies or `localStorage`, or read the page around them.
- **No network:** exhibits can't use `fetch`, XHR or WebSockets, submit forms, or load images from the internet. Scripts and styles may load only from cdnjs.cloudflare.com, cdn.jsdelivr.net and unpkg.com, plus Google Fonts, and scripts also from the local server's copy of the plugin's libraries.
- **Library copy:** the libraries in `~/.exhibit/lib` are downloaded from cdn.jsdelivr.net only, at pinned versions, and kept or served only if they match a SHA-256 fingerprint built into the plugin.
- **Local server:** accepts only requests with the secret token and a `127.0.0.1`/`localhost` host, and refuses cross-site requests to the data API.
- **Approvals:** the agent asks before deleting an exhibit; the tool refuses to delete without `confirm: true`.
- **Known limits:** scripts from the three CDNs are trusted, and an exhibit could leak data by building a script address on those hosts. Any program running as your Windows user can read `~/.exhibit`.
- **Dependencies:** Python standard library only. The tool does nothing at import time.

## Updates

### 0.4.1

- **Added Views:** every exhibit now defaults to freeform, but can be edited and viewed in Freeform, Slides, and Document view, switchable with a click.
  - Slides and pages are made by the plugin, borrowing Pandoc's slide levels and Paged.js-style page breaks, so the agent only writes one page
  - Includes panel of thumbnails so users can switch between slides and pages
  - Export now depends on the view: in Slides and Document Views, exports will be PDFs
  - The question asked by the agent regarding preset now changed, the answer just determiens which view is set initially
  - **Presets removed** due to the additional of views and element buttons, in order to simplify the user experience
- **Added Element Buttons:** each element (visualizations, important blocks of text, etc) now get their own buttons for export, edit, copy / copy as reference, depending on the type of element.
  - Hovering over the buttons will highlight the element
- Minor UI improvements
- **Improvements / Bug Fixes:**
  - Added limits to margins in freeform, and font choices
  - Fixed issue where some freeform pages stretched across the whole window

### 0.4.0

- **Added Diagrams tools:** the agent writes Mermaid text in `<pre class="exhibit-diagram">` and the plugin draws it (flowcharts, sequence and state diagrams, database schemas, mind maps, timelines, architecture and more) in any exhibit format. Some features include:
  - Deterministic framework around it in order to control light / dark mode, styles, and the agent is told about what type of diagrams that can be generated
  - Encouraged to be interactive whenever appropriate. Hovers, highlights, etc
- **Added Prebuilt Page Elements:** commonly reused elements of a freeform page, so the agent can quickly put a visually cohesive document together, which matching components, formats, and styles
  - Callouts, panels, stat tiles, quotes, source lines, captions, tags, side-by-side comparisons, term lists, numbered steps, meta rows, score bars and citations
  - The agent retains the option to deviate from them if they feel like no prebuilt matches its needs, or if the user requests a change
- **Improved Charts & Graphs:** 11 new chart types: dot plots, histograms, box plots, heatmaps, calendar heatmaps, waterfalls, funnels, treemaps, sunbursts, sankeys and radar charts. These were always a part of ECharts, but lack of visibility made the agnet ignore them
  - Added rules that improves how the agent decides to choose between different graphs and charts
  - All new types work with the Edit Data panel, hover details, and PNG / PDF export
- **Improved Exhibit Quality:**
  - Before replying, the agent's exhibit is opened in a hidden browser, and the agent is told about any problems (script errors, diagrams that didn't draw, text too small to read, charts missing axis names, etc), so it can fix them first
  - The agent now plans what each section should be before writing: plain text by default, charts for numbers, diagrams for processes, Gantt charts / timelines for plans, drawn pictures for physical things, and interactive elements only when there's something to change
- **Improvements / Bug Fixes:**
  - Improved problem where unnecessary interactions and steps are added to static information
  Fixed issue where downloaded modules like ECharts Mermaid are not stored in cache, and diagrams loaded way slower than they should. They should also work offline now
  - Fixed issue where static UI navigation elements would be generated as part of a freeform artifact
  - Fixed overlaps and clippings for bar charts
  - Fixed issue where the agent could accidentally delete parts of an exhibit while fixing a refused one

### 0.3.0

- **Added Charts and Graphs Preset & tools:** line, area, bar, pie, donut and scatter charts with Apache ECharts. Some features include:
  - Fast and presentable charts & graphs, often with animations, interactions, highlights, etc
  - For the preset, the agent fills in a title, a one-sentence takeaway and a JSON block of charts and stat tiles; the plugin draws them (charts full or half width, with captions). All elements depend on editable data and update instantly.
  - There is always an Edit Data panel, that allows you to edit values, add/delete/move entries
  - Exportable as PNGs and PDFs
- **User Interaction Improvements:** 
  - The New Exhibits button is hooked up to a panel where (in the future) can you chat with the agent directly, or choose from a preset to start
  - Added pinning exhibits to the top
- **Improvements / Bug Fixes:**
  - "Custom" removed as an option when selecting a preset, since one has to be chosen
  - By default, new exhibits are encouraged to be interactive, without the user exlicitly saying so
  - Fixed issue where the wrong UI shows during search


### 0.2.2

- **User interaction improvements:** 
  - Added the ability for users to quote / refer to a specific exhibit AND a specific highlighted piece of text in an exhibit, when chatting with the agent
  - Added parameter to exhibits that stores what session it originally was made in, so agent can retrieve relevant context if needed
  - Minor UI improvements
- **Added Export:** ability to save the exhibit in the form of HTML, PDF and Markdown
- **Added Presets:** premade templates that the LLM can fill in to create a complete exhibit.
  - The options so far are documents, slides, and freeform (default). These were added in order to 1. Provide agents with consistency regarding the basic structure of different types of documents, as well as save processing time 2. Allow for more controlled and easily formatted exports to common file formats
  - Before making any exhibits, the agent rail will ask the user what preset (if any) would they like to select.
  - Page controls added to the UI
  - Preset routing, where the agent can pick which preset to follow, is coming soon
- **Improvements / Bug Fixes:**
  - Fixed issue where the user asking to delete multiple exhibits at once will cause user answers to never reach the agent
  - Fixed issue where documents never got the saved-data bridge as their action-item ticks weren't saved
  - Fixed issue where the agent saves a page with write_file, then calls show without html_file and gets stuck retrying (seen with deepseek-v4-flash); the rail now fills in the page it just saved

### 0.2.1

- **User interaction improvements:**
  - When the agent deletes an exhibit, WorkSwarm shows the option select box, and the user has to click confirm, instead of responding via chatting
  - Saying "exhibit" once in a chat counts for the whole chat, so follow-ups aren't asked "Exhibit or answer in chat?" again
- Thumbnails in All Exhibits only refresh when an exhibit is edited, instead of refreshing each time the page is opened. Unnessesary animations removed
- **Bug Fixes / Improvements:**
  - Fixed issue where sometimes agent repeatedly injects HTML directly into chat
  - Added rail to ensure SKILLS.md is always read the the time the tools are made available to the agent
  - Fixes issue where sometimes agent retries the same html despite errors due to details on how to fix it not properly read

### 0.2.0

- **All Exhibits UI** created:
  - Modeled after existing WorkSwarm UI for easier future integration, possibly as another on the left hand side vertical menu
  - Added a collapsible  column with buttons for All Exhibits, creating a new exhibit (not hooked up), and searching for an exhibit (title + description)
  - Main UI panel sorts exhibits by when they were created, first row with large thumbnails, others with smaller ones. Name, created time, last updated time
  - Added more options button, added rename or delete exhibits
- **Individual Exhibit UI** improved:
  - Added renaming, versions, and deletion options
- New `gallery` action, the agent can now open the All Exhibits page when requested
- Exhibits now follow your system's light or dark theme at the time of creation.

### 0.1.0

- First working version, tested end to end in WorkSwarm 0.2.7.
- **Basic framework:** interactive, sandboxed exhibits with versions and saved data, opened in your browser.
- **User confirmation:** asks "Exhibit or answer in chat?" when what the user want is ambiguous or not mentioned.
