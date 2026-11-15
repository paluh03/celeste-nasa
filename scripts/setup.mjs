/** Instalacion de dependencias: venv con uv + node_modules con bun. */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const root = import.meta.dir ? join(import.meta.dir, "..") : process.cwd();
const isWindows = process.platform === "win32";
// Bun ya esta resolviendo este script: usamos el mismo binario para los hijos.
const bun = process.versions.bun ? process.execPath : "bun";

function run(command, args, cwd) {
  console.log(`\n> ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    shell: isWindows && command.toLowerCase().endsWith(".cmd"),
  });
  if (result.status !== 0) {
    console.error(`Fallo: ${command} ${args.join(" ")}`);
    process.exit(result.status ?? 1);
  }
}

/** mise puede no estar en el PATH de esta terminal (instalado despues de abrirla). */
function resolveMise() {
  const candidates = [
    isWindows ? join(process.env.USERPROFILE ?? "", ".local", "bin", "mise.exe") : "",
    isWindows
      ? join(
          process.env.LOCALAPPDATA ?? "",
          "Microsoft",
          "WinGet",
          "Packages",
          "jdx.mise_Microsoft.Winget.Source_8wekyb3d8bbwe",
          "mise",
          "bin",
          "mise.exe",
        )
      : "",
    isWindows ? "mise.exe" : "mise",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate.includes("\\") || candidate.includes("/")) {
      if (existsSync(candidate)) return candidate;
      continue;
    }
    const probe = spawnSync(candidate, ["--version"], { stdio: "ignore" });
    if (probe.status === 0) return candidate;
  }
  return null;
}

// 1) Herramientas via mise (si esta disponible).
const mise = resolveMise();
if (mise) {
  run(mise, ["install"], root);
} else {
  console.warn("mise no encontrado: se usara el node/python/uv del PATH.");
}

// 2) Backend: uv crea backend/.venv y resuelve uv.lock.
if (mise) {
  run(mise, ["exec", "--", "uv", "sync", "--project", "backend"], root);
} else {
  run("uv", ["sync", "--project", "backend"], root);
}

// 3) Frontend.
run(bun, ["install"], join(root, "frontend"));

console.log("\n  Listo. Arranca con:  bun run dev\n");
