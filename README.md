# Full Thrust Fleet Manager — source

This is the working branch. Everything about the app, and the way to get it, is on
[**main**](https://github.com/TheRealDeltrex/FullThrustFleetManager) and at the
[**download page**](https://therealdeltrex.github.io/FullThrustFleetManager/).

`main` carries only that README, the licence and the workflow files. All the source is here.

## Working on it

Read [CLAUDE.md](CLAUDE.md) first; it is the operating manual and it is current. The build plan
is [docs/PLAN.md](docs/PLAN.md). Needs Python 3.11 or newer.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe app.py
```

Then open <http://127.0.0.1:5000/>. Data is kept in `userdata/` next to the checkout; set
`FTFM_DATA_DIR` to put it elsewhere. `python -m pytest` and `ruff check .` before committing.

Shipping a release has its own procedure in
[.claude/skills/shipping-a-release/SKILL.md](.claude/skills/shipping-a-release/SKILL.md).

Licensed GPL-3.0. Ground Zero Games content notice in [NOTICE.md](NOTICE.md).
