# Exhibit to-do

Last updated 2026-11-09.

## Released

- [x] 0.2.1 tested in WorkSwarm, committed, tagged `v0.2.1` and pushed
- [x] 0.2.2 committed, tagged `v0.2.2` and pushed (2026-11-09)
- [x] Untrack the stray framework logs: `git rm -r --cached logs` (already in .gitignore), done with 0.2.2

## Evidence so far

- Same prompt ("5 slide presentation on this repo"), same model (deepseek-v4-flash), repo reading excluded:
  exhibit deck 66 s / 3 tool calls vs PowerPoint (`ppt-creation`) 6 min 47 s / 54 tool calls.
  Most PowerPoint time went to specs, QA scripts and 7 build-check-fix rounds, not slide content.

## Pinned

### Exhibit formats and routing
- [ ] A diverse set of exhibit presets, each a ready-made renderer the agent fills with content instead of writing the whole page:
  chart / dashboard, document / report, slides, table / data, calculator / tool, tracker / checklist, mockup / prototype, diagram; free-form HTML stays as the fallback. Document and slides are done (0.2.2)
- [ ] Routing: pick the preset from the request's intent, then load only that preset's instructions (today the user always picks)
- [x] Start with one preset and compare it with hand-written exhibits: document and slides built in 0.2.2
- [ ] Compare preset exhibits with free-form ones on the same prompts (time, tool calls, rubric score)
- [ ] Switching an exhibit's preset (document ↔ slides ↔ free-form). For now an exhibit's format is locked: the tool refuses a version in another format (`preset_locked`), and the agent offers a new exhibit instead. A first version was built and removed on 2026-11-09. What we learned:
  - Out of a preset should be done by the tool, not the agent. Given only a `convert_to` flag, the agent (deepseek-v4-flash) expected the tool to convert and sent no page; when it did write the page, it repeatedly dropped `html_file`. The tool can do this reliably: a document → one continuous page (drop the preset tag); a deck → all slides stacked in a scrolling page (drop the tag, add a stacking style).
  - Into a preset needs the content moved into the preset's structure (the agent fetches the preset page, fills it, saves it). The tool should accept it only if the page really has that structure.
  - Leaving a preset loses the page control and PDF/Markdown export, so the user should confirm in a dialog. Remember the answer for the turn, so retries after a failed save don't ask again.
  - Each version records its preset (already in place), so older versions keep their own controls and exports.

### Export to traditional file formats
- [x] Download from the exhibit bar (Export menu), 0.2.2
- [ ] Download from the gallery's ⋯ menu too
- [x] Self-contained HTML, with saved data baked in, 0.2.2
- [x] PDF for documents and slides, printed by a hidden Edge or Chrome, 0.2.2
- [x] Markdown for documents (.md with embedded charts, or .zip with images/), 2026-11-09
- [ ] Per-preset formats: Word for documents, PowerPoint for slides, Excel / CSV for tables, PNG / SVG for charts and diagrams

### Referring to and quoting exhibits
- [x] Refer to an exhibit in chat (`@exhibit(Name #code)`, Copy reference) so the agent knows which one you mean and can read it, 0.2.2
- [x] Quote part of an exhibit into the conversation (select text, Quote), 0.2.2
- [x] Link each exhibit to the chat that made it (session id and history path), 0.2.2

## Next

- [ ] Let the agent write an exhibit's saved data (refresh numbers without a new version)
- [ ] Look into "Continue in chat" from an exhibit, which also hooks up the New exhibit button
- [ ] An exhibit button that sends a message to the agent (may wait for the core feature)
- [ ] Measuring: about ten test prompts scored with the 1 / 0.75 / 0.5 / 0 rubric, run before and after changes

## Exhibit quality

- [ ] Real photos in exhibits. Today exhibits can only show images embedded in the page (`img-src data: blob:`), and the skill says images must be inline. So the agent hand-draws SVG, and its pictures come out poor: the flat-tire how-to on 2026-11-09 had 8 rough SVG drawings and no photos.
  - Tool-side embedding: `show` takes `images` (name → https URL), and the HTML uses `<img src="exhibit-image:name">`. The tool downloads each image (https only, size limit per image) and inlines it as a `data:` URL before saving. The page's CSP stays as strict as it is.
  - Skill guidance: use real photos for how-tos and physical things, preferring freely licensed sources (e.g. Wikimedia Commons) with a credit in the caption. Keep SVG for diagrams and charts.
  - Raise the page size limit to allow for embedded photos (2 MB now).
  - Finding the photo stays with the agent (`fetch_webpage`, search); the plugin only embeds it safely.
- [ ] A built-in look: theme variables and Chart.js defaults injected by the tool, charts that redraw when the theme changes
- [ ] Concrete design rules in the skill (lead with the answer, summarize before plotting, show each fact once)
- [ ] In-app preview: a script-free snapshot in WorkSwarm's artifact panel with an "Open exhibit" link

## Small, any time

- [ ] Retake `docs/demo.png`
- [ ] GitHub releases with the zips attached
- [ ] Check the agent reliably fills in `summary` and `chat_alternative` (it did in the last deck run)
- [x] The agent wrote the full HTML before the user was asked "Exhibit or answer in chat?": fixed in 0.2.2, the user now picks the preset (or chat) before anything is written

## Set aside for now

- Chinese labels on the Exhibits pages
- Reporting platform issues to the WorkSwarm team, and the core proposal (exhibits in the artifact panel, MCP Apps)
- Until Exhibit is a core feature: channels beyond the desktop and remote access, patch edits, lifecycle and scale, the remaining security gaps
