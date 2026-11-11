# Python pack (draft)

**Draft.** Written during the playbook's third trial (Tally, a command-line tool on Python 3.15 and uv, standard library only, SQLite) and brought to its final draft state at the trial's close. One project has used it; say so until a second project has. The files here are the copies the trial used, identical to the live copies in this repository at the close (`.claude/checks.json`, `.github/workflows/ci.yml`, `.claude/hooks/pre-push`, `scripts/`), kept with the project so they can become `templates/stacks/python/` in the playbook. Not copied here: `scripts/check_imports.py`, `scripts/rules.json` and `scripts/setup-dev.sh`, which are Tally's own (its import allowlist, its rules, its install), though a project of the same shape will want their like.
| File | Copy to | What it does |
| --- | --- | --- |
| [`checks.json`](checks.json) | `.claude/checks.json` | The edit hook formats the edited file with `ruff format` and lints it with `ruff check`; the stop hook runs the format check, the lint, `mypy` and the tests. A project with `scripts/rules.json` or an import allowlist adds those two to `beforeStop`, as Tally's does: otherwise they run only in CI and `pre-push`. |
| [`ci.yml`](ci.yml) | `.github/workflows/ci.yml` | Format, lint, types and rule checks on every push; shuffled parallel tests, mutation testing on changed files, lockfile integrity, `pip-audit`, gitleaks, zizmor and the agent configuration step once the pull request is ready. |
| [`pre-push`](pre-push) | `.claude/hooks/pre-push` | Refuses a push to `main` or `master` however the command spells it, then format, lint, type check, and the project's rule checks and import allowlist where it has them, before any push, for tools and people outside Claude Code. |
| [`mutation_changed.py`](mutation_changed.py) | `scripts/` | Rule 15's mutation testing on the files a change touches, with mutmut. |
| [`audit.py`](audit.py) | `scripts/` | `pip-audit` over the exported lockfile with a dated allowlist, like `templates/audit`. |
| [`check_lock.py`](check_lock.py) | `scripts/` | The lockfile only points at PyPI over HTTPS with a sha256 on every file, like lockfile-lint. |

## The tools

| Playbook item | npm | Python here |
| --- | --- | --- |
| Formatter and linter | Prettier, ESLint | `ruff format`, `ruff check` with a wide rule set, as errors |
| Type check | `tsc --noEmit` | `mypy --strict` |
| Tests once, never watch mode | `vitest run` | `pytest` (`-p no:cacheprovider` in `pyproject.toml`) |
| Random order and parallel (rule 16) | `--randomize`, `sequence.shuffle` | `pytest-randomly` (prints its seed; replay with `-p randomly_seed=<seed>`), `pytest-xdist -n auto` |
| No cached results | `--count=1` in Go | `-p no:cacheprovider`; pytest has no result cache that skips tests, but this also stops `.pytest_cache` from steering order |
| Fails if no tests ran (rule 9) | custom | pytest exits 5 when it collects nothing, so the plain exit code already fails |
| Mutation testing on changed files (rule 15) | Stryker `--incremental` | mutmut 3, filtered by mutant name pattern per changed module (`scripts/mutation_changed.py`) |
| Dependency audit with a dated allowlist | `templates/audit` | `pip-audit` over `uv export` (`scripts/audit.py`) |
| Lockfile integrity | lockfile-lint | `scripts/check_lock.py` over `uv.lock`, plus `uv lock --check` |
| Install scripts off | `ignore-scripts=true` | `UV_NO_BUILD=1` / `uv sync --no-build`: only wheels, so no package's `setup.py` runs |
| Minimum release age | `min-release-age=7` | `[tool.uv] exclude-newer = "<date>"`, moved by hand when dependencies change; Dependabot `cooldown` to match |
| Exact versions | `save-exact=true` | The lockfile pins exactly; `pyproject.toml` holds ranges with upper bounds so a lock under `exclude-newer` can resolve |
| `npm ci` only | | `uv sync --locked`: fails if the lockfile is stale rather than updating it |
| `prepare` script pointing git at the hooks | `package.json` | None in Python: `scripts/setup-dev.sh` sets `core.hooksPath` and is in CLAUDE.md's install command |

## Permissions to allow

Beside the template's deny and ask rules: `Bash(uv run --no-build ruff *)`, `Bash(uv run --no-build mypy*)`, `Bash(uv run --no-build pytest*)`, one `Bash(uv run --no-build python scripts/<name>.py*)` per script (not `scripts/*`, which would let the agent run any script it writes there unprompted), `Bash(uv sync --locked --no-build*)`, `Bash(uv lock --check*)`, `Bash(node scripts/check-rules.js*)`. Ask before `uv publish`, `uv build` and `twine`. Never `Bash(uv run --no-build pip-audit*)`: without `--disable-pip`, `pip-audit -r <file>` pip-installs the file's requirements and runs their build backends, which `UV_NO_BUILD` does not stop (the whole-codebase audit observed it); the audit runs through `scripts/audit.py`, allowed by name.

## What the trial learned

