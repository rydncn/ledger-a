# 003. OFX import

**Status:** draft, written by the slice 2 session before handing over; the slice 3 session reviews every decision before building · **Satisfies:** AC21 to AC25, AC39, AC41, with AC34 and AC35 for `import` of an OFX file · **Depends on:** 002

The second importer: OFX statements in the 1.x SGML form (unclosed tags) and the 2.x XML form, read by one scanner into the same `Transaction | Unreadable` outcomes slice 2 defined, fingerprinted from `FITID` (ADR 0008), and written through the same `Store.import_transactions`.

**Door:** one-way. The fingerprint `ofx:<FITID>` is persisted (ADR 0008); `tally import FILE` without `--layout` is now the OFX shape of the command line; the unreadable messages' prefix (`transaction N:`) is part of what `--format json` consumers see in `reason`. No schema change. A human reads `src/tally/importers/ofx.py` and `src/tally/cli.py` before merging.

## Decisions taken in this plan

- **One scanner, no XML parser.** OFX 2.x is OFX 1.x with closed tags and an XML prolog, so one tolerant tag scanner reads both: `<TAG>` opens an element, the text up to the next `<` is a leaf's value (entities decoded with `html.unescape`, which covers `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#39;` in both forms), `</TAG>` closes back to that tag, and a new `<TAG>` while a leaf is open closes the leaf (the SGML rule). The XML prolog and `<?OFX ...?>` processing instructions are skipped. No `xml.etree` or expat runs, so there is no entity expansion, no external fetch and no DOCTYPE handling to get wrong; AC39's check is still made on the first bytes, before the scanner, because the design says so and the message names the reason.
- **Streamed.** The file is read in 64 KB chunks; everything up to the last `<` in the buffer is scanned (every tag before it has its value complete), the rest is carried. A carry over 1 MB (a value with no tag for a megabyte) is `not a statement: a value longer than 1 MB`.
- **Depth is capped at 64** (AC41): the sixty-fifth nested open tag is `not a statement: tags nested deeper than 64`. Closing a tag that is not open is ignored (banks' SGML is loose); the scanner never recurses.
- **Encoding, once, from the header.** SGML: `CHARSET:1252` or no charset is `cp1252` (the OFX 1.x default and a superset of ASCII); `ENCODING:UTF-8` is `utf-8`. XML: the prolog's `encoding="..."`, else `utf-8`; a UTF-8 byte order mark is stripped. An unknown encoding or a decoding error is `not a text file: ...`, whole-file, as for CSV.
- **The currency check is before any row is written.** `CURDEF` is met before the first `STMTTRN`; a `CURDEF` that is not the account's raises `NotAStatementError("the file is in GBP but the account is in EUR")` (AC24). It is raised from inside the outcomes iterator, which `import_transactions` consumes under the lock, so the rollback makes "nothing written" hold; the record is rolled back with it. A file with no `CURDEF` takes the account's currency, as a CSV does.
- **A transaction's outcome** is decided when its `STMTTRN` closes (explicitly, or implicitly by the next `STMTTRN` or by `</BANKTRANLIST>`): no `FITID` is `no FITID` (AC41); no `DTPOSTED` is `no DTPOSTED` (AC25); a `DTPOSTED` whose first eight characters are not `YYYYMMDD` is `DTPOSTED is not a date`; `TRNAMT` through `parse_amount(text, ".", ",")` and `to_minor`, so `12,34` is `amount is not a number` (AC25); no `TRNAMT` is `no TRNAMT`; the description is `NAME`, else `MEMO`, else `no NAME`. `Unreadable.line` holds the transaction's 1-based position; `cli.py` prefixes `transaction N:` for an OFX file and `line N:` for a CSV, the one place that word lives.
- **The fingerprint is `ofx:<FITID>`** (ADR 0008) with the `FITID` trimmed; two `STMTTRN` with the same `FITID` in one file are one transaction (the second is "already there"), which is what a bank's promise of uniqueness means.
- **`--layout` with an OFX file stays exit 2**; `tally import --account savings samples/savings.ofx` is the whole command (AC21).

## Tasks

### Task 1: The scanner reads SGML and XML into the same outcomes (AC21, AC22, AC25, AC41)

- **Test:** `tests/test_ofx.py`: `read()` on `samples/savings.ofx` gives the two transactions with `ofx:2026100101` and `ofx:2026101501`; the same statement as XML gives the same two; a file whose second `STMTTRN` has `TRNAMT` `12,34` and whose third has no `DTPOSTED` gives one transaction and `Unreadable(2, "amount is not a number")`, `Unreadable(3, "no DTPOSTED")`; `STMTTRN` without `FITID` is `no FITID`; 10,000 nested tags are refused `not a statement`; a `&amp;` in `NAME` is `&`; `CHARSET:1252` decodes a `\x80` as `€`; a 1 MB value with no tag is refused.
- **Code:** `importers/ofx.py`.
- **Observed by:**

### Task 2: `tally import` reads an OFX file (AC21 to AC25, AC39, AC34, AC35)

- **Test:** `tests/test_ofx.py` through `main`: AC21 (2 added, the amounts and dates from the data file), AC22 (XML then SGML adds 0), AC23 (twice), AC24 (EUR account refused with the exact message, nothing written, no record), AC25 (standard error names `transaction 2: amount is not a number` and `transaction 3: no DTPOSTED`, exit 0), AC39 (a DOCTYPE with `SYSTEM` naming a FIFO the test made; the message is the DOCTYPE one), `--layout` with an OFX file stays exit 2, `--format json` on an OFX import, one subprocess run.
- **Code:** `cli.py`: the OFX branch replaces `OFX import is not available yet`; the `transaction`/`line` prefix; the help text.
- **Observed by:**

### Task 3: What mutation testing and the whole-codebase review found

- **Observed by:**

## Done when

- [ ] Every criterion above has a `test_acNN_` test seen to fail before its code and pass after
- [ ] The four checks pass locally and in CI; mutation testing has no survivors, or each is ruled on in the pull request
- [ ] The whole-codebase review (every slice read together, `docs/review-brief.md`) has run with the four questions answered by name; findings fixed test-first or ruled on
- [ ] `docs/effort.md`, `docs/trial-log.md`, `docs/playbook-feedback.md` have this slice's rows; `docs/handoff.md` says where slice 4 starts
- [ ] The pull request is out of draft with CI green on its final commit
