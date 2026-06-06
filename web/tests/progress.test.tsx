import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { abbreviatedSnapshot } from "./fixtures/abbreviated-snapshot";
import { Progress } from "../src/tabs/Progress";
import { parseDashboardSnapshot } from "../src/data/snapshot";

describe("progress tab", () => {
  it("renders candidate table columns and omits sparkline when no price series exists", () => {
    render(<Progress snapshot={parseDashboardSnapshot(abbreviatedSnapshot)} />);

    expect(screen.getByRole("columnheader", { name: "매력도" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "PER" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "렌즈" })).toBeInTheDocument();
    expect(screen.getByText("BLOCKED 확인")).toBeInTheDocument();
    expect(screen.queryByLabelText("ADI 가격 흐름")).not.toBeInTheDocument();
  });
});
