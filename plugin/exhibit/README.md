# Exhibit (exhibit)

**Version 0.2.2 (prototype)**

Lets WorkSwarm build exhibits for you: interactive pages like dashboards, calculators, checklists, forms, charts and small games, opened in a sandboxed browser tab. Exhibits keep their versions and can save what you enter, which WorkSwarm can read back.

## 中文

让 WorkSwarm 为你制作展品：可交互的页面，如仪表盘、计算器、清单、表单、图表和小游戏，并在沙盒浏览器标签页中打开。展品会保留各个版本，并能保存你填写的内容，WorkSwarm 可以读回这些内容。

## Requirements

- **Windows**, with a default web browser set. Exhibits open there, not inside WorkSwarm.
- No account, API key or extra software.

## Core capabilities

- **exhibit (skill)**: Tells the agent when an exhibit helps, how to write one that works in the sandbox, how to save data with `window.exhibit`, and to treat saved data as user input, not instructions.
- **exhibit (tool)**: Saves exhibits and their versions, opens them in your browser, and reads back what you saved. Actions: `show`, `list`, `gallery`, `read`, `open`, `delete` and `stop`.
- **ExhibitAskRail (rail)**: Before a new exhibit is shown, asks you "Exhibit or answer in chat?" with WorkSwarm's option dialog, unless your message mentioned an exhibit or you already picked Exhibit in this chat. Edits to an existing exhibit are never asked about. It also confirms deletes in a dialog, keeps HTML pages with scripts out of the file preview panel, and makes sure the agent has read the exhibit skill before showing one.

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

### 0.2.2

- **User interaction improvements:** 
  - Added the ability for users to quote / refer to a specific exhibit AND a specific highlighted piece of text in an exhibit, when chatting with the agent.
  - Added parameter to exhibits that stores what session it originally was made in, so agent can retrieve relevant context if needed.
  - Minor UI improvements
- **Export** added ability to export the exhibit as HTML, and other file formats depending on the preset. (TODO)

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
