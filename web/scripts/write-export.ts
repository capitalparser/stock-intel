import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { parseDashboardSnapshot } from "../src/data/snapshot";
import { exportSnapshot } from "../src/export/snapshotExport";

const source = resolve("public/dashboard-latest.json");
const target = resolve("dist/snapshot-export.html");
const snapshot = parseDashboardSnapshot(JSON.parse(readFileSync(source, "utf8")));
const generatedAt = new Date(process.env.EXPORT_TIMESTAMP ?? new Date().toISOString());

const html = exportSnapshot({
  scope: "all_tabs",
  currentTab: "요약",
  snapshot,
  generatedAt,
  source: { dashboardName: "개인 투자 상황판", userOrService: "04_stock_intel" },
  dataWindow: { from: snapshot.as_of, to: snapshot.price_time ?? snapshot.generated_at ?? snapshot.as_of },
});

mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, html, "utf8");
console.log(target);
