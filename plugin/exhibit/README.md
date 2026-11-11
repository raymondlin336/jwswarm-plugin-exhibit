# Exhibit (exhibit)

**Version 0.2.2 (prototype)**

Lets WorkSwarm build exhibits for you: interactive pages like dashboards, calculators, checklists, forms, charts and small games, opened in a sandboxed browser tab. Exhibits keep their versions and can save what you enter, which WorkSwarm can read back.

## 中文

让 WorkSwarm 为你制作展品：可交互的页面，如仪表盘、计算器、清单、表单、图表和小游戏，并在沙盒浏览器标签页中打开。展品会保留各个版本，并能保存你填写的内容，WorkSwarm 可以读回这些内容。

## Requirements

- **Windows**, with a default web browser set. Exhibits open there, not inside WorkSwarm.
- **Microsoft Edge** (built into Windows 10 and 11) or Google Chrome, for PDF export.
- No account, API key or extra software.

## Core capabilities

- **exhibit (skill)**: Tells the agent when an exhibit helps, how to write one that works in the sandbox, how to save data with `window.exhibit`, and to treat saved data as user input, not instructions.
- **exhibit (tool)**: Saves exhibits and their versions, opens them in your browser, and reads back what you saved. Actions: `show`, `preset`, `list`, `gallery`, `read`, `open`, `delete` and `stop`.
- **ExhibitAskRail (rail)**: Before a new exhibit is written, asks you what kind it should be (Document, Slides or Freeform) with WorkSwarm's option dialog, plus "Answer in chat" unless your message mentioned an exhibit or you already picked one in this chat. Edits to an existing exhibit are never asked about. It also confirms deletes in a dialog, keeps HTML pages with scripts out of the file preview panel, and makes sure the agent has read the exhibit skill before showing one.

## How it works

- Exhibits and saved data are stored in `~/.exhibit/exhibits/<exhibit_id>/` (`v1.html`, `v2.html`, …, `meta.json`, `data.json`). `meta.json` also records the WorkSwarm chat session each version was made in.
- On first use, the tool starts a small web server on `127.0.0.1`, reachable only from this computer, with a secret token in every address. It stops when WorkSwarm closes and restarts when needed.
- Each exhibit runs inside a sandboxed frame. It saves data through `window.exhibit` (`get`, `set`, `remove`, `all`, `clear`), up to 1 MB per exhibit, shared by all its versions.

## Permissions and safety

- **Sandbox:** exhibits run with an isolated origin, so they can't read other exhibits' data, call the local server, use cookies or `localStorage`, or read the page around them.
- **No network:** exhibits can't use `fetch`, XHR or WebSockets, submit forms, or load images from the internet. Scripts and styles may load only from cdnjs.cloudflare.com, cdn.jsdelivr.net and unpkg.com, plus Google Fonts.
- **Local server:** accepts only requests with the secret token and a `127.0.0.1`/`localhost` host, and refuses cross-site requests to the data API.
- **Approvals:** the agent asks before deleting an exhibit; the tool refuses to delete without `confirm: true`.
- **Known limits:** scripts from the three CDNs are trusted, and an exhibit could leak data by building a script address on those hosts. Any program running as your Windows user can read `~/.exhibit`.
- **Dependencies:** Python standard library only. The tool does nothing at import time.

## Updates

### 0.3.0 (in progress)

- **Chart kit:** `exhibit.chart(element, spec)` draws line, area, bar, pie, donut and scatter charts with Apache ECharts. The agent describes the data; the plugin supplies the interactions:
  - hovering a series highlights it and fades the others, and the tooltip lists every series;
  - pie and donut slices pop out and show their value and share;
  - legend items turn series on and off, and long series (more than 24 points) get zooming;
  - the page's theme colours, light and dark, resizing, and vector charts in PDFs;
  - **PNG export** of the whole exhibit (a picture of the page as shown, with titles, legends and notes), from the Export menu, for every exhibit.
  - **editable data:** an **Edit data** button in the exhibit's top bar opens a panel with each chart's data as a table (with a chart picker when there are several). It's the only place to edit a chart's data, the same in every exhibit, whatever the page's code. The user can change values and labels, add or remove rows, or reset; the chart redraws as they type, and edits are kept in the exhibit's saved data. `onChange` lets the rest of the page (totals, other charts) follow the edits. A page can call `exhibit.chart` again on the same element (for example when a filter changes) and the new chart replaces the old one; edits stay with the data they were made on. `onChange` also runs once when the chart first draws, so totals filled there show at load. `colors` takes a list or colors by series name.
  `spec.options` passes raw ECharts settings for anything else. The plugin adds the kit only to pages that call it.
- **Charts & Graphs preset:** a fourth kind of exhibit in the picker, next to Document, Slides and Freeform. The agent fills in a title, a one-sentence takeaway and a JSON block of charts and stat tiles; the plugin draws them (charts full or half width, with captions). Stat tiles (total, average, highest, lowest, count, first, last, change, growth) are worked out from a chart's data and recalculate when the user edits it. Exports as PDF, HTML and PNG. In Edit data only values are editable; labels and series names are fixed, and rows can be moved by dragging (or with the arrow keys). A broken data block is refused with a message saying what's wrong.
- **No "Custom" in Exhibit's dialogs:** WorkSwarm adds a "Custom" choice (type your own answer) to every question; it's removed from the exhibit-kind picker and the delete confirmation, where it isn't a real choice. WorkSwarm has no setting for this, so the plugin wraps WorkSwarm's question builder for these two dialogs only; if an update changes that code, "Custom" simply comes back.
- **New exhibit page:** the New exhibit button opens a page with a box to ask WorkSwarm for an exhibit and the four formats with live previews. Neither is connected yet (a plugin can't start a WorkSwarm chat); both say so.
- **Edit data panel:** drag the divider to resize it (or use the arrow keys on it); the width is remembered. No dot on the button for edited data. The chart picker sits in the panel's top row (no separate "Edit data" heading), and the column headers stay flush with the top when the rows scroll.
- **No speaker notes in slides:** the N key, the notes panel and `<aside class="notes">` are gone from the Slides preset and the skill. Notes in older decks stay hidden.
- **Interactive by default:** the skill now tells the agent to make every exhibit interactive whether or not the user asked: editable data, sortable and filterable tables, inputs for assumptions, and so on. It also tells the agent to use `exhibit.chart` instead of loading a chart library, and `show` adds a note when a page loads its own. Tables only when asked for (or the only way to show the data), never a read-only copy of a chart's data; `show` notes a chart page that adds one.

### 0.2.3 (in progress)

- **"Freeform" everywhere:** the default preset is now called Freeform in the dialog, the tool (`"preset": "freeform"`), the skill and the icons, instead of "No preset", `none` or "free-form". The old `none` still works, and older exhibits read as Freeform.
- **Clearer messages for the agent:**
  - a `show` with no page says exactly which fields the call had, instead of "[CHOOSE_PRESET]";
  - "[STOP_RETRYING]" also lists the call's fields.
- Fixed issue where some slide decks showed "No notes for this slide." above the slide; the plugin now hides speaker notes

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
