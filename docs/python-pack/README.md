# Python pack (draft)

**Draft.** Written during the playbook's third trial (Tally, a command-line tool on Python 3.15 and uv, standard library only, SQLite). It has been through one project's setup; say so until a second project has used it. The files here are the copies the trial used, kept with the project so they can become `templates/stacks/python/` in the playbook.

| File | Copy to | What it does |
| --- | --- | --- |
| [`checks.json`](checks.json) | `.claude/checks.json` | The edit hook formats the edited file with `ruff format` and lints it with `ruff check`; the stop hook runs the format check, the lint, `mypy` and the tests. |
| [`ci.yml`](ci.yml) | `.github/workflows/ci.yml` | Format, lint, types and rule checks on every push; shuffled parallel tests, mutation testing on changed files, lockfile integrity, `pip-audit`, gitleaks, zizmor and the agent configuration step once the pull request is ready. |
| [`pre-push`](pre-push) | `.claude/hooks/pre-push` | Format, lint and type check before any push, for tools and people outside Claude Code. |
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
- **The pack's pieces need Node too:** the hooks and the rule check are Node scripts, which the playbook says; a Python-only machine needs Node installed for them. GitHub's runners have it.

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
