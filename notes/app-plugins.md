# WorkSwarm 0.2.7 application plugins: can the Exhibit gallery be a native nav page?

Read-only investigation, 2026-11-09. Nothing installed, nothing restarted.

Sources:
1. Readable Python source of the extension system at `...\WorkSwarm\_internal\jiuwenswarm\extensions\` (loader.py, manager.py, registry.py, application_host.py, sdk/application_plugin.py, sdk/base.py, types.py, video_duplex/extension.py and extension.yaml).
2. The frontend bundle `...\channels\web\frontend\dist\assets\index-BNp3WxG0.js`.
3. One live GET to the gateway, `127.0.0.1:19000/api/application-plugins`.

Everything below is verified from those unless marked **[unverified]**.

## Verdict (short)

**Feasible, with caveats.** An "application plugin" is a different system from our agent plugin, but a package can be an *iframe* page with its own static files. A native nav entry "Exhibits" that opens an iframe is realistic today. The hard parts:

- (a) The iframe `src` must be a file served from the plugin's own assets, not an arbitrary URL. Reaching our token-protected random-port server needs a trampoline.
- (b) Our server sends `frame-ancestors 'none'`, which must change.
- (c) There is no install UI for application plugins. It is a manual folder drop plus a restart (restart is inferred).
- (d) There is no host-to-iframe message bridge, and every plugin gets the same generic nav icon.

## 1. Registration, layout, manifest

It is a separate system ("extensions"), NOT the agent-plugin `manifest.json` system.

- Manifest file: **`extension.yaml`** (YAML), not `manifest.json`. `MANIFEST_FILENAME = "extension.yaml"`.
- Optional entry script: **`extension.py`** exposing `async def register_extensions(registry)`.
- Discovery (`manager.py`): search paths are `~/.jiuwenswarm/application_plugins/` (created on startup, searched first, the user-install location), then `extensions.extension_dirs` from config (`;`-separated), then the built-in `jiuwenswarm/extensions`. Each *direct subdirectory* containing `extension.yaml` or `extension.py` is an extension root. Loaded once at startup (no hot reload seen).

  ```
  _USER_APPLICATION_PLUGIN_DIR = "application_plugins"
  user_plugin_dir = get_root_dir() / _USER_APPLICATION_PLUGIN_DIR
  ```

  `C:\Users\A2306101770\.jiuwenswarm\application_plugins` exists and is currently empty.
- Manifest fields (`sdk/base.py`, `ExtensionMetadata`): `id, name, version, description, author, min_jiuwenswarm_version, dependencies{pkg: spec}, config_schema, package_type (default "extension"), permissions[list of str], frontend[list of dicts]`. Also `requires_transport: true` (skipped in Runtime-direct mode). `dependencies` are pip-installed at load time (uv or pip, 120 s timeout).
- Built-in example `video_duplex/extension.yaml`:

  ```yaml
  id: video-duplex
  name: Full-duplex Video
  version: 1.0.0
  package_type: application
  min_jiuwenswarm_version: "0.2.5"
  permissions: [camera, microphone, display_capture, outbound_network, agent_tools]
  ```
- Two flavours:
  1. **Manifest-only** (no `extension.py`) with `package_type: application`. The loader builds a `ManifestApplicationPlugin(root)`. Iframe frontends only: any other `render_mode` raises `"manifest-only application plugins support iframe frontends only"`. It must declare at least one `frontend` entry. `frontend` entry keys: `id` (default `<plugin_id>-page`), `nav_key` (default `app:<plugin_id>`), `title` (default plugin name), `title_i18n_key`, `render_mode` (iframe), `entrypoint` (default `index.html`), `position` (default 100+index, int).
  2. **Full-stack**: `extension.py` with `register_extensions` calling `registry.register_application_plugin(<ApplicationPluginExtension subclass>)`. This gives Python in the gateway process: `bind_web_channel(channel, services)` (register RPC methods on the web websocket, `services.agent_client`), `websocket_routes()`, `frontend_contributions()`, `is_enabled()`, `frontend_asset_root()`.
- Comparison with our agent plugin `plugin/exhibit/manifest.json`: that one uses `"package_type": "plugin"` with `tools/skills/rails` and is uploaded through the UI (the upload hint says zip/tar with a `manifest.json` declaring `package_type`). The extension loader reads none of those keys. The two systems share nothing but the words "package_type" and "manifest".
- Install/enable: **no install UI found.** grep of the bundle for `extension.yaml` and `application_plugins` returned nothing. Install means copying a folder to `~/.jiuwenswarm/application_plugins/<name>/` and restarting WorkSwarm **[restart need inferred from load-once code, not tested]**. Enable/disable is `is_enabled()` on the Python class (manifest-only plugins are always enabled). The built-in one is toggled by the `VIDEO_DUPLEX_ENABLED` env or settings.
- A broken plugin only logs `加载扩展 ... 失败` and is skipped (try/except in `load_all_extensions`).
- Live check: `GET :19000/api/application-plugins` currently returns only video-duplex:

  ```
  {"api_version":1,"plugins":[{"plugin_id":"video-duplex","plugin_version":"1.0.0",...,"enabled":true,"id":"video-live",
   "nav_key":"app:video-duplex","title":"Full-duplex","render_mode":"none","component":"video-duplex","position":75}]}
  ```

  Its tab is hidden on purpose (`render_mode="none"`); a code comment says its config lives in Settings > Experimental.

## 2. `render_mode: "iframe"`

Frontend (bundle):

```js
function sVe({contribution:e}){ if(e.render_mode==="none")return null;
 if(e.render_mode==="iframe") return e.entry_url ? o.jsx("iframe",{className:"application-plugin-frame",
   src:e.entry_url, title:e.title, allow:rVe(e.permissions)}) : null; ...
```

- **`src` = `entry_url`**, which the *backend* builds in `application_host.py`: `/api/application-plugins/<plugin_id>/assets/<entrypoint>` (relative, same origin as the host page). The plugin cannot supply an arbitrary URL; `entrypoint` is only a path under the plugin's asset root. The asset route serves files with `Cache-Control: no-cache`, checks path traversal, and returns 404 otherwise. It has no token of its own.
- Asset root is `<plugin dir>/frontend/dist/` (default `frontend_asset_root`).
- **No `sandbox` attribute** on the iframe. Only `allow=` is set, built from `permissions`: `camera`, `microphone`, `display_capture` (becomes `display-capture`), nothing else. CSS: `.application-plugin-frame{width:100%;height:100%;border:0;background:var(--color-bg)}`. The page fills the content area (`<div class="app-section">`).
- **Pointing at an external localhost server:** not directly. Workarounds, none tested:
  - (a) `frontend/dist/index.html` contains a nested `<iframe src="http://127.0.0.1:PORT/TOKEN/">`, or a `<meta refresh>` / `location.replace` to it. The host `index.html` has no Content-Security-Policy (0 matches; only charset, viewport, theme-color metas), so the host does not block it. **[Gateway/5173 response headers not checked: 5173 returns 403 to curl.]**
  - (b) Our server sets `frame-ancestors 'none'` on shell pages (`_shell_csp` in exhibit_tool.py), and it has a Host-header check and a per-process random port and token. So (a) needs `frame-ancestors` relaxed to the host origin (for example `http://127.0.0.1:5173 http://localhost:5173`, or whatever origin the desktop shell uses **[unverified]**).
  - (c) The port and token change every session (`ThreadingHTTPServer(("127.0.0.1", 0))`, `secrets.token_urlsafe`) and live in Exhibit's `server.json`. A static page can't read that file. Options:
    - (i) A full-stack application plugin whose `extension.py` writes `frontend/dist/url.json` (or rewrites `index.html`) from `server.json`. The tool starts the server lazily on first use (`_ensure_server`), so the page may open before any server exists, and the agent tool and gateway may be different processes **[process model unverified]**.
    - (ii) Give the exhibit server a stable port plus a stable token file.
    - (iii) Move the gallery UI into the plugin's static assets and talk to exhibit data over `register_method` RPC (see "Bigger option").

## 3. `bundled` mode

```js
const t=Qie.get(e.plugin_id); return t ? o.jsx(t,{}) : null
JWe=Object.assign({"../../../../../extensions/video_duplex/frontend/index.tsx":XWe}), Qie=new Map ...
```

Bundled components are found through a **Vite build-time glob** over `extensions/*/frontend/index.tsx`, compiled into the main bundle and registered by `applicationPluginId`. The only entry is `video_duplex`. A plugin dropped into `~/.jiuwenswarm/application_plugins` cannot add a bundled component without rebuilding WorkSwarm's frontend.

The SDK docstring agrees: "`bundled` entries are compiled with Jiuwen... `iframe` entries are prebuilt assets shipped by an installable plugin." So **a third-party plugin can ship its own frontend assets only as iframe pages** (static files in `frontend/dist`). The extra hooks `applicationPluginSettings`, `applicationPluginTaskInputAction` and `applicationPluginTaskRuntime` are bundled-only.

## 4. Nav entry, icon, ordering, combined packages

- Sidebar (`TKe`) is an icon rail. Built-ins in order: chat, agents, skills, connectorMarket, experiments, personalContext, settings, updatepanel. Plugin entries are **appended after the built-ins** (`[...MKe, ...d]`):

  ```js
  d=i.filter(p=>p.enabled!==!1).map(p=>({key:p.nav_key,labelKey:p.title_i18n_key,label:p.title,icon:o.jsx(jie,{"aria-hidden":!0})}))
  ```

  So there is **one generic icon (`jie`, a 16x16 layered glyph) for every application plugin, and no manifest field to change it.** The label is `title`, or the host's i18n key (a plugin can't add translations).
