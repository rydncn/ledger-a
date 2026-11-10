// Reads .claude/checks.json: the project's own commands for the after-edit and
// before-stop hooks, so they work for any language. Without the file, the
// hooks fall back to the npm defaults (Prettier, ESLint and package.json
// scripts).
//
//   {
//     "afterEdit": [
//       { "extensions": [".go"], "run": ["gofmt", "-w", "{file}"], "fix": true },
//       { "extensions": [".go"], "run": ["go", "vet", "{dir}"] }
//     ],
//     "beforeStop": [
//       { "run": ["gofmt", "-l", "."], "failOnOutput": true },
//       { "run": ["go", "test", "./..."] }
//     ]
//   }
//
// `{file}` is the edited file's absolute path; `{dir}` its folder relative to
// the project, as `./internal/web` (or `.`). A `fix` entry (a formatter) never
// reports; any other entry reports when it exits non-zero, or, with
// `failOnOutput`, when it prints anything. A `run` can call the project's
// existing task runner: ["make", "check-fast"] or ["just", "lint"].
//
// The file runs commands on every edit, so it is agent configuration and
// reviewed as code (rule 18).

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

export const CHECKS_FILE = path.join(".claude", "checks.json");

const isRun = (run) =>
  Array.isArray(run) &&
  run.length > 0 &&
  run.every((part) => typeof part === "string" && part !== "");

function validEntries(entries, needsExtensions) {
  return (
    Array.isArray(entries) &&
    entries.every(
      (entry) =>
        entry !== null &&
        typeof entry === "object" &&
        isRun(entry.run) &&
        (!needsExtensions ||
          (Array.isArray(entry.extensions) &&
            entry.extensions.every((e) => typeof e === "string"))),
    )
  );
}

/**
 * The project's checks, or null when it has no checks.json. Throws an Error
 * naming the file when it exists but can't be used, so a broken file is
 * reported rather than silently checking nothing.
 */
export function loadChecks(projectDir) {
  const file = path.join(projectDir, CHECKS_FILE);
  if (!existsSync(file)) return null;
  let checks;
  try {
    checks = JSON.parse(readFileSync(file, "utf8"));
  } catch (error) {
    throw new Error(`${CHECKS_FILE} can't be read: ${error.message}`);
  }
  const afterEdit = checks?.afterEdit ?? [];
  const beforeStop = checks?.beforeStop ?? [];
  if (!validEntries(afterEdit, true) || !validEntries(beforeStop, false)) {
    throw new Error(
      `${CHECKS_FILE} is not in the expected shape: "afterEdit" and "beforeStop" are lists of { "run": ["command", "arg"] }, and each afterEdit entry has "extensions".`,
    );
  }
  return { afterEdit, beforeStop };
}

/** The command with `{file}` and `{dir}` filled in. */
export function fill(run, { file = "", dir = "." } = {}) {
  return run.map((part) =>
    part.replaceAll("{file}", file).replaceAll("{dir}", dir),
  );
}

/** Whether a finished run counts as a failure for this entry. */
export function failed(entry, result) {
  return (
    result.status !== 0 ||
    (entry.failOnOutput === true && result.output.trim() !== "")
  );
}

export const shown = (run) => run.join(" ");
