/**
 * Lanzador de desarrollo: API (uvicorn --reload) + web (Vite).
 *
 * Usa el Python del venv directamente para no depender de que `uv` este en el
 * PATH de la terminal, y `bun` para el frontend. Al cambiar un archivo de
 * backend/app, uvicorn reinicia solo; Vite recarga el navegador.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const root = import.meta.dir ? join(import.meta.dir, "..") : process.cwd();
const backend = join(root, "backend");
const frontend = join(root, "frontend");

const isWindows = process.platform === "win32";
const venvPython = join(backend, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
// Si el script corre con bun, reutilizamos ese mismo binario para el hijo:
// asi `bun run dev` funciona aunque bun no este en el PATH de la terminal.
const bun = process.versions.bun ? process.execPath : "bun";

function fail(message) {
  console.error(`\n  ${message}\n`);
  process.exit(1);
}

if (!existsSync(venvPython)) {
  fail(
    "No existe backend/.venv.\n" +
      "  Ejecuta:  mise install\n" +
      "            mise exec -- uv sync --project backend\n" +
      "  (o simplemente:  bun run setup)",
  );
}

if (!existsSync(join(frontend, "node_modules"))) {
  fail("Faltan dependencias del frontend. Ejecuta: bun run setup");
}

const children = [];
let shuttingDown = false;

function run(label, color, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, FORCE_COLOR: "1", PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });
  children.push(child);

  const prefix = `\x1b[${color}m[${label}]\x1b[0m `;
  const pipe = (stream, target) => {
    let buffer = "";
    stream.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) target.write(prefix + line + "\n");
    });
    stream.on("end", () => {
      if (buffer.trim()) target.write(prefix + buffer + "\n");
    });
  };
  pipe(child.stdout, process.stdout);
  pipe(child.stderr, process.stderr);

  child.on("exit", (code) => {
    if (shuttingDown) return;
    console.error(`${prefix}termino con codigo ${code}`);
    shutdown(code ?? 1);
  });
  return child;
}

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null) child.kill();
  }
  setTimeout(() => process.exit(code), 150);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

console.log("\n  NASA SPACE - entorno de desarrollo\n");
console.log("  API  http://127.0.0.1:8000/docs");
console.log("  Web  http://127.0.0.1:5173\n");

run(
  "api",
  "36",
  venvPython,
  ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
  backend,
);

run("web", "35", bun, ["run", "dev"], frontend);
