import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { Summary } from "../src/tabs/Summary";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("summary tab", () => {
  it("renders dual regimes, transition badges, axis percentile, and KPI strip", () => {
    render(<Summary snapshot={parseDashboardSnapshot(abbreviatedSnapshot)} />);

    expect(screen.getByText("미국 국면")).toBeInTheDocument();
    expect(screen.getByText("한국 국면")).toBeInTheDocument();
    expect(screen.getByText("전환")).toBeInTheDocument();
    expect(screen.getByText("97%")).toBeInTheDocument();
    expect(screen.getByText("S&P 500 ETF")).toBeInTheDocument();
  });
});
