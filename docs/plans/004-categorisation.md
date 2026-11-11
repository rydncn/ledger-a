# 004. Categorisation

**Status:** active · **Satisfies:** AC26 (through `rules.categorise`, `uncategorised` and `explain`; its `report` form is slice 5's), AC27, AC28, AC29, AC38 (for `uncategorised` and `explain`), with AC34 and AC35 for `uncategorised` and `explain` · **Depends on:** 003

The user's `[[rules]]` from `tally.toml`, validated before the data file opens, and `rules.categorise(entry, rules) -> Match | NoMatch` as the one definition of a transaction's category. Two commands read it: `tally uncategorised` lists what no rule matched, and `tally explain <id>` says why one transaction got its category. Nothing stores a category.

**Door:** one-way. Two new commands and their machine-readable output (`uncategorised --format csv|json`, `explain --format json`) are the shape of the command line other people's scripts read, and the rule keys are the shape of the user's `tally.toml`. No schema change, nothing new leaves the machine, no new dependency, no import outside `scripts/check_imports.py`'s list (`re`, `unicodedata`, `decimal`, `csv` are already on it). A human reads `src/tally/rules.py`, `src/tally/cli.py` and `src/tally/store.py` before merging.

## Decisions taken in this plan

- **A rule** is a `[[rules]]` table with a `name` and any of `account`, `description_contains`, `description_matches`, `amount_above`, `amount_below`. Every value is a TOML string; any other key, or a value of another type, is a configuration error. A rule is all of its conditions; the first rule whose conditions all hold wins. A rule with only a `name` matches everything (a catch-all "Other" at the end is a reasonable thing to write); a rule with an empty `description_contains` or `description_matches` is refused instead of matching everything by accident.
- **Positions are 1-based:** `rules[2]` is the second `[[rules]]` table in the file, which is how a person counts them in an editor. Two rules may share a name (Groceries for TESCO and for SAINSBURY), so `explain` names each rule by position and name.
- **`description_contains` ignores case** (`casefold`): banks change the case of the same payee between files. **`description_matches` is Python's `re.search`**, case-sensitive unless the pattern says `(?i)`, so `^TFL` anchors and `TFL` finds it anywhere. The pattern is compiled once, when the rules load; `re.error`, `OverflowError` (`a{4294967296}`) and `RecursionError` (two thousand nested groups) are each `rules[N]: description_matches is not a valid pattern: <re's message, without the position>`. A pattern that backtracks catastrophically costs the user's own CPU on their own pattern: accepted in the design (§ Three checks).
- **Amounts in rules are quoted text in one shape:** an optional sign, 1 to 19 ASCII digits, and an optional fraction of 1 to 3 digits (3 is the most any currency's minor unit has). `Decimal` alone would also take `1_000`, ` 5 `, `NaN`, `1e5` and Arabic-Indic digits (probed); a TOML number would arrive as a binary `float`. `"ten"`, `-100` unquoted and `1,000` are each `rules[N]: amount_below is not an amount like "-100.00"`. `amount_above` must be less than `amount_below` when both are given, else the range is empty and the rule could never match.
- **Comparisons are exact and strict:** `amount_above X` holds when the amount is greater than X, `amount_below X` when it is less, each compared as `Decimal` in the account's own currency (the transaction's amount from `from_minor`, built from digits). Comparing two `Decimal`s never rounds, so no arithmetic and no `to_minor` per account is needed; the handoff's suggestion to convert with `to_minor` would refuse a rule like `amount_below = "0.005"` at report time for a GBP account rather than at load.
- **`account` is compared exactly with the account's name.** A rule naming an account that does not exist never matches; checking it would need the data file open before the rules are known to be valid, and AC29 is about the file alone. Recorded as open for the owner.
- **Names are checked like account names:** not empty, no control characters, because they reach the terminal in `explain` and slice 5's report.
- **What `categorise` returns:** `Match(rule, verdicts)` or `NoMatch(verdicts)`, where `verdicts` is every rule tried, in order, each with whether it matched and its conditions: all of them for the rule that matched, the first that failed for each rule that did not (the conditions are checked account, then description, then pattern, then amounts, so the cheap ones stop a rule before its pattern runs). The texts are AC28's: `description contains TESCO` / `description does not contain TESCO`, `description matches ^TFL` / `does not match`, `account is card` / `is not`, `amount is above 0` / `is not above`, `amount is below -100.00` / `is not below`.
- **The transaction rules read** is `store.Entry`: id, date, account name, currency, scale, description, amount in minor units, with `amount` as a `Decimal`. `Store.entries()` iterates every one, oldest first; `Store.entry(id)` reads one. Both only read: no `BEGIN IMMEDIATE` (`CLAUDE.md` § Lessons).
- **`tally uncategorised [--format table|csv|json]`** lists every transaction `categorise` gives `NoMatch`, oldest first. Table: one line each, `id  date  account  amount currency  description`, two spaces apart and the description last, so no column width needs the whole list. CSV: header `id,date,account,amount,currency,description`. JSON: an array of objects with those keys; `id` is a number, `amount` a string with the account's decimal places. The rows are collected before anything is printed, so a data file that fails part way leaves standard output empty (AC34).
- **`tally explain ID [--format table|json]`**: the transaction's line as in `uncategorised`, then `category Travel, from rule 2` or `no rule matched`, then one line per rule tried: `rule 1 Groceries did not match: description does not contain TESCO`, `rule 2 Travel matched: description matches ^TFL` (conditions joined by ` and `; a catch-all says `it has no conditions`). JSON: the transaction's fields, `category` (a string or `null`) and `rules`, a list of `{"rule": 1, "name": ..., "matched": false, "conditions": [...]}`. An id that is not 1 to 19 ASCII digits below 2^63 is a usage error (exit 2, `int` would take `٣`); an id with no transaction is refused, `no transaction 999`, exit 1.
- **AC38: one function, `cli.printable`,** replaces every control character before text reaches the terminal: C0 controls by their Unicode control picture (`\x1b` as `␛`, backspace as `␈`), DEL as `␡`, and every other character in a `C` category (C1 controls such as the 8-bit CSI `\x9b`, bidirectional overrides, unassigned code points) or a line or paragraph separator by `?`. It applies to each table line, each CSV text cell and each configuration error. JSON keeps the original, which `json.dumps` writes as `\u001b`.
- **CSV text cells** (`date`, `account`, `currency`, `description`) are printable-replaced and then, if they start with `=`, `+`, `-`, `@`, a tab or a carriage return, prefixed with `'` (`CLAUDE.md` § Security boundaries); `id` and `amount` are written as numbers and never prefixed. The CSV keeps the replacement rather than the original because it is read on the terminal as often as in a spreadsheet, and a control character means nothing in either; the JSON is the faithful form.
- **Which commands read rules:** `uncategorised` and `explain` (and slice 5's `report`). Each loads the rules before `open_store`, so a broken rule is exit 2 with the data directory not created (AC29). `import` and `account` do not read rules, and a broken rule does not stop them.
- **AC26's `report` form is slice 5's.** AC26's matching is proved now through `rules.categorise` on the imported samples, `explain` (TESCO −150.00 is Groceries, not Big; the savings transfer is not Big) and `uncategorised`; slice 5's handoff names the `report --format json` check.
- **Tests:** `tests/test_rules.py` for loading and `categorise` alone, `tests/test_categorise.py` for the two commands through `main`, with `tests/test_import.py::Place` reused and the rules appended to its config; one subprocess test for the group.

## Tasks

Each task: the test first, seen to fail for the right reason, then the code, then the test seen to pass. "Observed by" records what was actually seen.

### Task 1: Rules load and categorise (AC26, AC28's texts, AC29)

- **Test:** `tests/test_rules.py`: AC26's four rules over the samples' entries give Groceries, Travel, Big, Card payments; TESCO at −150.00 is Groceries; the savings transfer is not Big; strict comparisons at the boundary; contains ignores case; pattern searches; each verdict's text; a catch-all; every AC29 refusal (`(`, `ten`, no name) and each other: unknown key, non-string value, empty name, control character in a name, empty contains or pattern, `OverflowError` and `RecursionError` patterns, every amount shape `Decimal` would wrongly take, `amount_above` not below `amount_below`.
- **Code:** `src/tally/rules.py`; `store.Entry`.
- **Observed by:** _(filled in as it happens)_

### Task 2: `tally uncategorised` and `tally explain` (AC26 to AC29, AC34, AC35, AC38)

- **Test:** `tests/test_categorise.py` through `main` with the three samples imported: AC27's six rows in the table, CSV and JSON; AC28's explain of the TFL row and of an uncategorised row, in table and JSON; AC26 through `explain`; AC29 for both commands with the data directory not created; an unknown id (exit 1) and a non-ASCII or huge id (exit 2); AC38 with `\x1b]0;evil\x07` and a backspace in a description, absent from standard output in table and CSV and kept in JSON; a formula description escaped in the CSV and an amount never prefixed; a configuration error with a control character in a key; the help screens; one subprocess run.
- **Code:** `cli.py`: the two commands, `printable`, the CSV writer; `store.py`: `entries()` and `entry(id)`.
- **Observed by:** _(filled in as it happens)_

### Task 3: What mutation testing and the fresh-context review found

- **Observed by:** _(filled in as it happens)_

## Done when

- [ ] Every criterion above has a `test_acNN_` test seen to fail before its code and pass after
- [ ] The five checks pass locally and in CI; mutation testing has no survivors, or each is ruled on beside the code
- [ ] The fresh-context review of the slice has run with the four questions answered by name; findings fixed test-first or ruled on
- [ ] `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md` have this slice's rows; `docs/handoff.md` says where slice 5 starts
- [ ] The pull request is out of draft with CI green on its final commit
