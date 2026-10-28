# Desktop and web builds

Read before changing `scripts/`, `web/`, the PyInstaller specs or `.github/workflows/`.
Releasing is `.claude/skills/shipping-a-release/SKILL.md`.

## Web build (Pyodide on GitHub Pages)

- The web build runs the real app through Flask's test client in an iframe `srcdoc`, so
  absolute `/static/...` URLs don't resolve there: `web/index.html`'s `renderPage()` inlines
  every `static/*.css` / `*.js` by file name. Only text passes through `bundle.json`; binary
  assets and the rulebooks are copied next to `index.html` by `deploy-pages.yml`. The shell
  rewrites `url("fonts/` and `url("themes/` to `static/` paths when it inlines CSS; keep that
  spelling in CSS assets. Portrait HTML uses `art_url` for desktop/web paths.
- `build_browser_bundle.py` globs modules, templates, `data/`, `translations/` and static text
  files; `fleetmanager.spec` adds whole folders. Neither keeps a hand list (Frostgrave's drifted
  and shipped broken). New top-level desktop-only modules go in `EXCLUDED_MODULES`.
- The shell stamps a content hash into its `bundle.json?v=` URL on each build; commit it with
  the `__BUNDLE_VERSION__` placeholder, not a hash.
- `FTFM_BROWSER=1` turns off the local-host guard (no network hop in the page).
- `bundle.json` is **text only**. Binary files the Python side opens (the PDF's TTFs) are
  fetched by the shell and written into the Pyodide filesystem under `/app` (`BINARY_ASSETS` /
  `copyBinaryAssets` in the shell). Add to that list when the app starts reading another binary.
- Flask routes do not exist for anything outside the page: pdf.js must be pointed at
  `/rulebooks/<file>.pdf` in `BROWSER_MODE`, not at `/rulebook/<code>/file`.
- An inline binary response (the fleet PDF) is opened from a blob in a new tab; an attachment is
  downloaded.
- Try it locally: `python scripts/build_browser_bundle.py`, then serve a copy of what
  `deploy-pages.yml` assembles: `web/index.html`, `web/bundle.json`, `static/`, `rulebooks/` in
  one folder (`python -m http.server`).
- The deployed site has two levels: `web/landing.html` becomes the site root (`index.html`) and
  the app sits under `app/` with its `static/` and `rulebooks/`. The landing page reads its logo
  and fonts from `app/static/`, so the site carries one copy. Two steps run on every deploy:
  - `scripts/build_preview_pages.py _site` writes `preview-design.html` and
    `preview-fleet.html`, the "See it in action" snapshots, **rendered from the real app through
    its test client** so a preview cannot drift; sanitising rewrites `/static/` to `app/static/`
    and injects a script that inerts every form and internal link.
  - `scripts/stamp_landing_page_versions.py _site/index.html` fills the version badges and the
    download links from the newest release carrying each platform's asset (`-win64.zip`,
    `-linux-x64.tar.gz`). A platform with no release at all **loses its whole card** rather than
    publishing a vDEV badge over a dead button. An unreachable API changes nothing.
- Keep the `data-version-badge` / `data-download` / `data-platform-card` markers in
  `landing.html`: `tests/test_landing_page.py` holds that contract.
- `tests/test_web_boot.py` boots the built site in headless Chromium and saves a fleet. It needs
  Playwright and the network, so it is skipped unless `FTFM_WEB_BOOT=1`; the Tests workflow's
  `web-build` job sets that.
- Deployment is manual (`deploy-pages.yml`, workflow_dispatch) and belongs to the owner.

## Desktop build

- `.venv/Scripts/python.exe -m PyInstaller --noconfirm fleetmanager.spec` produces a onedir
  build at `dist/FullThrustFleetManager/` (~63 MB; the rulebooks and pdf.js are most of it). The
  spec adds whole folders, so new static or data files need no edit there.
- `fleetmanager-linux.spec` is the Linux build, made by `build-linux.yml` rather than by hand:
  **onefile** (one file to `chmod +x` for a non-technical user), with `tray` excluded, since
  `main()` only reaches the tray icon on win32 and pystray would drag in GTK/X11. Keep the two
  specs' `datas` in step; the Linux workflow's smoke test catches a folder one of them forgot.
  Dispatch it with a release tag to attach the tarball, or without one for a bare artifact.
- Verifying a build: run the exe with `PORT` and `FTFM_DATA_DIR` pointed at a scratch dir, then
  exercise it over HTTP. **It opens a browser tab on launch**, and that tab's heartbeat keeps the
  idle watchdog from exiting, so stop a test instance by PID from the port (never by process
  name), not by waiting for the watchdog.
