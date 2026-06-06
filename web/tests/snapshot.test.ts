import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { dashboardSnapshotSchema, getSnapshotErrorMessage } from "../src/data/snapshot";

describe("dashboard snapshot schema", () => {
  it("parses the abbreviated Lane B snapshot contract", () => {
    const parsed = dashboardSnapshotSchema.parse(abbreviatedSnapshot);

    expect(parsed.candidates[0].ticker).toBe("ADI");
    expect(parsed.dual_regime.transitions.kr.changed).toBe(true);
  });

  it("returns a user-safe parse failure message", () => {
    expect(getSnapshotErrorMessage({ candidates: "broken" })).toContain("상황판 데이터를 읽지 못했습니다");
  });
});
