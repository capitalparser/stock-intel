import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

const source = resolve("../state/dashboard/cache/dashboard-latest.json");
const target = resolve("public/dashboard-latest.json");

mkdirSync(dirname(target), { recursive: true });

if (existsSync(source)) {
  copyFileSync(source, target);
}