- `position` only sorts plugin entries among themselves (backend sorts by `(position, nav_key)`, the frontend sorts again by `position`). It does NOT interleave with built-ins. Entries missing `plugin_id/id/nav_key/title`, or with an invalid `render_mode`, are dropped. `enabled:false` or `render_mode:"none"` hides the entry.
- The active page is `Ir.find(Z=>Z.nav_key===x)` rendered as `<sVe contribution=.../>` inside `.app-section`. It is mounted only while active, so the iframe reloads on every visit (unlike personalContext, which is kept hidden).
- **Agent plugin and application plugin in one package: no.** Different roots, manifest files and loaders. Our agent plugin is uploaded through the agent-plugin UI (manifest.json). The application plugin would be a second folder in `~/.jiuwenswarm/application_plugins/`, so it can't ship in the same zip. They could share data on disk by path **[not tested]**.

## 5. Bridge to the host app

- grep for `postMessage` and message listeners in the bundle found only the React scheduler, PPTX/XLSX workers and audio worklets. **There is no host-to-plugin-iframe message API**: no "navigate to chat", no session id handed over.
- A plugin asset iframe is same-origin with the host, so it could technically reach `window.parent` or same-origin gateway APIs. That is unsupported and brittle **[not tested]**. A nested cross-origin exhibit page has no such access.
- What does exist for full-stack plugins: websocket RPC via `channel.register_method("x.y", handler(ws, req_id, params, session_id))` (the client protocol lives in the compiled frontend and was **not examined**), extra websocket routes, and `services.agent_client` (Core Agent client) for delegating work to the agent **[unverified]**.