- **mutmut only sees tests that run the code in-process.** Its trampolines record which test reached which function from inside the test process; a test that drives the command through `subprocess` reaches none, and mutmut stops with "could not find any test case for any mutant". Drive behaviour through the entry function (`main(argv)`) and keep a few subprocess tests for what only a real process shows: exit codes, the installed command, standard error, `NO_COLOR`.
- **`exclude-newer` is the release-age gate, and it bites the day you set it up.** With the cutoff seven days back, the newest ruff was refused at the first lock. That is the gate working; take the versions the resolver picks under the cutoff rather than pinning today's.
- **`--no-build` has no per-package exception.** uv can refuse all source builds or none (`no-build-package` is a deny list). A brand-new Python has packages without wheels yet (here pyyaml, needed by mutmut's libcst, on 3.15), so the setting lives on the install commands (`UV_NO_BUILD=1` in CI's `env` and `.claude/settings.json`), and the one job that needs the build turns it off, with an ADR.
- **mutmut's mutant names** are `package.module.x_<function>__mutmut_<n>` for functions and `package.module.<Class>.x<method>__mutmut_<n>` for methods, so a changed file `src/tally/cli.py` is the pattern `tally.cli.*`. `mutmut run` exits 0 with survivors; read `mutmut results --all true` and fail on `survived` yourself. `mutmut run` with a filter that matches nothing asserts and exits non-zero, which is the right behaviour for a gate.
- **mutmut's stats are incremental.** `mutants/mutmut-stats.json` maps each function to the tests that reached it; a function added after the first run is mapped only to tests added after it, so its mutants are judged by too few tests and a `while True` became `while False` unseen. `scripts/mutation_changed.py` deletes `mutants/` before each run; CI starts clean anyway.
- **mutmut 3 config keys:** `source_paths` (not the deprecated `paths_to_mutate`) and the tests directory through pytest's own arguments; it copies `tests/`, `pyproject.toml` and `uv.lock` into `mutants/` itself.
- **Run mutation testing in the background** (`run_in_background` with a long timeout, its output to a file) once a change touches more than a few files: a tool call has a time limit, a run cut off by it prints no summary and looks like a failed run, and CI's mutation job is the gate either way. In the trial, a run over seven source files was about 1,750 mutants and 45 minutes on the CI runner, 25 minutes locally; CI's job has `timeout-minutes: 60` for it.
- **Run the fresh-context review first, then one mutation run on the final tree.** A run started in parallel with the review mutates code the review's fixes will change, and is wasted.
- **mutmut runs a mutant's covering tests fastest first** with `-x`, so a slow acceptance test (a 10-second lock wait) only runs for mutants nothing else kills; no need to design around it.
- **A `pragma: no mutate` guards one physical line.** When the formatter splits a long condition, the pragma lands on the closing bracket and guards nothing; give the guarded expression a line of its own, and check with `grep -n "):  # pragma"`. A pragma without a reason beside it is a finding.
- **The pack's pieces need Node too:** the hooks and the rule check are Node scripts, which the playbook says; a Python-only machine needs Node installed for them. GitHub's runners have it.

- **The shell is a blind spot for the after-edit hook.** Edits made with a heredoc or `sed` get no format or lint feedback; in the trial's last session the `pre-push` lint caught two such edits before anything left. The rule check `no-raw-control-character` (C0 but tab and line feed, and DEL, in source) makes the `chr()` lesson a gate for ESC and its kind; ruff's RUF001 and PLE2502 cover the dashes and the bidi overrides.
- **`--end-of-options` before a ref from the command line** (`mutation_changed.py`): a base starting `--` was passed to `git diff` as an option.
- **Never allow `pip-audit*` by prefix.** Without `--disable-pip`, `pip-audit -r <file>` pip-installs the file and ran its build backend in the trial's audit, whatever `UV_NO_BUILD` said. Allow the audit script by name.
- **A security audit's sandbox in a cloud container:** `unshare -m -n -p -f`, a recursive read-only remount of `/` with the agent's scratch bound writable, `env -i` with a short allowlist, and `prlimit`. The trial wrote it for the audit (`~/security-audit-skill/<repo>/run-<n>/bin/sandbox.sh`); it belongs here or in the skill.

## Measuring a session

Rule 17's budget counts what a session added since its first reply. The same arithmetic as `context-budget.mjs`, for the record in `docs/effort.md`, from the session's transcript (`~/.claude/projects/<project>/<session>.jsonl`):

```python
import json, sys

start = last = None
peak = 0
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        row = json.loads(line)
    except ValueError:
        continue
    if row.get("type") == "system" and row.get("subtype") == "compact_boundary":
        start = None
        continue
    usage = (row.get("message") or {}).get("usage")
    if row.get("type") != "assistant" or row.get("isSidechain") or not usage:
        continue
    last = sum(
        usage.get(k, 0)
        for k in (
            "input_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
            "output_tokens",
        )
    )
    peak = max(peak, last)
    start = start if start is not None else last
print(f"start {start:,} peak {peak:,} added at peak {peak - start:,}")
```

Not part of the pack proper; here because the trial needed it and nothing in the playbook gives the number after the fact.
