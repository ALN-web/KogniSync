import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { journey } from "../test/fixtures";
import { JourneyCard } from "./JourneyCard";
import { ProvenanceBadge } from "./ProvenanceBadge";

describe("JourneyCard", () => {
  it("shows labels, totals, route and provenance", () => {
    render(<JourneyCard journey={journey()} />);
    expect(screen.getByText("Recommended")).toBeInTheDocument();
    expect(screen.getByText("Fastest")).toBeInTheDocument();
    expect(screen.getByText("₹6,900")).toBeInTheDocument();
    const route = screen.getByLabelText("Route");
    expect(within(route).getByText("Cab")).toBeInTheDocument();
    expect(within(route).getByText("Flight")).toBeInTheDocument();
    // Recommended cards open with details: every fare carries a label.
    expect(screen.getByText("IndiGo 6E-123")).toBeInTheDocument();
    expect(screen.getAllByText("live").length).toBeGreaterThan(0);
    expect(screen.getAllByText("scheduled").length).toBeGreaterThan(0);
    expect(screen.getAllByText("estimated").length).toBeGreaterThan(0);
  });

  it("calls onBook", () => {
    const onBook = vi.fn();
    render(<JourneyCard journey={journey()} onBook={onBook} />);
    fireEvent.click(screen.getByRole("button", { name: "Book" }));
    expect(onBook).toHaveBeenCalledWith(expect.objectContaining({ id: "J1" }));
  });
});

describe("ProvenanceBadge", () => {
  it("marks stale live data", () => {
    render(
      <ProvenanceBadge
        provenance={{ kind: "estimated", source: "mock:x", as_of: "", ttl_seconds: 600, stale: true }}
      />,
    );
    expect(screen.getByText("stale")).toHaveAttribute("title", expect.stringContaining("went stale"));
  });
});
