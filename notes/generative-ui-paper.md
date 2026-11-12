# Generative UI paper: what applies to Exhibit

Source: "Generative UI: LLMs are Effective UI Generators", Google Research ([arXiv 2604.09577](https://arxiv.org/html/2604.09577), blog Nov 2025). The research behind Gemini's "dynamic view": the model answers with one generated HTML page instead of Markdown. Read in full on 2026-11-12, including the system prompt in appendix A.5.

## What they built

- **Tools:** Google Search (mandatory for any entity or fact), image retrieval and image generation endpoints, Maps, Tone.js and speech for audio, Tailwind from a CDN.
- **Instructions (~3K words):** core philosophy, 6 worked examples, a mandatory 7-step internal plan, technical rules and tool manuals, and a short swappable style section.
- **Post-processors (9):** fixed, deterministic repairs after generation, for example real API keys in place of placeholders, JS and CSS error fixes, escaping attributes, removing hallucinated icons and stray citations. One injects JS that reports client-side errors, but the paper doesn't say whether errors go back to the model. **There is no repair loop:** generation is one-shot, then patched.

### The planning step (paraphrased)

1. Interpret the request; decide whether search is required and which interactive app fits.
2. Plan the app concept: core functions and design.
3. Plan the content (scripts, characters, visual descriptions). Internal only, never shown on the page.
4. Identify data and image needs and plan the searches.
5. Run the searches, with follow-ups.
6. **Brainstorm about 12 UI components** and features.
7. Filter: drop weak or unverified ideas, integrate the rest.

### Core philosophy (the part that mattered most)

- "Your main goal is always to build an interactive application or component", even for "what's the time?".
- "Avoid long segments with a lot of text. Instead, use interactive features / visual features as much as possible."
- Every fact must come from search; hallucinating is "a critical failure".
- No placeholders, mock functionality or dummy data; "NEVER simulate or illustrate any data or functionality."

There is no rule about when to use a table, cards, navigation menus or emojis, and no step that decides between a UI and plain text: UI is always the default.

## Evaluation

- **Conditions:** expert-made website (PAGEN, built by paid freelancers, 3–5 h each), top Google result, plain text, Markdown, Generative UI.
- **Method:** pairwise overall preference by 2 raters per item, 3-point scale. No criteria beyond "which do you prefer"; generation time ignored.
- **Prompt sets:** 100 random LMArena prompts and 100 hand-picked information-seeking prompts (all listed in A.3: people, explainers, how-tos, trips, comparisons, small games and tools).
- **Results (LMArena):** Elo expert 1800, Generative UI 1736, Markdown 1438, top search result 1352, text 1174. Generative UI beat Markdown in 82.8% of pairs (90.5% on information seeking). Experts beat it 50% of the time.

### Ablations

- **Prompt:** full prompt 1553, minimal prompt 1496, prompt without the philosophy and examples 1451. Removing the philosophy hurt more than cutting the prompt to almost nothing, so **the stated philosophy plus worked examples is the biggest prompt lever** they measured.
- **Model:** output errors were 0% for Gemini 2.5 Flash and newer, but 29% for 2.0 Flash and 60% for 2.0 Flash-Lite. Quality depends heavily on the model.
- **Not tested:** planning, examples alone, post-processors, style section.

## What this means for Exhibit

1. **Examples and a stated philosophy steer the model more than rules do.** Their biggest prompt effect came from the philosophy and examples. Exhibit's skill is mostly rules. Worth adding 2–3 short worked examples of *choosing a form*: a findings write-up (prose plus charts, one widget for the mechanism), a how-it-works explainer (martini glass: narrative, then a playground), a data request (chart only).
2. **Their philosophy is the opposite of what we want, and it was tuned for a different measure.** "Interactive first, avoid text" won on *overall preference* for quick answers to search-style prompts. Nobody measured comprehension, accuracy or how professional the page looks. Our "Interactive by default" line came from the same instinct and produced the boxed prose, section menus and collapsibles in the JWMemory capstone. Exhibit's pages are write-ups people keep, so the stance should be: prose is the default, a chart for every dataset, and a widget only where the reader has an input to change (Victor's test).
3. **Plan forms per section, don't brainstorm features.** Their step 6 (brainstorm ~12 components, then filter) pushes toward more UI. Our planning step should be one line per section: its point and its form (text, chart, diagram, widget), with the widget test applied.
4. **Weak models need deterministic checks.** DeepSeek v4 Flash is closer to their weaker backbones than to Gemini 3. Their answer was fixed post-processors. Ours goes further: the render check sends problems back to the agent, which their pipeline doesn't do. Keep rules that matter in code (read-only tables, page-wide navigation, emojis in headings) rather than in prose the agent can argue past.
5. **"Never simulate data" matches our invented-data finding** from the widget baseline. Their version is absolute; ours has to allow clearly labelled mock data for prototypes (the skill already says so) but not invented numbers in reports.
6. **Evaluation to borrow:** pairwise preference against a Markdown answer of the same content, plus their 100 information-seeking prompts as a wider prompt set. Add what they lacked: measurable checks (form counts, invented facts, errors), scored neutrally.

## Changes this supports (not yet made)

- Replace "Interactive by default" with a short philosophy: prose by default, charts for data, widgets only for mechanisms with a changeable input.
- Remove the "table of contents" line; Exhibit owns page-wide navigation. Render check blocks sticky or fixed elements and in-page link menus.
- Neutral starter CSS (no `--card`); explanatory text as plain paragraphs, no boxes, badges or numbered circles.
- Read-only numeric tables become a blocking `show` error.
- Emojis in headings and labels flagged by the render check.
- A per-section form plan before writing.
- 2–3 worked examples of choosing forms.
