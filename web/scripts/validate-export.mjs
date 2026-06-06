import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const file = resolve(process.argv[2] ?? "dist/snapshot-export.html");
const html = readFileSync(file, "utf8");
const withoutScripts = html.replace(/<script>[\s\S]*?<\/script>/g, "");

if (!html.startsWith("<!doctype html>")) throw new Error("Export must start with <!doctype html>");
if (/(?:src|href)=["']http/i.test(html)) throw new Error("Export contains CDN/network assets");

const targets = [...withoutScripts.matchAll(/data-target="([^"]+)"/g)].map((match) => match[1]).sort();
const panels = [...withoutScripts.matchAll(/data-panel="([^"]+)"/g)].map((match) => match[1]).sort();
if (JSON.stringify(targets) !== JSON.stringify(panels)) {
  throw new Error(`Switcher target/panel mismatch: ${targets.join(",")} vs ${panels.join(",")}`);
}

const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
if (scripts.length === 0) throw new Error("Export has no inline runtime script");

scripts.forEach((script, index) => {
  const scriptFile = `/private/tmp/stock-intel-export-runtime-${index}.js`;
  writeFileSync(scriptFile, script, "utf8");
  execFileSync("node", ["--check", scriptFile], { stdio: "inherit" });
});

console.log(`validated ${file}`);
