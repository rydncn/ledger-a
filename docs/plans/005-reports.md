# 005. Reports

**Status:** active · **Satisfies:** AC30, AC31, AC32, AC33, AC35 (for `report`, `payees`, `uncategorised --format csv` and `account list --format csv`), AC36, AC37, AC38 (for `report` and `payees`), AC26's `report` check, AC3's `report` check, AC34 for the new commands · **Depends on:** 004

`report.py` turns transactions into plain rows: monthly totals by category per currency, and the payees taking the most money out per currency. Two commands render them: `tally report` and `tally payees`, each as a table, CSV or JSON. Categories come from `rules.categorise`, never stored.

**Door:** one-way. Two new commands, their options and their JSON and CSV are the shape of the command line other people's scripts read; `account list` gains `--format csv`; `uncategorised --format csv` changes its line endings on Windows only. No schema change, nothing new leaves the machine, no new dependency. Two modules join `scripts/check_imports.py`'s allowed list: `heapq` (the top payees in bounded memory) and `io` (to recognise the text stream whose line endings are set). A human reads `src/tally/report.py`, `src/tally/cli.py`, `src/tally/store.py` and `scripts/check_imports.py` before merging.

## Decisions taken in this plan

- **Months are `YYYY-MM` in ASCII digits, month 01 to 12**, checked by `[0-9]{4}-(?:0[1-9]|1[0-2])` in full. `strptime("2026-1", "%Y-%m")` is January (probed), and `\d` takes Arabic-Indic digits, so neither is used. Anything else is argparse's usage error naming the option (`argument --month: not a month like 2026-10`), exit 2 (AC37).
- **A period is `--month M`, or `--from M --to M`, both inclusive.** `--month` with `--from` or `--to`, only one of `--from` and `--to`, neither, or `--from` after `--to` is a usage error naming the options, exit 2, before the rules load or the data file opens. The months compare as text, which is their order. `report` and `payees` share the options.
- **Only months that have transactions get a section.** A range from 0001-01 to 9999-12 is 120,000 months; printing an empty section for each costs output for nothing. A period with no transactions prints nothing, as `uncategorised` does.
- **`Store.entries(months)`** takes an optional `(first, last)` pair and filters in SQL with `substr(t.date, 1, 7) BETWEEN ? AND ?`; the dates are ISO text, so the month is their first seven characters. **`Store.payments(months)`** reads the transactions with money out (`amount_minor < 0`) in the period, ordered by currency, scale and description, so payees are grouped as they stream. Both only read.
- **Sums are Python `int`s over `amount_minor`, then `from_minor`.** SQLite's integer `sum` raises `integer overflow` past 2^63 (probed); two transactions of 2^63 − 1 minor units each are a valid data file, and Python's `int` adds them exactly. No `Decimal` arithmetic anywhere. Rows are keyed by currency and scale, so nothing sums across currencies (AC36) and no total mixes two scales.
- **`report.monthly(entries, rules)`** gives one row per month, currency and category: `income` (the sum of positive amounts), `spending` (the sum of negative amounts, so negative), and `net` (both), in minor units with the scale. Net is what AC30's 0.10 + 0.20 − 0.30 shows as 0.00. Uncategorised is `NoMatch`, carried as category `None`. Rows sort by month, currency, then category name, uncategorised last. Memory is one total per row, whatever the number of transactions.
- **`report.payees(payments, top)`** gives, per currency, the `top` descriptions with the largest money out: the description, the total (negative) and the count. Descriptions are grouped exactly as stored. Ties go to the earlier description in sort order. `heapq.nsmallest` keeps `top` of them at a time, so memory is bounded by `top`, not by how many different descriptions a file holds. `--top` is 1 to 1,000 in ASCII digits (default 10); anything else is a usage error.
- **Table form of `report`:** one section per month and currency, headed `2026-10 GBP`, then a header line `category  income  spending  net` and a line per category, the category left-aligned and the amounts right-aligned in columns as wide as the section needs, sections separated by a blank line. Uncategorised shows as `uncategorised`. **`payees`:** one section per currency, headed `GBP`, then `description  total  count`. Every line goes through `printable` (AC38).
- **JSON:** `report` is an array of `{"month", "currency", "category", "income", "spending", "net"}`, `category` `null` for uncategorised; `payees` an array of `{"currency", "description", "total", "count"}`. Amounts are strings with the currency's places; `count` is a number. **CSV:** the same keys as headers and the same rows; text cells through `_cell`, uncategorised an empty cell (a rule name is never empty); amounts as `str(Decimal)`, never prefixed.
- **CSV line endings (the slice 4 review's F2), for every CSV command:** `\r\n`, as AC32 says, on every platform. Before writing, a text stream (`io.TextIOWrapper`) is reconfigured with `newline=""`, so Windows's text mode does not turn `\r\n` into `\r\r\n` (probed with a stream that translates as Windows does). `lineterminator="\n"` was rejected: it gives `\n` on Linux, against AC32. Windows is not in CI; the test uses a stream with `newline="\r\n"`, which translates exactly as Windows's does.
- **`account list --format csv`** (owed since slice 1): header `name,currency`, cells through `_cell`.
- **Colour (AC33):** only in the table form, only when standard output is a terminal and `NO_COLOR` is not in the environment at all (any value, the empty one too: `CLAUDE.md` says unset). Negative amounts are red; the `-` is there with or without colour, and the colour is applied after the padding, so the text with escape sequences removed is the same in all three cases. The escape character is written as `chr(0x1B)`.
- **AC33's tests use a real pseudo-terminal:** in-process, with `sys.stdout` opened on the slave side of `os.openpty()` in raw mode (so the terminal adds no `\r`), which mutation testing sees; and once through the installed command with the pty as its standard output.
- **Which commands read rules:** `report` loads them before `open_store` (AC29); `payees` does not need categories and does not read them.
- **Tests:** `tests/test_report.py` for `report.py` alone; `tests/test_reports.py` for the commands through `main`, with `tests/test_categorise.py::samples` reused; one subprocess test for the group, and the pty test.

## Tasks

Each task: the test first, seen to fail for the right reason, then the code, then the test seen to pass. "Observed by" records what was actually seen.

### Task 1: `report.py` and the store's reads (AC30, AC31, AC36, the overflow)

- **Test:** `tests/test_report.py`: monthly totals on the samples' entries by category and currency, income and spending apart; 0.10, 0.20 and −0.30 net to exactly 0.00; GBP and EUR never in one row; two amounts of 2^63 − 1 minor units sum exactly; payees ordered by money out with counts, per currency, ties by description, `top` honoured; income never counted as a payee's money out; the store's month filter inclusive at both ends.
- **Code:** `src/tally/report.py`; `Store.entries(months)`, `Store.payments(months)`.
- **Observed by:** before the code, `ModuleNotFoundError: No module named 'tally.report'` for the whole file. After `report.py` and the two store reads, 9 passed on the first run. Probed first: SQLite's `sum` over two `2**63 - 1` is `OperationalError: integer overflow`, so the sums are Python's.

### Task 2: `tally report` and `tally payees` (AC26, AC3, AC30 to AC32, AC34 to AC38)

- **Test:** `tests/test_reports.py` through `main`: AC26's categories in `report --month 2026-10 --format json`; AC3's report after `account forget`; AC30's table; AC31's range and payees; AC32's hostile descriptions in `report` and `uncategorised --format csv`, round-tripped through `csv`, amounts matching `^-?[0-9]+\.[0-9]{2}$`, `\r\n`; the Windows-style stream; AC35's JSON and CSV equal to the table's rows, and `account list --format csv`; AC36's two sections; AC37's refusals with the option named and the data directory not created; AC38 for both commands; AC29 for `report`; the help screens.
- **Code:** `cli.py`: the two commands, the period options, `_csv_stdout`, `account list --format csv`.
- **Observed by:** before the code, all 61 tests in `tests/test_reports.py` failed with argparse's `invalid choice: 'report'`, `'payees'` or (for `account list`) `'csv'`. After it, 57 passed and 4 failed, each the test's own mistake: one space short in the hand-counted payees header (twice, the in-process and the subprocess test), the sample's `=HYPERLINK` refund also uncategorised, and `subprocess.run(text=True)` translating `\r\n` on the way in (the check now reads bytes). Then 70 passed. The Windows-style stream test was seen to fail with the `reconfigure` removed: all four CSV commands wrote `\r\r\n`. The full suite then failed only `tests/test_cli.py`'s two help screens, which now list the two commands and `--format csv` for `account list`; updated, with the two new screens and three abbreviated options. `scripts/check_imports.py` was seen to fail on `io` and `heapq` before they were added. The after-edit hook asked for `zip(strict=)` and `map(strict=)` in `_columns`, and flagged a `‮` written in a Write that arrived as the raw character again, with fullwidth and Arabic-Indic digits pasted in tests (all now `chr()`).

### Task 3: Colour (AC33)

- **Test:** the in-process pty test and the subprocess pty test: escape sequences on a terminal, none piped or with `NO_COLOR`, `-` on every negative amount, the three identical once escapes are stripped.
- **Code:** `cli.py`: the colour decision and the red negative amount.
- **Observed by:** before the code, the three tests that expect colour on a terminal failed (no escape sequence in the pty's output); the three that expect none (with `NO_COLOR` of `1` and of the empty string, and the CSV and JSON forms on a terminal) passed, as they must before and after. After the code, 2 failed on the test's own mistake: `sys.stdout` was left on the closed pty, so the piped run after it wrote to a closed file; the patch is now scoped with `monkeypatch.context()`. Then all 6 pass, the subprocess one included. Full suite: 573 passed, 1 skipped (AC42 under root), 65 s.

### Task 4: What the review, the audit and mutation testing found

- **Observed by:**

## Done when

- [ ] Every criterion above has a `test_acNN_` test seen to fail before its code and pass after
- [ ] The five checks pass locally and in CI; mutation testing has no survivors, or each is ruled on beside the code
- [ ] The fresh-context review and the security audit have run with the four questions answered by name; findings fixed test-first or ruled on
- [ ] `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md` have this slice's rows; `docs/handoff.md` says what comes next
- [ ] The pull request is out of draft with CI green on its final commit
