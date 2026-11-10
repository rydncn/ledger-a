#!/usr/bin/env node
// PostToolUse hook for Edit, Write and MultiEdit: formats the file that was
// just changed and lints it, so the agent sees problems while it is still
// working on that file rather than at CI time.
//
// The commands come from .claude/checks.json when the project has one (any
// language; see checks.mjs). Without it: Prettier and ESLint from the
// project's node_modules.
//
// Exit 0: nothing to report. Exit 2: a failing check, shown to Claude (the
// edit has already happened; this cannot block it). Tools the project hasn't
// installed are skipped, so the hook never breaks a session.

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { failed, fill, loadChecks, shown } from "./checks.mjs";

const FORMAT_EXTENSIONS = new Set([
  ".js",
  ".jsx",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".json",
  ".css",
  ".scss",
  ".md",
  ".yml",
  ".yaml",
  ".html",
]);
const LINT_EXTENSIONS = new Set([".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"]);
const MAX_OUTPUT = 4000;

const WINDOWS = process.platform === "win32";

function defaultExec(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: "utf8",
    timeout: 60_000,
    shell: WINDOWS,
  });
  return {
    status: result.status ?? 1,
    output: `${result.stdout ?? ""}${result.stderr ?? ""}`,
  };
}

function localBin(projectDir, name) {
  const base = path.join(projectDir, "node_modules", ".bin", name);
  if (existsSync(base)) return base;
  if (WINDOWS && existsSync(`${base}.cmd`)) return `${base}.cmd`;
  return null;
}

export function afterEdit(input, { projectDir, exec = defaultExec }) {
  const filePath = input?.tool_input?.file_path;
  if (typeof filePath !== "string" || filePath === "") return { code: 0 };

  const absolute = path.resolve(projectDir, filePath);
  const relative = path.relative(projectDir, absolute);
  if (relative.startsWith("..") || path.isAbsolute(relative))
    return { code: 0 };
  if (relative.split(path.sep).includes("node_modules")) return { code: 0 };
  if (!existsSync(absolute)) return { code: 0 };

  const extension = path.extname(absolute).toLowerCase();

  let checks;
  try {
    checks = loadChecks(projectDir);
  } catch (error) {
    return { code: 2, stderr: `${error.message}\n` };
  }
  if (checks)
    return configured(
      checks.afterEdit,
      extension,
      absolute,
      relative,
      projectDir,
      exec,
    );

  const prettier = localBin(projectDir, "prettier");
  if (FORMAT_EXTENSIONS.has(extension) && prettier) {
    exec(
      prettier,
      ["--write", "--log-level", "warn", "--ignore-unknown", absolute],
      projectDir,
    );
  }

  const eslint = localBin(projectDir, "eslint");
  if (LINT_EXTENSIONS.has(extension) && eslint) {
    const lint = exec(
      eslint,
      ["--no-warn-ignored", "--max-warnings", "0", absolute],
      projectDir,
    );
    if (lint.status !== 0) {
      return {
        code: 2,
        stderr: `ESLint found problems in ${relative}. Fix them before moving on:\n${lint.output.slice(-MAX_OUTPUT)}`,
      };
    }
  }

  return { code: 0 };
}

function configured(entries, extension, absolute, relative, projectDir, exec) {
  const dir = path.dirname(relative);
  const vars = {
    file: absolute,
    dir: dir === "." ? "." : `./${dir.split(path.sep).join("/")}`,
  };
  for (const entry of entries) {
    if (!entry.extensions.map((e) => e.toLowerCase()).includes(extension))
      continue;
    const [command, ...args] = fill(entry.run, vars);
    const result = exec(command, args, projectDir);
    if (entry.fix !== true && failed(entry, result)) {
      return {
        code: 2,
        stderr: `\`${shown([command, ...args])}\` found problems in ${relative}. Fix them before moving on:\n${result.output.slice(-MAX_OUTPUT)}`,
      };
    }
  }
  return { code: 0 };
}

function main() {
  let input = {};
  try {
    input = JSON.parse(readFileSync(0, "utf8") || "{}");
  } catch {
    process.exit(0);
  }
  const projectDir =
    process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();
  const result = afterEdit(input, { projectDir });
  if (result.stderr) process.stderr.write(result.stderr);
  process.exit(result.code);
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
)
  main();
