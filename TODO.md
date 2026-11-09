# Exhibit to-do

Last updated 2026-11-05.

## Released

- [x] 0.2.1 tested in WorkSwarm, committed, tagged `v0.2.1` and pushed
- [ ] Untrack the stray framework logs: `git rm -r --cached logs` (already in .gitignore)

## Evidence so far

- Same prompt ("5 slide presentation on this repo"), same model (deepseek-v4-flash), repo reading excluded:
  exhibit deck 66 s / 3 tool calls vs PowerPoint (`ppt-creation`) 6 min 47 s / 54 tool calls.
  Most PowerPoint time went to specs, QA scripts and 7 build-check-fix rounds, not slide content.

## Pinned

### Exhibit formats and routing
- [ ] A diverse set of exhibit presets, each a ready-made renderer the agent fills with content instead of writing the whole page:
  chart / dashboard, document / report, slides, table / data, calculator / tool, tracker / checklist, mockup / prototype, diagram; free-form HTML stays as the fallback
- [ ] Routing: pick the preset from the request's intent, then load only that preset's instructions
- [ ] Start with one preset (Chart on the benchmark data, or Slides, HTML-first with PowerPoint as an export) and compare it with today's hand-written exhibits

### Export to traditional file formats
- [ ] Download from the ⋯ menu and the exhibit bar
- [ ] Self-contained HTML, with saved data baked in
- [ ] PDF (print layout)
- [ ] Per-preset formats: Word for documents, PowerPoint for slides, Excel / CSV for tables, PNG / SVG for charts and diagrams

### Referring to and quoting exhibits
- [ ] Refer to an exhibit in chat (for example by name or @-mention) so the agent knows which one you mean and can read it
- [ ] Quote part of an exhibit (a chart, a table, a section) into the conversation
- [ ] Link each exhibit to the chat that made it

## Next

- [ ] Let the agent write an exhibit's saved data (refresh numbers without a new version)
- [ ] Look into "Continue in chat" from an exhibit, which also hooks up the New exhibit button
- [ ] An exhibit button that sends a message to the agent (may wait for the core feature)
- [ ] Measuring: about ten test prompts scored with the 1 / 0.75 / 0.5 / 0 rubric, run before and after changes

## Exhibit quality

- [ ] A built-in look: theme variables and Chart.js defaults injected by the tool, charts that redraw when the theme changes
- [ ] Concrete design rules in the skill (lead with the answer, summarize before plotting, show each fact once)
- [ ] In-app preview: a script-free snapshot in WorkSwarm's artifact panel with an "Open exhibit" link

## Small, any time

- [ ] Retake `docs/demo.png`
- [ ] GitHub releases with the zips attached
- [ ] Check the agent reliably fills in `summary` and `chat_alternative` (it did in the last deck run)
- [ ] The agent writes the full HTML before the user is asked "Exhibit or answer in chat?"

## Set aside for now

- Chinese labels on the Exhibits pages
- Reporting platform issues to the WorkSwarm team, and the core proposal (exhibits in the artifact panel, MCP Apps)
- Until Exhibit is a core feature: channels beyond the desktop and remote access, patch edits, lifecycle and scale, the remaining security gaps
