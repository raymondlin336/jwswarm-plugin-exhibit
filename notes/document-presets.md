# Exhibit presets: document and slides

Status: implemented on this branch, 2026-11-09. Not committed. The plugin version is unchanged.

## What's built

- **Two presets**:
  - `plugin/exhibit/skills/exhibit/presets/document.html` (about 24 KB);
  - `plugin/exhibit/skills/exhibit/presets/slides.html` (about 18 KB).

  Each is a complete sample page: a guidance comment at the top, a fixed stylesheet, sample content and a small script. The agent replaces the content and keeps the rest.
- **Tool action** `{"action": "preset", "name": "document" | "slides" | "none"}`:
  - for document and slides, it returns `{preset, html, next}`;
  - `none` returns only `next` ("write it yourself");
  - with no name, it lists the presets.
- **Rail**: the `preset` call is paused, and the user **always** picks Document, Slides or No preset.
  - Their pick is written into the call, so the agent gets that page back.
  - A new `show` is refused with `[CHOOSE_PRESET]` until the user has picked, once for each new exhibit.
  - Edits never ask.
- **Skill**: step 2 now says to call `preset` before writing a new exhibit, and how to use the result.

No routing yet. The agent never chooses the preset; the user does, every time.

## The dialog

One dialog replaces the old "Exhibit or answer in chat?" question, so the user is asked at most once per new exhibit:

| Situation | Options |
|---|---|
| The user didn't ask for an exhibit | Document · Slides · No preset · Answer in chat |
| The user mentioned "exhibit", or already picked a kind in this chat | Document · Slides · No preset |

- **Answer in chat** works as before: `[USER_CHOSE_CHAT]`, with the agent's `chat_alternative`, now passed on the `preset` call.
- **Skip** means No preset, still an exhibit, not remembered.
- **Cancel** gives `[USER_CANCELLED]`.
- **A reply in their own words** gives `[USER_REPLIED]`. After that, the agent's next `preset` call goes through with the `name` the agent picks.
- **Calling `preset` again** before the exhibit is shown reuses the pick without asking.
- **After a successful new `show`**, the next new exhibit asks again. A failed `show` keeps the pick for the retry.

Why the dialog sits on `preset` and not on `show`: the pick changes what the agent writes, so it has to come before the HTML exists. Asking at `show` would mean writing the page twice.

## Document preset

- **One file, four layouts**, chosen by a class on `<html>`:
  - `report` (the default sample): cover, summary, contents, numbered sections, figures, tables and sources. Proposals use it too.
  - `brief`: one printed page with a status pill, a bottom line, number tiles and a grid of panels.
  - `memo`: To/From/Subject block. A letter uses the same layout with a letter head instead.
  - `notes`: meeting notes with attendees, topics, decisions, and action checkboxes saved through `window.exhibit`.
- **Snippets:** the guidance comment has a snippet for each layout that isn't the sample, so the agent doesn't need four sample files.
- **Print:**
  - always light, even on a dark system;
  - page numbers;
  - headings never end a page, and figures and callouts don't split;
  - phone rules are screen-only;
  - sizes in `rem`, scaled down for print.
- **Print button:** a Print / Save as PDF button calls `print()` inside the sandboxed frame (`allow-modals` is already there).

## Slides preset

