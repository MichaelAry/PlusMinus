#!/usr/bin/env node
// Stage unmodified CMake executables for Tauri v2 externalBin.
import fs from "node:fs";
import {createHash} from "node:crypto";
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

/** Hash the exact original source set that is built into each sidecar.
 * The sidecar and manifest are staged together after the CMake build. */
function buildFingerprint() {
  const hash = createHash("sha256");
  const files = [];
  function visit(dir) {
    for (const entry of fs.readdirSync(dir, {withFileTypes:true})) {
      const file = path.join(dir,entry.name);
      if (entry.isDirectory()) visit(file);
      else if (entry.isFile() && /\.(cpp|hpp|h)$/.test(entry.name)) files.push(file);
    }
  }
  for (const folder of ["src","include","tests/cpp","tests/portable"]) {
    const base=path.join(root,folder);
    if (fs.existsSync(base)) {
      files.length=0; visit(base);
      files.sort();
      for (const file of files) {
        hash.update(path.relative(root,file),"utf8");
        hash.update(fs.readFileSync(file));
      }
    }
  }
  for (const relative of ["CMakeLists.txt","ide/CMakeLists.txt","ide/runner.cpp",
    "Parser.h","tools/generate_native_tests.py"]) {
    const file=path.join(root,relative);
    if (fs.existsSync(file)) {
      hash.update(relative.split("/").join(path.sep),"utf8");
      hash.update(fs.readFileSync(file));
    }
  }
  return hash.digest("hex");
}
const manifest=path.join(staged,"source-fingerprint.json");
fs.writeFileSync(manifest,JSON.stringify({schema:1,sha256:buildFingerprint()},null,2)+"\n","utf8");
console.log("Staged source fingerprint for native sidecars");
