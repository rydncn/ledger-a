# Handoff

Where the work is, for the next session. The work, not the machine: tools come from the environment's setup script, never from here.

## Where we are

- **Slice 0 (foundation)** merged as pull request [#1](https://github.com/rydncn/ledger-a/pull/1); **slice 1 (accounts and the data file)** merged as [#6](https://github.com/rydncn/ledger-a/pull/6).
- **Slice 2 (CSV import)** is pull request [#7](https://github.com/rydncn/ledger-a/pull/7), branch `slice-2-csv-import`, awaiting the owner's merge (ADR 0007). It delivers `importers/__init__.py` (the row outcomes, the whole-file refusal, which importer reads a file), `importers/csv_layout.py` (the layout from `[layouts.<name>]`, the streamed reader, the ADR 0008 fingerprint), `Store.import_transactions` and `tally import`; criteria AC5, AC9 to AC20, AC40, AC42, AC43, AC34 and AC35 for `import`, AC7 and AC8 re-proved through `import`. The plan with what each task observed is `docs/plans/002-csv-import.md`; the review's findings and rulings are in the pull request.
- **Next: slice 3**, OFX import: AC21 to AC25, AC39, AC41. **After it: the whole-codebase review** (every slice read together, `docs/review-brief.md`), and before the final review `/security-audit`.

## How a slice goes

1. New session, new branch from `main` (`slice-3-ofx-import`), `scripts/setup-dev.sh`. Set `git config user.name` and `user.email` in the checkout. Push with `git push origin <branch>`, never bare.
2. Plan in `docs/plans/003-ofx-import.md` from `002-csv-import.md`'s shape: the decisions taken, then `### Task N:` headings, each with the failing test first, the criteria it satisfies and an "Observed by" filled in as it happens. Open the draft pull request with the plan in the description and the door kind; its first line says it is not ready to merge.
3. Test-first per task: tests named `test_acNN_...` in a file per behaviour group (`tests/test_csv_layout.py` for the importer alone, `tests/test_import.py` for the command, are the pattern); in-process `main(argv)` for behaviour, one subprocess test per behaviour group (ADR 0002). `tests/test_import.py::Place` gives a test its own config with the two sample layouts, data directory and two accounts; add the `savings` account there or beside it. The after-edit hook runs ruff on every Edit and Write (it did this slice, now that files go through those tools); it reports each intermediate state of a multi-edit response, so finish the response and then run the checks once.
4. Before marking ready: `UV_NO_BUILD=0 uv sync --locked --group mutation` then `uv run python scripts/mutation_changed.py origin/main` (about 25 minutes for four changed files; run it in the background); the fresh-context review from `docs/review-brief.md` by a subagent given only the diff, `CLAUDE.md`, `docs/design.md`, `docs/brief.md` and the ADRs, told not to read `docs/plans/` or this file; for a parser, name the other parsers it must ask about (for OFX: the SGML reader Tally writes, `xml.etree` or whatever reads the XML, the codecs, the `CHARSET` header, `strptime` on `DTPOSTED`, the terminal). Findings fixed test-first or ruled on in the pull request.
5. Records: `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md`. Peak context from the transcript with the script in `docs/python-pack/README.md` § "Measuring a session".
6. Handoff here, push, mark ready once CI is green, ask the owner to merge.

## What slice 3 builds on

- **The importer contract** is `importers/__init__.py`: an importer is `read(path, ..., scale) -> Iterator[Transaction | Unreadable]`, raising `NotAStatementError` for the whole file (exit 1). `Transaction(line, date, description, amount_minor, fingerprint)`; for OFX the fingerprint is `ofx:<FITID>` (ADR 0008) and `line` is the transaction's position (AC25 says `transaction 2: ...`, so the `Unreadable` message for OFX needs its own prefix: `cli.py` prints `line {n}: {reason}` today; make the prefix the importer's, or give `Unreadable` the word). `kind(path)` already returns `"ofx-sgml"` and `"ofx-xml"` from the first bytes; `cli._import` refuses both with `OFX import is not available yet` and refuses `--layout` with them (exit 2): replace that branch.
- **AC39's DOCTYPE check** belongs before any XML parser sees the bytes: `kind` reads the first 1 KB, so a DOCTYPE check can live there or in the OFX importer's own header read. The design says the message is `the file declares a DOCTYPE, which statements never do`.
- **AC24's currency** comes from `CURDEF`; the account's is `Account.currency`. Refuse before `store.write()`: the lifecycle puts every whole-file refusal before the lock, but the OFX reader only meets `CURDEF` after opening the file, which is fine as long as nothing has been written (the import record is written inside the same transaction as the rows, so a `NotAStatementError` raised from the iterator inside `import_transactions` rolls everything back anyway; AC42's test is the proof of that path).
- **`Store.import_transactions(account, file, outcomes)`** is the one write; it takes any iterator of outcomes. A `NotAStatementError` raised by the iterator part-way propagates through `write()`'s rollback and `cli.main` maps it to exit 1.
- **The amount** text in OFX (`TRNAMT`) goes through `money.parse_amount(text, ".", ",")` then `to_minor(amount, scale)`; `12,34` is `amount is not a number` (AC25).
- **Encoding**: the SGML header has `ENCODING:USASCII` and `CHARSET:1252`; decide once what to honour and record it in the plan. The CSV reader's `_Lines` guard (2 MB per physical line, drained in chunks) is the pattern for bounding a hostile file; AC41's depth limit (64) and 10,000 nested tags need their own bound in the SGML reader.
- **Messages carry no content.** The CSV reader's reasons are fixed strings plus a number or the layout's own `date_format`; AC19's test imports marker strings and asserts none reach standard error or standard output, with and without `--verbose`. Copy that test for OFX.
- **`--verbose`** is a handler on the `tally` logger for the run only (`cli.import_run`); log through `logging.getLogger(__name__)` and never log a description or an amount.

## Decisions taken that the next session should not reopen

- Everything in the slice 1 list: exit codes and streams, the 10-second busy timeout, the fingerprint of ADR 0008, the sign rule, subprocess tests kill no mutants, the data directory order.
- **The sample `samples/current-account.csv` quotes its formula cell.** The brief wrote line 4 as `03/10/2026,=HYPERLINK("http://example.invalid","Refund"),,12.50,"4,420.33"`, which is six columns to the `csv` module, Excel and RFC 4180 alike; AC9's five rows and AC27's "the refund" only hold with the cell quoted. The unquoted form stays tested as `expected 5 columns, found 6`. `docs/brief.md` keeps the brief as given.
- **Unreadable rows go to standard error in both output forms**, the first 50 and then `and N more`; the JSON carries them all. The human summary is `added 5, already there 0, unreadable 0` on standard output.
- **A decoding error refuses the whole file** as `not a text file: not valid <encoding>` with no line number (the decoder reads ahead of the lines).
- **The field guard is 1 MB** (`csv.field_size_limit`) and the line guard 2 MB per physical line, both reported as `field longer than 1 MB`; a field spread over many short lines trips the limit where it passes 1 MB and the rest of its lines become one-column unreadable rows.
- **A layout refuses unknown keys** (a typo would otherwise fall back to a default silently) and has no `balance` key.
- **A `0400` data file is still writable through its WAL**; `SQLITE_READONLY` comes from the first `INSERT`, which `write()` maps to `the data file cannot be written (its permissions are 0400)` after the rollback. The test skips under root (the cloud session is root) and CI's runner proves it; locally, `runuser -u nobody -- .venv/bin/python -m pytest -p no:cacheprovider tests/test_import.py -k ac42 --rootdir . -c pyproject.toml` from `/tmp`.

## Open

- From slice 1: `account forget` keeps no tombstone; AC3's report check waits for slice 5; `account list` owes no CSV until slice 5.
- The full suite now takes about 55 s (AC18 under `tracemalloc` is 28 s of it, the two AC8 waits 20 s), and the stop hook runs it on every stop. Slice 3 adds no slow test; if the suite passes 90 s, move the slow ones behind a marker the hook skips and CI runs, and record the ADR.
- `Unreadable.line` is a line number for CSV and will be a transaction position for OFX; the message prefix in `cli.py` is the one place that assumes "line".
