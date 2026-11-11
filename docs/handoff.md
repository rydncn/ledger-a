# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slices 0 to 5** are merged: pull requests #1 to #12. Every criterion, AC1 to AC44, has its tests.
- **The last review step** is pull request [#13](https://github.com/rydncn/ledger-a/pull/13), on `final-review`. It holds:
  - the security audit of the whole codebase: 7 low findings fixed; of 2 that need validation, 1 ruled by removing the rule and 1 left for the owner;
  - whole-codebase review 2: 13 findings, 3 must-fix, 9 fixed or decided, 4 ruled or left for the owner;
  - a fresh-context review of the pull request's own diff: 6 should-fix, all fixed (one in part, with a ruling);
  - the handoff's three items;
  - ADR 0011 (amounts in the currency's own places) and ADR 0012 (a FITID reused for a different transaction is reported);
  - the agent-configuration changes.
- Every finding, by layer, is in `docs/trial-log.md` under "Security audit (whole codebase)", "Whole-codebase review 2" and "The fixes". The audit's own files are outside the repository (`~/security-audit-skill/ledger-a/run-1/`: REPORT.md, findings.json, coverage-ledger.json), so a fresh container will not have them. The trial log and the pull request carry what they found.
- **The owner merges #13** (ADR 0007) after reading the agent-configuration files.

## Next: the trial's close (a separate session)

1. Total the records. Leave the numbers here alone and work them out from the files:
   - `docs/effort.md`, one row per session (slices 0 to 5, and "Audit and review 2"): sessions, peak context, wall clock and working time;
   - `docs/trial-log.md`, by layer: tests seen failing, hooks, rule and import checks, gate breaks, each fresh-context review, each security audit, mutation testing, process. Count findings by severity and by what was done with each (fixed, ruled, for the owner);
   - which layer found what no other layer did. Each audit and review section names its overlaps.
2. Summarise `docs/playbook-feedback.md`. It is grouped by session. Session 7 covers:
   - the security-audit skill's cost for a project this size;
   - the sandbox and the promotion code the skill needs but does not ship;
   - Phase 5 catching a fix that was already pushed;
   - the overlap between the audit and the review;
   - the `chr()` lesson broken a third time;
   - rule 17's budget at a close.
3. Bring `docs/python-pack/README.md` into `templates/stacks/python/` if the owner wants it in the playbook. It is up to date as of #13.
4. Compare this build with the one made without the playbook, as the trial's owner asks.

## For the owner

- **Read before merging #13**:
  - `.claude/settings.json`: new ask rules, the `pip-audit*` allow rule removed, MCP tools asking first;
  - `.claude/checks.json`: the rule and import checks before stop;
  - `.claude/hooks/pre-push`: it refuses `main` and `master`, and runs the rule and import checks;
  - `CLAUDE.md`: what asks first, and the security boundary on amount places.
- **Pin the plugin marketplace** (`extraKnownMarketplaces` in `.claude/settings.json` follows `rydncn/ai-playbook`'s default branch). Not done from here.
- **A plain push of a named branch does not ask first**, and nor does the GitHub tool that edits a pull request's description or marks it ready. `CLAUDE.md` now says so. Making them ask would stall an unattended session on its own pushes. The `pre-push` hook refuses `main` and `master` whatever the command.
- **Windows** (audit A9, needs validation): the data file's privacy rests on the inherited ACL, and the "tightened" notice would show on every open there. The audit report has a VM plan. Either test it or declare Windows outside AC6.
- **Commands that only read create an empty data file** (review R13). A mistyped `--data-dir` therefore reports nothing instead of refusing. Changing this changes the command line's contract.
- **`uncategorised` collects every row before printing** (AC34; review R11). Memory grows with the data.
- **An OFX file with no `CURDEF`** takes the account's currency; the OFX `ACCTID` is compared with nothing.
- From before:
  - a rule's `account` is not checked against the accounts;
  - `account forget` keeps no tombstone;
  - the store keeps up to 1,000 unreadable rows for the summary;
  - a data directory on a network or synced folder is undecided;
  - wide (CJK) characters misalign the tables.
- The suite takes about 40 s with `-n auto` (about 65 s serial).

## Decisions taken that the next session should not reopen

- Everything in the earlier handoffs (exit codes and streams, the busy timeout, ADR 0008's fingerprint, the sign rule, the encoding allowlist, the 1 MB field guard, OFX read by Tally's own scanner, reports in Python integers).
- From #13:
  - **Amounts:** an amount has its currency's own decimal places in every form (ADR 0011). Only a Unicode `Sc` character before an amount is a currency symbol.
  - **Duplicates:** a fingerprint already stored with a different date or amount is an unreadable row, not "already there" (ADR 0012).
  - **The data directory:** it must be the user's own, and writable by no one else. A pre-existing one is refused, never chmodded. Every data and side file in it must be absent, or a regular file of the user's own with one link.
  - **CSV records:** one record is bounded as one 2 MiB line is.
  - **Patterns:** a pattern searches a description's first 1,000 characters.
  - **Compact dates:** a date format with no separators reads only its own width, month names in any case.
  - **`forget`** uses `secure_delete`.
  - **The terminal:** every message, argparse's and logging's included, goes through `printable`. A closed pipe ends quietly with exit 1.
  - **Names:** account and rule names refuse what `printable` would change. A rule cannot be named `uncategorised`. `forget` and `import --account` look a name up as given.
  - **Configuration errors** are all exit 2.