## What it would take (rough, nothing built)

Minimal prototype:

1. Folder `~/.jiuwenswarm/application_plugins/exhibit-gallery/` with `extension.yaml` (`package_type: application`, one `frontend` entry: `title: Exhibits`, `entrypoint: index.html`) and `frontend/dist/index.html`. Manifest-only is enough for a static page.
2. `index.html` has to find the live gallery URL and embed or redirect to it (options (c) above). Simplest robust route: the Exhibit server gets a stable port, or a small `extension.py` writes a known `url.json` into the asset dir. Also relax `frame-ancestors` to the host origin. Keep the token, since it is the protection.
3. Keep the browser gallery as a fallback.

Caveats:
- Separate manual install and restart.
- Generic icon, no localization.
- No agent-to-page bridge.
- `allow=` has no clipboard or fullscreen.
- Nesting would be host, then our shell, then the sandboxed exhibit iframe.

Bigger option (not recommended now): rebuild the gallery as static assets in the application plugin and expose exhibit data through `register_method` RPC. This needs the web-channel RPC protocol reverse-engineered and a rewrite of the Python-generated HTML.

## Open questions (unverified)

- The origin the desktop shell uses (5173 or 19000), and whether a nested `http://127.0.0.1:<port>` frame loads there. The best check is a throwaway manifest-only plugin on a test profile; I deliberately did not install one.
- Whether plugins load only at startup (the code suggests yes).
- Whether the agent plugin's tool shares a process with the gateway. This decides whether `extension.py` could call `_ensure_server()` directly.
- Stability: this area has no third-party docs (only the video-duplex README), and `api_version: 1` could change.

