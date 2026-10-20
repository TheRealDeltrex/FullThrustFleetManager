# AGENTS.md

Read `CLAUDE.md` first and follow it. It is the operating manual for every agent on this
project (Codex included): conventions, architecture, testing, git rules. `docs/PLAN.md` says
what is built. This file only adds how Codex and Claude work together; it does not repeat
`CLAUDE.md`.

## Working alongside Claude

- `devversion` is the only branch with source. Start every piece of work on a new branch off
  the latest `devversion` (e.g. `codex/<topic>`), never on `devversion` or `main` directly.
- Open a pull request into `devversion`. Claude reviews it and merges it once CI is green,
  like any other PR.
- Notes for Claude (what changed, open questions, what is left for a later PR) go in the PR
  description or PR comments, not in local files. Read Claude's review comments there too.
- The owner's checkout (`E:\ClaudeCodeFolder\FullThrustFleetManager`) is shared with Claude
  sessions. Commit or stash before switching branches; never switch, pull or reset with
  uncommitted changes in the tree.
- Ship artwork is stored as WebP; keep original PNGs out of the repo
  (see `docs/SHIP-ARTWORK.md`).
- If you change anything `CLAUDE.md` describes, update `CLAUDE.md` in the same PR.
