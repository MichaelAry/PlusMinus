#!/usr/bin/env node
// Smoke the unmodified C++ executable directly, not a mocked JSON-RPC server.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const pos = args.indexOf("--build-dir");
const dir = path.resolve(root, pos < 0 ? "build/studio5" : args[pos + 1]);
const ext = process.platform === "win32" ? ".exe" : "";
function locate(name) {
  const found = [path.join(dir, name + ext), path.join(dir, "Release", name + ext),
    path.join(dir, "Debug", name + ext)].find((file) => fs.existsSync(file));
  if (!found) throw new Error("Missing native executable: " + name);
  return found;
}
const runner = locate("plusminus_runner");
function run(mode, source) {
  const result = spawnSync(runner, [mode], {
    input: source, encoding: "utf8", maxBuffer: 10 * 1024 * 1024, timeout: 10_000,
  }); // spawnSync writes UTF-8 input, closes stdin (EOF), and waits.
  if (result.error) throw result.error;
  const data = JSON.parse(result.stdout);
  if (typeof data.ok !== "boolean" || typeof data.output !== "string" ||
      typeof data.result !== "string" || !Array.isArray(data.diagnostics) ||
      !Array.isArray(data.trace) || typeof data.metrics !== "object") {
    throw new Error("Native report schema invalid in " + mode);
  }
  return { data, code: result.status };
}
function assert(ok, message) { if (!ok) throw new Error(message); }

let {data,code} = run("run", "print(2 + 3);\n");
assert(code === 0 && data.ok && data.output.includes("5"), "Run did not execute C++ VM");
({data,code} = run("compile", "print(1);\n"));
assert(code === 0 && data.ok && data.bytecode.length > 0, "Compile missing bytecode");
({data,code} = run("profile", "print(1);\n"));
assert(code === 0 && data.ok && typeof data.metrics.opcode_hits === "object", "Profile missing counts");
({data,code} = run("trace", "print(1);\n"));
assert(code === 0 && data.ok && data.trace.length > 0, "Trace missing events");
({data,code} = run("run", "x = 2;\n"));
assert(code === 0 && data.ok && data.output === "", "Empty stdout was lost");

const native = spawnSync(locate("plusminus_native_tests"), ["--list"], {
  encoding: "utf8", timeout: 12_000, maxBuffer: 1024 * 1024,
});
if (native.error) throw native.error;
assert(native.status === 0, "Cannot list native tests");
const tests = native.stdout.trim().split(/\r?\n/).map((s) => JSON.parse(s));
assert(tests.length === 225 && tests.every((t) => t.type === "test"), "Expected 225 native tests");
console.log("Native C++ runner smoke: run/compile/profile/trace/empty stdout and 225 test listing passed");
