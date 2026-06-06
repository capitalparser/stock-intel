import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";

describe("App scaffold", () => {
  it("renders the local cockpit label", () => {
    render(<App />);

    expect(screen.getByText("개인 투자 상황판")).toBeInTheDocument();
  });
});
