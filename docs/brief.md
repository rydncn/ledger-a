# Tally: the brief

The brief this project is built from, as given at the start of the trial.

Build **Tally**, a command-line tool for people who want to see where their money goes without giving their bank statements to anyone. It imports the statement files banks let you download, removes duplicates, sorts transactions into categories by rules the user writes, and reports spending by month.

It runs entirely on the user's own computer. It never makes a network connection.

## What it does

- **Import** statement files: CSV in the layouts different banks use, and OFX (both the older SGML form, with unclosed tags, and the XML form). A CSV layout is described once, in the user's configuration: which columns hold the date, the description and the amount (or separate money in and money out columns), the date format, and the decimal and thousands separators. Importing the same file twice, or two statements whose dates overlap, never counts a transaction twice. Importing reports how many transactions were added, how many were already there, and any rows it couldn't read, with the reason and the line number.
- **Accounts**: each import belongs to an account the user names. An account has one currency; Tally never converts between currencies.
- **Categorise** by rules in a configuration file the user edits by hand: match on the description (text or a pattern), the amount (a range) and the account, with the first matching rule winning. The user can see which transactions no rule matched, and why a given transaction got its category.
- **Report** spending and income by category for each month or a range of months, and the payees taking the most money. Show reports in the terminal, and export them as CSV for a spreadsheet.
- **Forget**: delete an account and everything imported into it.

## What matters

- **It's people's money and their financial history.** Amounts are exact: no floating point anywhere money is held or summed. Nothing personal goes into any log or error message unless the user asked to see it. The data file is readable only by the user.
- **Statement files are messy and sometimes hostile.** They arrive with byte order marks, Windows line endings, Latin-1 instead of UTF-8, quoted fields containing commas, amounts like `1,234.56` and `(12.50)`, and descriptions that start with `=`, `+`, `-` or `@`, which a spreadsheet runs as a formula when it opens an export. A file may be very large, or not a statement at all.
- **People run it in a terminal, often with a screen reader, often piping its output.** Meaning never depends on colour alone; colour turns off when output isn't a terminal or `NO_COLOR` is set; errors go to standard error with a non-zero exit code; and there is a plain, machine-readable output for every report.
- **Two copies may run at once,** for example an import started twice by a scheduled job.

Out of scope: a graphical interface, bank connections, investments, budgets, multiple users, and syncing between computers.

## Stack

Python 3.15, managed with `uv`. Standard library first; add a dependency only when the standard library can't reasonably do the job. Storage in SQLite through the standard library. It installs as a single command, `tally`.

## Sample files

Three small files to start from. Real exports are larger and messier.

`samples/current-account.csv` (UTF-8 with a byte order mark, Windows line endings):

```csv
Date,Description,Money Out,Money In,Balance
01/10/2026,"TESCO STORES 2045, LEEDS",42.17,,"1,957.83"
02/10/2026,SALARY ACME LTD,,"2,450.00","4,407.83"
03/10/2026,=HYPERLINK("http://example.invalid","Refund"),,12.50,"4,420.33"
03/10/2026,TFL TRAVEL CH,(3.40),,"4,416.93"
05/10/2026,DIRECT DEBIT COUNCIL TAX,156.00,,"4,260.93"
```

`samples/credit-card.csv` (Latin-1, semicolons, decimal commas, US-style dates):

```csv
Transaction Date;Payee;Amount
10/02/2026;CAFÉ NERO;-4,20
10/03/2026;AMAZON MARKETPLACE;-23,99
10/03/2026;PAYMENT RECEIVED - THANK YOU;150,00
```

`samples/savings.ofx` (OFX 1.x SGML, unclosed tags):

```
OFXHEADER:100
DATA:OFXSGML
VERSION:102
ENCODING:USASCII
CHARSET:1252

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>GBP
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261001<TRNAMT>12.34<FITID>2026100101<NAME>INTEREST
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261015<TRNAMT>-500.00<FITID>2026101501<NAME>TRANSFER TO CURRENT
</BANKTRANLIST>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
```
