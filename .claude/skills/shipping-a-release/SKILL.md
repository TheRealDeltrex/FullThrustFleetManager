---
name: shipping-a-release
description: Ship a Full Thrust Fleet Manager release - version bump, Windows build, GitHub release, Pages deploy, and the landing page that has to end up telling the truth. Use when asked to ship, cut a release, build the exe, or deploy the online build.
---

# Shipping a release

Read this only when actually shipping. CLAUDE.md holds the rule that **`main` is for releases
only and is never pushed without the owner**, and that applies here too: this file is the
mechanics, not the permission. Tags and GitHub releases are the owner's.

## The shape of it

Version is single-sourced from `pyproject.toml` `[project] version`, read at runtime by
`paths.app_version()` and shown in the top bar. Nothing else stores a version number; the
landing page's badges are filled in at deploy time, never by hand.

**A release is tagged on `devversion`. Nothing is merged into `main`.** `main` carries only
`README.md`, `LICENSE`, `NOTICE.md`, `.gitignore` and `.github/workflows/`, and the only reason
it carries those workflow files is that GitHub will not offer a `workflow_dispatch` workflow
unless it exists on the **default branch**, which `main` is. Everything else lives on
`devversion`. (v0.1.0 and v0.1.1 predate this and were cut by merging into `main`; their tags
still point at commits that carry the whole source, which is why the history looks different
before that point.)

Check `gh release list` before picking a tag; a tag is never reused.

**The order below matters.** The two version badges on the landing page each state the truth
about their own channel, which is the point of them:

- **online** = the `pyproject.toml` of the branch the Pages site was built from.
- **windows** = the newest release that actually has a `-win64.zip` attached.

So a Pages deploy that runs before the zip is attached stamps the Windows badge with the
*previous* version and needs a second dispatch to correct. Deploy Pages **last**.

## 1. Bump the version

On `devversion`, in its own commit: `pyproject.toml`, and the status line in `README.md` if it
names the version. Then `.venv/Scripts/python.exe -m ruff check .` and the full suite — a
release is the one time running everything locally is the right call rather than the targeted
tests CLAUDE.md asks for day to day.

## 2. Build and check the Windows exe

PyInstaller cannot cross-compile, so this is local and manual:

```bash
.venv/Scripts/python.exe -m PyInstaller --noconfirm fleetmanager.spec
```

That produces a **onedir** build at `dist/FullThrustFleetManager/` (~63 MB; the rulebooks and
pdf.js are most of it).

### Sign it, then package it

In that order: the signature goes on the exe inside `dist\FullThrustFleetManager\`, and signing
the zip instead would do nothing for the user.

Sign with the same self-signed `CN=Deltrex, O=Deltrex, C=DE` certificate the Frostgrave project
uses (expires 2036-08-05). There is no Windows SDK / `signtool.exe` on this machine, so use the
PKI cmdlets.

The key lives in the Windows certificate store, and that is the copy to use — do not copy the
`.pfx` into this repo. It is passwordless, so a stray commit would publish a working signing
key; `.gitignore` blocks `.codesign/` as a guard in case one ever lands there anyway.

**Select it by thumbprint.** There are two `Deltrex` certificates in `Cert:\CurrentUser\My`, and
matching on the subject returns both. The older one (`CN=Deltrex`, no `O`/`C`, expires
2031-07-29, thumbprint `F76A92DB…`) is the `OLD-lostpw` key and must not be used.

```powershell
$cert = Get-Item "Cert:\CurrentUser\My\723FEAB2277DA6FB30EB99D5105CAA4ED98057E2"
Set-AuthenticodeSignature -FilePath "dist\FullThrustFleetManager\FullThrustFleetManager.exe" `
  -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com"
```

**`Status` comes back `UnknownError`, and that is the expected result** — it is the
untrusted-root complaint for a self-signed certificate, not a failure. Confirm the signature
really landed by checking the subject and that it was timestamped, which is what keeps it valid
after the certificate expires:

```powershell
$v = Get-AuthenticodeSignature "dist\FullThrustFleetManager\FullThrustFleetManager.exe"
$v.SignerCertificate.Subject          # CN=Deltrex, O=Deltrex, C=DE
$null -ne $v.TimeStamperCertificate   # True
```

If the store is ever empty (fresh machine), re-import from Frostgrave's
`.codesign\Deltrex-CodeSigning.pfx` with an empty `SecureString` as the password, or regenerate
with `New-SelfSignedCertificate -Type CodeSigningCert` and export passwordless.

The certificate exists so Windows shows "Deltrex" rather than "Unknown Publisher". **SmartScreen
still warns**, because the root is not trusted and the binary has no reputation; the owner has
accepted that, and `web/landing.html` says so.

Note that **v0.1.1 shipped unsigned** (`Get-AuthenticodeSignature` on the published asset reports
`NotSigned`), so the first signed release is also the first one whose landing-page note is true.

