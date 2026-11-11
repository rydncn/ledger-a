# Handoff: trial complete

The third trial of the ai-playbook (`dfc984a`) is finished. Tally is built, reviewed, audited and merged (pull requests #1 to #13); this close (branch `close-out`) changed records only. Nothing here is "installed": a fresh session runs `scripts/setup-dev.sh`.

## What was built

A command-line tool that imports bank statements (CSV in each bank's layout; OFX in SGML and XML), removes duplicates, categorises transactions by the user's own rules and reports spending by month and payee, as a table, CSV or JSON. Python 3.15, standard library only, one SQLite data file the user alone can read, no network. Every acceptance criterion in `docs/design.md`, AC1 to AC44, has its tests; the suite is about 40 s with `-n auto`.

| Slice | Pull request | Branch |
| --- | --- | --- |
| 0, foundation: design, ADRs 0001 to 0008, hooks, CI, the draft Python pack, every gate broken once | #1 | `claude/new-session-xwzj72` (and the proof branch `proof/gate-breaks-1`, #2, never merged) |
| 1, accounts and the data file | #5 (plan, merged early), #6 (code) | `slice-1-accounts` |
| 2, CSV import | #7 (merged early), #8 (survivors and records) | `slice-2-csv-import` |
| 3, OFX import | #9 | `slice-3-ofx-import` |
| Whole-codebase review 1's fixes | #10 | `whole-codebase-review` |
| 4, categorisation | #11 | `slice-4-categorisation` |
| 5, reports | #12 | `slice-5-reports` |
| Whole-codebase audit and review 2, their fixes, ADRs 0011 and 0012, the agent configuration | #13 | `final-review` |
| The close: totals and summaries, records only | this pull request | `close-out` |

## Where each record is

- **`docs/effort.md`**: one row per session and, at the end, the totals: 7 sessions (8 started), 46 subagent sessions, peak context per session, about 11 h wall clock of which about 1 h 15 was a stall and about 9 h 50 working time, and a note on rule 17's budget (passed in every session, by 1.7 to 4.4 times).
- **`docs/trial-log.md`**: every defect by slice and layer, one line each, and at the end the totals by layer, severity and outcome, which layer found what no other did, and how each ambiguous line was counted. 203 findings in all: 183 fixed, 6 ruled or decided, 14 left for the owner; 41 equivalent mutants ruled by pragma; 24 gate breaks.
- **`docs/playbook-feedback.md`**: where the playbook was wrong, slow or missing something, as it happened, by session, with a summary by theme at the top.
- **`docs/python-pack/README.md`** and the files beside it: the draft Python stack pack, identical to the live copies at the close. Still a draft: one project has used it.
- **`docs/design.md`**: the design and the acceptance criteria as amended (AC13, AC20, AC32, AC35). **`docs/decisions/`**: ADRs 0001 to 0012. **`docs/plans/`**: one plan per slice with what each task observed; all done, none active. **`docs/review-brief.md`**: the brief every reviewer and the audit were given.
- The whole-codebase audit's own files (REPORT.md, findings.json, coverage-ledger.json) were outside the repository, in the session's home directory, and are gone with its container. The trial log's "Security audit (whole codebase)" section and pull request #13 carry what they found.
- Each pull request's description records its door kind, its review and its rulings.

## What is left for the owner

Housekeeping on the repository:

- **Merge or close Dependabot's #3** (`astral-sh/setup-uv` 9.0.0 to 10.3.3) **and #4** (`uv-build` to `>=0.13.7,<0.14`). Both are one-way doors by the project's rule (a dependency and a release setting); neither was touched by the trial.
- **Delete the branch `proof/gate-breaks-1`**, which holds the planted secrets-scan token (pull request #2, closed, never merged). A cloud session cannot delete a branch; the scan's `--log-opts=HEAD` has kept the token out of every other run meanwhile.
- **Delete the merged branches**: `claude/new-session-xwzj72`, `slice-1-accounts`, `slice-2-csv-import`, `slice-3-ofx-import`, `whole-codebase-review`, `slice-4-categorisation`, `slice-5-reports`, `final-review`, and `close-out` once this pull request is merged.
- **Pin the plugin marketplace**: `extraKnownMarketplaces` in `.claude/settings.json` follows `rydncn/ai-playbook`'s default branch (whole-codebase review 1, audit hardening note, R12).
- **Branch protection**, if ADR 0007 is to have a mechanism: two draft pull requests were merged before the agent marked them ready (#5, #7). A required status check, or a CI step that fails while the description says "not ready", would give the rule teeth.

Decisions about the product, raised by the reviews and the audit and not taken:

- **Windows** (audit A9, needs validation): the data file's privacy rests on the inherited ACL, and the "tightened" notice would show on every open there. No Windows host ran in the trial. Either test it (the audit's report had a VM plan, now lost with the container; the finding in the trial log says what to try) or declare Windows outside AC6.
- **Commands that only read create an empty data file** (review 2's R13): a mistyped `--data-dir` reports nothing instead of refusing. Changing it changes the command line's contract.
- **`uncategorised` collects every row before printing** (AC34; slice 4's review, R11): memory grows with the data. AC34 requires it as written.
- **OFX**: a file with no `CURDEF` takes the account's currency, and the OFX `ACCTID` is compared with nothing, because a Tally account has no bank account number (slice 3's review, audit hardening).
- **A rule's `account` is not checked against the accounts**, because the rules are validated before the data file opens (slice 4).
- **`account forget` keeps no tombstone** (slice 1).
- **The store keeps up to 1,000 unreadable rows** in memory for the summary (AC13 and AC20 as amended by #10).
- **`seen` holds every distinct description per file** during an import, about four times the file (audit hardening).
- **A layout's `decimal` may be a digit** (audit hardening); **`check_imports.py`'s ignore marker exempts a whole line** (audit hardening); **the mutation group's build requirements are not hashed** (audit hardening, ADR 0003's one exception).
- **A data directory on a network or synced folder** is undecided (whole-codebase review 1).
- **Wide (CJK) characters misalign the tables**: cosmetic, accepted (slice 3).
- **Slow tests**: if the suite passes 90 s, move the slow acceptance tests (the AC8 lock waits, AC18 under `tracemalloc`) behind a marker the stop hook skips and CI runs, and record the ADR.

Agent configuration, as merged in #13 and to be read by a person (ADR 0007 asked this before #13 was merged; recorded here in case it was not):

- `.claude/settings.json`: the ask rules for pushes, merges and `gh api` writes, the `pip-audit*` allow rule removed, the GitHub MCP tools that merge, push files or make branches asking first.
- `.claude/checks.json` and `.claude/hooks/pre-push`: the rule and import checks before stop and before push; `pre-push` refuses `main` and `master` whatever the command.
- A plain push of a named branch does not ask first, and nor does the GitHub tool that edits a pull request's description or marks it ready; `CLAUDE.md` says so. Making them ask would stall an unattended session on its own pushes.

For the playbook, which this session did not touch (the owner does that):

- the Python pack in `docs/python-pack/` for `templates/stacks/python/`, and `docs/playbook-feedback.md`'s summary for the playbook's own records;
- the lessons in `CLAUDE.md` that are not Tally-specific (the `chr()` rule, the shell-edit blind spot, the pragma on its own line, `origin/main` in a fresh checkout, grepping the codebase when a lesson is added).

The comparison of this build with the one made without the playbook is the independent reviewer's, not this repository's.

## Decisions taken that a later session should not reopen

Every ADR in `docs/decisions/`, and from the slices:

- exit codes and streams (1 refused, 2 configuration, 3 locked; errors to standard error); the busy timeout; ADR 0008's fingerprint; the sign rule for money-out columns; the encoding allowlist; the 1 MB field and 2 MiB line and record guards; OFX read by Tally's own scanner; reports summed in Python integers;
- an amount has its currency's own decimal places in every form (ADR 0011); only a Unicode `Sc` character before an amount is a currency symbol;
- a fingerprint already stored with a different date or amount is an unreadable row, not "already there" (ADR 0012);
- the data directory must be the user's own and writable by no one else; a pre-existing one is refused, never chmodded; every data and side file in it absent, or the user's own regular file with one link;
- a pattern searches a description's first 1,000 characters; a date format with no separators reads only its own width; `forget` uses `secure_delete`;
- every message, argparse's and logging's included, goes through `printable`; a closed pipe ends quietly with exit 1; account and rule names refuse what `printable` would change, and no rule is named `uncategorised`; configuration errors are all exit 2.
