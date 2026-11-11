# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slices 0 to 4** merged: foundation (#1), accounts and the data file (#6), CSV import (#7, #8), OFX import (#9), the first whole-codebase review's fixes (#10), categorisation (#11, merged by the agent at the owner's explicit request once every CI job was green; ADR 0007 has the owner merge, and this was the owner's delegation).
- **Slice 5 (reports)** is pull request [#12](https://github.com/rydncn/ledger-a/pull/12) on `slice-5-reports`: `report.py` (`monthly`, `payees`, Python-integer sums, ADR 0010), `tally report` and `tally payees` with `--month` or `--from`/`--to` and table, CSV and JSON forms, `account list --format csv`, colour on a terminal only, CSV `\r\n` on every platform. The plan is `docs/plans/005-reports.md`; the audit, the review, their rulings and the mutation results are in #12's description. **The owner merges #12** (ADR 0007), once every CI job is green on its final commit.
- Every criterion in the design, AC1 to AC44, now has its tests.

## Next: the whole-codebase review (review 2), then the trial's close

The playbook asks for one every few slices; the last ran after slice 3, and slice 5's session had no budget left for it.

1. New session, branch from `main` after #12 merges (`whole-codebase-review-2`), `scripts/setup-dev.sh`, `git fetch origin main`, `git config user.name` and `user.email`. Push with `git push origin <branch>`, never bare.
2. A subagent in a worktree of `main` with `docs/plans/`, this file and the trial records (`docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`) removed, given `docs/review-brief.md`, `CLAUDE.md`, `docs/design.md`, `docs/brief.md` and the ADRs, scope "the whole repository at <commit>", the four questions by name, reading the slices together. Name the parsers: the spreadsheet (every CSV command), the terminal (every path to standard output and standard error, argparse's own messages included), `strptime` (CSV dates, OFX dates, months), `Decimal`, SQLite, `re` on the user's patterns, the OFX scanner, the codecs.
3. Start it with these, which the slice 5 audit raised and left for this review:
   - argparse prints an unrecognised argument raw (`tally report --month 2026-10 $'\x1b]0;x\x07'`); the user's own command line, but every other message goes through `printable`. One `ArgumentParser.error` override in `cli.py` would cover it.
   - `tally uncategorised --format csv | head` exits 1 with `cannot open the data file: Broken pipe: None`: the `OSError` branch in `main` takes standard output closing for a data-file error.
   - No check catches a raw C0 control character (ESC) written into source; ruff catches only the bidi overrides (`docs/playbook-feedback.md`, slice 5). A rule check would make the `chr()` lesson a gate.
4. Fix findings test-first, one pull request; a mutation run on the changed files; records as for a slice (`docs/effort.md` gets a row for the review).
5. **The trial's close:** whatever the trial's owner asks for comparing this build with the one made without the playbook. The records are `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`.

## Decisions taken that the next session should not reopen

- Everything in the earlier handoffs: exit codes and streams, the 10-second busy timeout, the fingerprint of ADR 0008, the sign rule, subprocess tests kill no mutants, the data directory order, unreadable rows on standard error (50 and then a count), the encoding allowlist, the 1 MB field guard, OFX read by Tally's own scanner, `to_minor` bounded before `int()`, the rules' shapes, AC38's replacements, `explain`'s id.
- **Reports (slice 5):** months are `[0-9]{4}-(0[1-9]|1[0-2])` in full (never `strptime`); `--month` or both `--from` and `--to`, inclusive, else exit 2 before the rules or the data file; only months with transactions get a section; sums are Python `int`s, never SQLite `sum` or `Decimal` arithmetic (ADR 0010); rows keyed by currency and scale, no grand total; uncategorised is `null` in JSON, an empty cell in CSV and `uncategorised` in the table; payees are money out only, grouped by the exact description, per currency, ties by description, `--top` 1 to 1000 (default 10); the payees table shortens a description to 60 characters; `payees` reads no rules.
- **CSV:** `\r\n` everywhere, by reconfiguring a text stream with `newline=""` before writing (the slice 4 review's F2); text cells through `_cell`, amounts never prefixed.
- **Colour:** table only, red on negative amounts after the padding, only when standard output is a terminal and `NO_COLOR` is absent (any value, empty too, turns it off).

## Open

- For the owner, raised by slice 4's review and again by slice 5's audit and review: AC32, AC35 and `CLAUDE.md` say amount cells have two decimals (`-?\d+\.\d{2}`), but a JPY amount is `1234` and a BHD one `1.234`. The code uses each currency's own places, exactly; the criteria and the rule should say so, or the code should change. Both reviewers recommend amending the criteria.
- For the owner: `uncategorised` collects every row before printing (AC34); memory grows with the data.
- For the owner: a rule's `account` is not checked against the accounts, because the rules are validated before the data file opens.
- From slice 1: `account forget` keeps no tombstone.
- From the slice 3 review: the OFX `ACCTID` is compared with nothing; a file with no `CURDEF` takes the account's currency; the store keeps every unreadable row for the summary up to 1,000.
- The full suite takes about 65 s. If it passes 90 s, move the slow tests behind a marker the hook skips and CI runs, and record the ADR.
- From the first whole-codebase review, for the owner (agent configuration, unchanged): the "ask first" rules in `.claude/settings.json` miss some push and merge forms; the plugin marketplace is not pinned; `check-rules.js` and `check_imports.py` run only in CI. Also undecided: a data directory on a network or synced folder.
- The table's column widths count characters, so wide (CJK) characters misalign; cosmetic, accepted.