Only once it is signed, zip it. The published zip holds the build folder's **contents** at its
root, `FullThrustFleetManager.exe` next to `_internal\`, not the folder itself, so the user
unzips anywhere and runs the exe they can see. Name it exactly
`FullThrustFleetManager-<version>-win64.zip`: `scripts/stamp_landing_page_versions.py` finds the
download by that `-win64.zip` suffix and reads the version from the release tag, so a misnamed
asset silently leaves the card unstamped.

```powershell
Compress-Archive -Path "dist\FullThrustFleetManager\*" `
  -DestinationPath "dist\FullThrustFleetManager-<version>-win64.zip" -Force
```

Smoke-test the built exe before releasing it. **Do the whole thing in one command**:
`idle_watchdog` exits the process 180 s after the last browser heartbeat and nothing here sends
one, so an exe left running across a few tool calls is simply gone, with a healthy-looking
"Serving on ..." as the last thing it said. Use an isolated `FTFM_DATA_DIR` and a non-default
`PORT`, and stop it **by PID from the port**, never by process name. Worth hitting: `/`,
`/design`, a catalog design's workbench (the SSD), `/fleet`, `/campaign`, a rulebook page (the
one thing that proves the PDFs got bundled) and a fleet PDF.

## 3. Tag and release

Owner's call, every time. Tag `vX.Y.Z` on `devversion`, push the tag, then create the release
and attach the zip:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z dist/FullThrustFleetManager-<version>-win64.zip \
  --target devversion --title "vX.Y.Z" --notes "..."
```

`main` is not touched. It only ever changes when the README, the licence or a **workflow file**
changes — and a workflow file changing on `devversion` is the one case where `main` genuinely
has to be updated too, or the dispatchable copy goes stale. See step 4 for why that bites.

## 4. Deploy Pages, last

```bash
gh workflow run deploy-pages.yml --ref devversion -f ref=devversion
```

**Pass `--ref devversion` as well as `-f ref=devversion`.** They do different jobs and both
matter: `-f ref=` is an *input* the checkout step consumes, while `--ref` selects **which
branch's copy of the workflow file runs**. Without it GitHub runs `main`'s copy, because `main`
is the default branch.

That is not academic. Note what the two do together: the checkout step takes `ref` as an
**input** defaulting to `devversion`, so `main`'s copy of the workflow runs against
`devversion`'s *source*. The source is therefore never the problem — the **steps** are. A
`main` copy that is missing a step just silently does not run it, against perfectly good source,
and the site deploys looking almost right. That is exactly how Frostgrave's landing page sat at
`vDEV` through several deploys.

Since nothing is merged into `main` any more, **`main`'s copy of a workflow file is only ever
updated deliberately**. If you change `.github/workflows/deploy-pages.yml` on `devversion`, copy
it to `main` in the same breath, or the dispatchable version quietly goes stale. Passing
`--ref devversion` sidesteps the whole question, so do that as well.

Afterwards, open the deployed site and check the badges actually moved. A stamp step that fails
does not fail the deploy: it warns and leaves the page as it was.

## The landing page

`web/landing.html` is the site root; the Pyodide app sits under `app/`. Three things finish it,
and they are the reason it should never need hand-editing at release time:

- **Badges and download links** — `scripts/stamp_landing_page_versions.py`, from the releases
  API, per channel. A platform with no release asset at all **loses its whole card** rather than
  publishing a `vDEV` badge over a dead button, so nothing has to be commented out by hand.
- **Preview pages** — `scripts/build_preview_pages.py` renders `preview-design.html` and
  `preview-fleet.html` from the real app through its test client, so they cannot drift from the
  templates or the rules engine.
- **The prose** — this is the part with no build step, and it is the part that rots. The page
  claimed 96 catalog designs for the whole of the alien-race work. `tests/test_landing_page.py`
  now fails if the stated ship-class count or the named races disagree with the app, so a
  release cannot quietly ship a page describing the previous one. **When a release adds
  something the page should boast about, add the line and let the test catch the number.**

## Linux

**Parked, and never yet released.** `fleetmanager-linux.spec` and `.github/workflows/build-linux.yml`
exist and are inert: the workflow is `workflow_dispatch` only, and with no `-linux-x64.tar.gz` on
any release the stamp script drops the Linux card from every deploy, so the published page does
not mention it. Do not dispatch it as part of a release unless the owner asks for a Linux build
specifically. If one is ever cut, attach it to an **already-existing** release — the workflow
uploads to a tag, it does not create one — and the card appears on the next Pages deploy by
itself.

## Web build specifics

Architecture is in CLAUDE.md's Web build section. The parts that bite at release time:

- **Any Python change requires regenerating `bundle.json`** — the bundle embeds a copy of the
  source. Easy to forget for a change that "isn't a browser thing". CI rebuilds it on deploy, so
  this matters for local verification, not for the deployed site.
- `bundle.json` is **text only**. Binary files the Python side opens (the PDF's TTFs) are fetched
  by the shell into the Pyodide filesystem under `/app`.
- Verify persistence by reloading the page, not by first render.
