# Exhibit: interactive exhibits for WorkSwarm (prototype)

Exhibit lets the WorkSwarm agent build exhibits: interactive pages like dashboards, calculators, checklists, forms, charts and small games, opened in a sandboxed browser tab. Each exhibit keeps its versions and can save what the user enters, which the agent can read back.

It's a prototype of Claude-style artifacts for WorkSwarm. ("Artifact" already means self-improvement outputs in WorkSwarm's backend, so each item here is an *exhibit*.) WorkSwarm's own HTML preview blocks scripts, and its built-in browser refuses `localhost`, so a plugin can only open exhibits in the user's default browser. The longer-term fix belongs in WorkSwarm itself (see "Why a plugin" below).

![Demo exhibit with saved checklist and blocked break-out attempts](docs/demo.png)

## How it works

- **One tool, `exhibit`**, with actions `show`, `list`, `read`, `open`, `delete` and `stop`. Standard library only.
- **Storage:** `~/.exhibit/exhibits/<exhibit_id>/` holds `v1.html`, `v2.html`, …, `meta.json` and `data.json`. Set `EXHIBIT_HOME` to move it.
- **Server:** a small HTTP server on `127.0.0.1` with a random port, started inside the agent process on first use. Every URL includes a secret token. Exhibits open at `/<token>/e/<exhibit_id>`.
- **Sandbox:** the user sees a trusted outer page (title, version picker) with the exhibit inside an `<iframe sandbox="allow-scripts …">` without `allow-same-origin`. The exhibit's own response also carries a CSP `sandbox` directive, so it stays sandboxed even if opened on its own.
- **Saved data:** the exhibit calls `window.exhibit.get/set/remove/all/clear`. These go by `postMessage` to the outer page, which is the only thing allowed to call the data API.

### Security checks

| Threat | Defense |
|---|---|
| Exhibit reads other exhibits' data or calls the server | Opaque origin (sandbox without `allow-same-origin`), `connect-src 'none'` |
| Exhibit sends saved data to the internet | `connect-src 'none'`, `form-action 'none'`, images limited to `data:`/`blob:`; scripts and styles only from three CDNs |
| Websites the user visits call the server | Secret token in every path; data API refuses requests whose `Sec-Fetch-Site` isn't `same-origin` or whose `Origin` doesn't match |
| DNS rebinding | `Host` must be `127.0.0.1:<port>` or `localhost:<port>` |
| Outer page framed by another site | `frame-ancestors 'none'` |
| Prompt injection via saved data | The skill tells the agent to treat saved data as user input, not instructions |

Known gaps: scripts from the three CDNs are trusted; an exhibit can still beacon out through a CDN URL it builds (`script-src` allows those hosts). Any process running as the same Windows user can read `~/.exhibit`.

## Verified

- 12 unit tests (`python -m unittest discover -s plugin/tests`).
- End to end in headless Microsoft Edge (as "Live Pages", before the rename to Exhibit): the exhibit loaded data saved earlier, saved a visit counter on each load (reached 3 over 3 loads), drew with Chart.js from jsDelivr, and all five break-out attempts were blocked (server API, internet fetch, `localStorage`, reading the outer page, cookies). The agent's `read` action returned the saved values.
- **Not yet tested inside WorkSwarm itself.** The tool interface mirrors the Obsidian CLI plugin, but loading, the skill trigger and opening the default browser from WorkSwarm still need a real run.

## Build and install

```powershell
powershell -ExecutionPolicy Bypass -File plugin\package.ps1
```

This writes `plugin\dist\exhibit-0.1.0.zip`. Import it in WorkSwarm under Extensions, the same way as the Obsidian CLI plugin.

## Why a plugin, and what WorkSwarm itself should do

A plugin can't change WorkSwarm's frontend, so exhibits open in a separate browser tab. Nine of the eleven Hub plugins with interfaces that we checked already run their own `127.0.0.1` servers for this; Exhibit could replace those one-off servers. The proper fix is in WorkSwarm: render exhibits inside the app with scripts enabled in an isolated origin, and support **MCP Apps** (SEP-1865), the interactive-UI extension Claude and ChatGPT use, so connectors can bring their own interfaces.
