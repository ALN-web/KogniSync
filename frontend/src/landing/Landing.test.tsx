import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App, { viewFromHash } from "../App";
import { mockApi } from "../test/fixtures";
import { Landing } from "./Landing";

describe("Landing", () => {
  it("presents KogniSync content in the reference layout", () => {
    render(<Landing onOpen={vi.fn()} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Every leg.One journey.");
    expect(screen.getByText("7 modes")).toBeInTheDocument();
    expect(screen.getByText("14 hubs")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "One itinerary. Complete control." })).toBeInTheDocument();
    const cards = within(screen.getByRole("list", { name: "Capabilities" })).getAllByRole("listitem");
    expect(cards.map((c) => within(c).getByRole("heading").textContent)).toEqual([
      "Orchestrate",
      "Optimize",
      "Trust",
      "Book safely",
      "Protect",
      "Converse",
    ]);
    expect(screen.getByText("Demo data · no real bookings or payments")).toBeInTheDocument();
  });

  it("uses static backdrops with accessible labels when WebGL is missing", () => {
    render(<Landing onOpen={vi.fn()} />);
    expect(screen.getByRole("img", { name: /brushed-metal globe/ })).toHaveClass("three-fallback");
    expect(screen.getByRole("img", { name: /map pin/ })).toHaveClass("three-fallback");
  });

  it("opens the right part of the app", () => {
    const onOpen = vi.fn();
    render(<Landing onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /Plan your journey/ }));
    fireEvent.click(screen.getByRole("button", { name: "Open Protect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open Converse" }));
    expect(onOpen.mock.calls.map((c) => c[0])).toEqual(["plan", "trip", "copilot"]);
  });
});

describe("routing", () => {
  it("maps hashes to views and keeps section anchors on the landing page", () => {
    expect(viewFromHash("")).toBe("home");
    expect(viewFromHash("#capabilities")).toBe("home");
    expect(viewFromHash("#/plan")).toBe("plan");
    expect(viewFromHash("#/copilot")).toBe("copilot");
    expect(viewFromHash("#/nope")).toBe("home");
  });

  it("goes from the landing page into the planner and back", () => {
    mockApi({ "GET /api/v1/places": { body: { places: [] } } });
    window.location.hash = "";
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /Plan your journey/ }));
    expect(window.location.hash).toBe("#/plan");
    expect(screen.getByRole("form", { name: "Plan a journey" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "KogniSync home" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Every leg.");
  });
});
