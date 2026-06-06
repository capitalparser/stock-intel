import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { Evidence } from "../src/tabs/Evidence";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("evidence tab", () => {
  it("renders selected candidate inspector sections and technical details", () => {
    render(<Evidence snapshot={parseDashboardSnapshot(abbreviatedSnapshot)} />);

    expect(screen.getByRole("heading", { name: "ADI 근거" })).toBeInTheDocument();
    for (const label of ["밸류에이션", "품질", "성장", "이익상향", "모멘텀"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("독립성")).toBeInTheDocument();
    expect(screen.getByText("catalyst")).toBeInTheDocument();
    expect(screen.getByText("밸류에이션 기대치")).toBeInTheDocument();
    expect(screen.getByText("기술 세부정보")).toBeInTheDocument();
  });
});