- **Slide size:** 16:9 slides. Every size is a multiple of `--u` (1% of the slide's width, using container query units), so slides scale to any window.
- **Layouts:** title, divider, quote, end, and a standard slide holding:
  - bullets;
  - `.columns`;
  - `.numbers` (big-number tiles);
  - an inline SVG chart;
  - an optional `.takeaway` line.
- **Controls:**
  - arrow keys, Page Up/Down, Space, Home/End;
  - swipe on touch screens;
  - a counter and prev/next buttons;
  - N toggles a speaker-notes panel (`aside.notes`; kept for a later PowerPoint export).
- **Saved position:** the current slide is saved with the exhibit.
- **Print:** one slide per landscape 13.333 × 7.5 in page, always light, no controls.
- **Phones held upright:** all slides in a scrolling column, with text at a readable size.

## Checks done

- **Tests:** 72 pass (`plugin/tests`) against the AgentStudio 3.11 venv with the real openjiuwen. Rail tests cover:
  - the dialog with and without the chat option;
  - the pick being written into the call;
  - the `[CHOOSE_PRESET]` gate;
  - one pick per new exhibit;
  - Skip, Cancel, free text, chat, Chinese labels and the skill gate.

  Tool tests cover the action and check that the preset files load nothing from the network, have the theme and print blocks, and are served with the bridge.
- **Rendering:** served with the exact exhibit CSP.
  - Document: report, brief, memo and notes layouts checked in light and dark.
  - Printed to PDF from a dark-mode browser: report 3 pages, brief 1, memo 1, notes 1, slides 8. All light.
  - Slides: keyboard navigation, the notes panel and the phone column checked in the browser pane.
- **Bugs found and fixed while testing:**
  - Slide layout classes clashed with block classes (`.cols` / `.stats`). Two slides showed at once on screen; print hid the bug.
  - Newer Chrome applies `justify-items` in block layout, so the deck's `place-items: center` collapsed phone slides to zero width.

## Not done / open

- **Not tried inside WorkSwarm:**
  - the real dialog;
  - how the agent actually uses the presets, including whether it keeps the stylesheet intact.

  This is the next check: run a few document and slide prompts.
- **Old system prompt:** an agent still following the old instructions (calling `show` straight away) now gets `[CHOOSE_PRESET]` and has to start over. Expected, but it costs one wasted HTML write until the skill is reloaded.
- **Charts on phones:** on a phone, SVG chart labels in slides get small. Fine for now; revisit with the charts preset.
- **Printing from the viewer:** Ctrl+P in the viewer still prints the viewer's toolbar and sidebar; only the in-page button prints the exhibit alone. A viewer ⋯ menu "Print" (a postMessage to the bridge) is the natural next step for export.
- **Not started:** routing (the agent suggesting a preset), and a charts preset.

## Slides v2 (2026-11-09, after trying v1)

v1 had two problems in real use: a control bar under the slide (← counter → Notes Print), and text cut off at the bottom of crowded slides.

- **No control bar.** Moving between slides: keys, swipes, and arrows at the sides that appear while the mouse moves. Notes still open with N. Printing moved to the viewer's Export menu (Print / Save as PDF), which asks the page to print itself.
- **Bigger slides.** The slide fills the window, less a 16 px margin.
- **Text fits.** A script measures each slide. If anything spills past the slide, or out of its own box (a column into the takeaway, a word out of a number tile), it shrinks that slide's content (`--fit`) by binary search, down to 60%. Past that, the slide scrolls and the console warns. Fitting is skipped in the phone layout.
- **No fixed word limit.** The "6 bullets or 40 words" rule is gone. The comment instead gives rough full-size capacities for each layout, and says to split a slide rather than rely on small text.
- Checked against the HTN deck that showed the problem: its slides fit at 72 to 84% text size, the sample deck fits at full size, and a slide with 33 bullets stops at 60% and scrolls.

## Slides v3 (2026-11-09): navigation moved out of the deck

Moving between slides is no longer in the preset. The plugin injects one script (`_SLIDES_SCRIPT` in the tool) into every page whose `exhibit-preset` tag says slides:
- It shows the `.slide` with class `active`, handles keys and swipes, and remembers the slide through `window.exhibit` ("slide").
- In the viewer, it reports its position to the viewer, which draws floating ‹ n / N › buttons at the top right of the exhibit and sends next/prev (and arrow keys pressed while the viewer has focus).
- In an exported HTML file (no viewer), it draws the same small buttons inside the page. They're hidden on paper and in the PDF.
- Older decks: it hides v1's `.controls` bar and v2's `.edge` arrows, and catches keys and swipes first (capture phase), so their own handlers never move a second slide.

The preset (v3) keeps numbering, text fitting and the notes toggle (N). It tells the agent not to add slide buttons or navigation scripts.

## Pages for documents, and the top-bar page control (2026-11-09)

- **Documents as pages:** the plugin injects `_DOCUMENT_SCRIPT` into every page made with the document preset.
  - It applies the preset's print rules on screen (and switches off its screen-only rules), so the screen layout is the print layout.
  - It makes `.sheet` one Letter page wide (816 px) and walks its blocks. Any block that would cross a page's bottom margin (18 mm top, 17 mm sides, 20 mm bottom) is pushed to the next page with a spacer. Headings (`break-after: avoid`) stay with the next block, and `.page-break` forces a new page.
  - It draws page cards and "n / N" numbers behind the content, and scales the strip to fit.
  - For print it sets `@page { size: 8.5in 11in; margin: 0 }`, so the PDF cuts at the same places. Checked: an 8-page test report has the same page breaks on screen and in the PDF.
- **Top-bar page control:** `‹ [n] / N ›` for documents and slides. Both pages talk to it over the `exhibit-pages` channel (`next`, `prev`, `goto`, `hello`, and `key` for slides). This replaces the floating slide buttons.
- **Bug found:** script injection looked for the first `<head`, which matched `<header class="top">` inside the document preset's guidance comment. Every document exhibit got its scripts inside a comment, so it had no saved-data bridge. Fixed with `_insert_in_head`, which skips comments and `<header>`.
- **Document preset v2:** its own Print button is removed (Export → PDF), and the guidance says Exhibit handles pages and page numbers.
