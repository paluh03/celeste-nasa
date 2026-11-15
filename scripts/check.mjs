/** Verificación completa: ruff + pytest + tsc + vitest, en ese orden. */
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const root = import.meta.dir ? join(import.meta.dir, "..") : process.cwd();
const isWindows = process.platform === "win32";
const venvPython = join(root, "backend", ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const bun = process.versions.bun ? process.execPath : "bun";

const steps = [
  { label: "ruff", command: venvPython, args: ["-m", "ruff", "check", "."], cwd: join(root, "backend") },
  { label: "pytest", command: venvPython, args: ["-m", "pytest", "-q"], cwd: join(root, "backend") },
  { label: "tsc", command: bun, args: ["run", "lint"], cwd: join(root, "frontend") },
  { label: "vitest", command: bun, args: ["run", "test"], cwd: join(root, "frontend") },
];

const lintOnly = process.argv.includes("--lint");
const selected = lintOnly ? steps.filter((step) => ["ruff", "tsc"].includes(step.label)) : steps;

for (const step of selected) {
  console.log(`\n=== ${step.label} ===`);
  const result = spawnSync(step.command, step.args, { cwd: step.cwd, stdio: "inherit" });
  if (result.status !== 0) {
    console.error(`\nFallo en ${step.label} (codigo ${result.status}).`);
    process.exit(result.status ?? 1);
  }
}

console.log("\nTodo verde.\n");
