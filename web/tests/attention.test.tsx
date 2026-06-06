import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { Attention } from "../src/tabs/Attention";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("attention tab", () => {
  it("renders required filter badges and matching caution rows", () => {
    render(<Attention snapshot={parseDashboardSnapshot(abbreviatedSnapshot)} />);

    for (const label of ["차단", "과열", "위험", "공매도", "데이터부족"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByText("ADI")).toBeInTheDocument();
    expect(screen.getByText("독립성 확인 필요")).toBeInTheDocument();
  });
});
