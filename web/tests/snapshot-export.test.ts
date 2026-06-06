import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { exportSnapshot, extractInlineScripts, validateSwitcherContracts } from "../src/export/snapshotExport";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("snapshot export", () => {
  it("exports a self-contained full cockpit HTML snapshot", () => {
    const html = exportSnapshot({
      scope: "all_tabs",
      currentTab: "요약",
      snapshot: parseDashboardSnapshot(abbreviatedSnapshot),
      generatedAt: new Date("2026-06-06T09:00:00+09:00"),
      source: { dashboardName: "개인 투자 상황판", userOrService: "04_stock_intel" },
      dataWindow: { from: "2026-06-05", to: "2026-06-05" },
    });

    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(html).toContain("data-switcher=\"main\"");
    expect(html).toContain("data-filter-control=\"#attention-export\"");
    expect(html).toContain("2026-06-06T09:00:00+09:00");
    expect(html).toContain("data hash");
    expect(html).not.toMatch(/(?:src|href)=["']http/i);
    expect(validateSwitcherContracts(html)).toEqual([]);
    expect(extractInlineScripts(html).join("\n")).toContain("document.querySelectorAll('[data-switcher]')");
  });
});
