#!/usr/bin/env node
// Stage unmodified CMake executables for Tauri v2 externalBin.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const option = (name) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
};
const rustc = spawnSync("rustc", ["-vV"], { encoding: "utf8" });
const detected = rustc.stdout?.match(/^host:\s*(\S+)/m)?.[1];
const triple = option("--target") || process.env.TAURI_ENV_TARGET_TRIPLE || detected;
if (!triple || !/^[a-zA-Z0-9_-]+$/.test(triple)) {
  throw new Error("Pass --target <rust target triple> or install rustc");
}
const build = path.resolve(root, option("--build-dir") || "build/studio5");
const staged = path.join(root, "apps", "studio", "src-tauri", "binaries");
fs.mkdirSync(staged, { recursive: true });
const ext = triple.includes("windows") ? ".exe" : "";

for (const name of ["plusminus_runner", "plusminus_native_tests"]) {
  const candidates = [
    path.join(build, name + ext),
    path.join(build, "Release", name + ext),
    path.join(build, "Debug", name + ext),
  ];
  const source = candidates.find((candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
  if (!source) throw new Error("Missing " + name + " in: " + candidates.join(", "));
  const destination = path.join(staged, name + "-" + triple + ext);
  fs.copyFileSync(source, destination);
  if (!ext) fs.chmodSync(destination, 0o755);
  console.log("Staged " + path.relative(root, destination));
}