---

## Addendum: tests against the v0.2.7 source (2026-11-09)

Source: `git clone` of tag v0.2.7 of github.com/openJiuwen-ai/jiuwenswarm into `Documents\workswarm-src\jiuwenswarm-0.2.7`.
The installed `extensions/` folder is identical to the repo's (diff), and `docs/zh/application-plugins.md` is the official doc for this system.

Test rig (throwaway, in the session scratchpad; nothing installed in WorkSwarm, no restart): a FastAPI app on 127.0.0.1:5199 that runs the
repo's real `ManifestApplicationPlugin` + `application_host.py` (with `openjiuwen`/registry stubbed), a fake host page that renders the
iframe exactly like `sVe` (no sandbox attr), a manifest-only plugin whose `frontend/dist/index.html` nests an iframe to our real
exhibit server (`exhibit_tool.py`, random port + token), with the URL handed over through `frontend/dist/url.json`.

| Theory | Result |
|---|---|
| Manifest-only `extension.yaml` plugin is accepted; manifest endpoint output | **Confirmed.** Real repo code produced `render_mode: iframe`, `entry_url: /api/application-plugins/exhibit-gallery/assets/index.html`, `nav_key: app:exhibit-gallery`. Asset route served `index.html` with `Cache-Control: no-cache`. |
| Iframe `src` can't be external; a static trampoline page can nest our server | **Confirmed.** host page -> plugin asset page -> `http://127.0.0.1:<random>/<token>/`. |
| Our `frame-ancestors 'none'` blocks the nested load | **Confirmed.** Chromium (built-in pane): `Framing 'http://127.0.0.1:25114/' violates ... "frame-ancestors 'none'"`, frame blank. |
| Relaxing `frame-ancestors` to the host origin fixes it | **Confirmed.** With `frame-ancestors http://127.0.0.1:5199` the full Exhibits gallery (rail, sidebar, New exhibit, search, cards) rendered inside the fake host. (CSP was patched in the test harness only; `exhibit_tool.py` is unchanged.) |
| `url.json` handoff works for a changing port/token | **Confirmed in the harness** (page fetched `url.json` and used it). Real-world staleness after a server restart is still untested. |
| Host origin is `http://127.0.0.1:5173` | **Confirmed from `main.cjs`**: `FRONTEND_HOST = '127.0.0.1'`, base port 5173, entry is `http://127.0.0.1:5173/?dt=<token>` and the window loads that. So the real `frame-ancestors` value to allow is `http://127.0.0.1:5173` (the port moves by +1000 per extra instance index; **multi-instance not tested**). No CSP in host `index.html`, none set in main.cjs (grep for frame-ancestors / CSP in the repo only hits IDE/browser webviews and an isolated-preview helper). |
| An exhibit (sandboxed sub-iframe) renders inside the nested gallery | **Inconclusive.** The exhibit iframe loaded (`onload` fired, 200, no CSP violation) but painted blank in the built-in browser pane, and it is *also* blank when the exhibit viewer is opened top-level there, so it's a pane rendering limit for opaque-origin sandboxed frames, not a nesting problem. The raw exhibit page itself is fine (text and button present). Needs a check in real Chrome or the real WorkSwarm window. |
| Real Electron window behaviour | **Not tested.** `main.cjs` window uses `sandbox: true, contextIsolation: true, webSecurity: true`; nothing there restricts nested iframes, but I did not run the app. |
| Web-channel RPC protocol / postMessage bridge | **Not examined this round.** |
