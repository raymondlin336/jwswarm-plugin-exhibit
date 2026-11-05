# Exhibit (exhibit)

**Version 0.2.1 (prototype)**

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

- Exhibits and saved data are stored in `~/.exhibit/exhibits/<exhibit_id>/` (`v1.html`, `v2.html`, …, `meta.json`, `data.json`).
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

### 0.2.1

- **Delete asks in a dialog:** when the agent deletes an exhibit, WorkSwarm shows "Delete '<name>'?" with Delete and Keep it, instead of the agent asking in chat. Nothing is deleted unless you pick Delete.
- **No more blank charts in the file preview:** if the agent tries to send an HTML page with scripts as a file, it's told to show it as an exhibit instead (the preview panel blocks scripts). If you asked for the file itself, it can still send it.
- **The agent always reads the exhibit instructions** before showing one, so exhibits follow the rules for theme, libraries and saving data.
- The agent refers to exhibits by name instead of showing their ids.
- **No more retry loops:** the agent can hand over a long page as a saved file (`html_file`), errors say how to fix the call, and the same failing call is stopped after 3 tries with a note to fix it or explain.
- Saying "exhibit" once in a chat counts for the whole chat, so follow-ups aren't asked "Exhibit or answer in chat?" again.
- **Previews only refresh when an exhibit is edited:** each version is cached by your browser, thumbnails draw without animations, and renaming or deleting on All exhibits updates the page in place instead of reloading it.

### 0.2.0

- **New Exhibits pages,** styled after WorkSwarm:
  - a rail with WorkSwarm's logo and an Exhibits button;
  - a collapsible Exhibits column with a New exhibit button (not hooked up yet), search over all your exhibits, an All exhibits link, and your open exhibits as tabs.
- **The All exhibits page** lists exhibits newest-created first: a row of large cards with live previews, then the rest as list rows with a small preview, name, and when each was updated and created.
- **Unique names:** a new or renamed exhibit that would reuse another's name gets a number, like "Report (2)".
- **More actions (⋯):** rename or delete exhibits from All exhibits, or delete one from its bar. Deleting asks for confirmation first.
- **A simpler bar above each exhibit:** click the title to rename it, and a version menu with dates (shown when there's more than one version).
- **New `gallery` action,** so the agent can open the Exhibits page when you ask to see your exhibits; `list` also returns its link.
- **New `summary` field:** one line describing each exhibit, used for search.
- **Exhibits follow your system's light or dark theme** instead of picking one.
- **Fix:** after an update, a server left running by the old version is no longer reused, so new pages show up without restarting WorkSwarm.

### 0.1.0

- First working release, tested end to end in WorkSwarm 0.2.7.
- **exhibit tool:** interactive, sandboxed exhibits with versions and saved data, opened in your browser. It's always visible to the agent, which tells it to use this tool instead of the preview panel for interactive HTML.
- **ExhibitAskRail:** asks "Exhibit or answer in chat?" before a new exhibit you didn't ask for, with the agent's description of the chat alternative.
- **exhibit skill:** when an exhibit helps, how to write one that works in the sandbox, and how to report results honestly.
