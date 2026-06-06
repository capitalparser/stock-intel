import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { NextActions } from "../src/tabs/NextActions";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("next actions tab", () => {
  it("renders candidate and market-regime next actions", () => {
    render(<NextActions snapshot={parseDashboardSnapshot(abbreviatedSnapshot)} />);

    expect(screen.getByText("후보별 다음 행동")).toBeInTheDocument();
    expect(screen.getByText("수주 언급 추적")).toBeInTheDocument();
    expect(screen.getByText("국면 다음 행동")).toBeInTheDocument();
    expect(screen.getByText("후보 압축")).toBeInTheDocument();
  });
});
