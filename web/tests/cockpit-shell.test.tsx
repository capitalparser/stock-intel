import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { CockpitApp } from "../src/cockpit/CockpitApp";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("cockpit shell", () => {
  it("renders the executive cockpit shell with the five common tabs", async () => {
    render(<CockpitApp snapshot={parseDashboardSnapshot(abbreviatedSnapshot)} />);

    expect(await screen.findByTestId("cockpit-shell")).toHaveAttribute("data-cockpit-profile", "executive_cockpit");
    expect(screen.getByRole("heading", { name: "개인 투자 상황판" })).toBeInTheDocument();
    for (const label of ["요약", "진행현황", "주의 필요", "근거", "다음 행동"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });
});
