import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { journey, mockApi } from "../test/fixtures";
import { PlanPage } from "./PlanPage";

const result = {
  search_id: "S1",
  origin: { name: "Udayapalya", lat: 0, lon: 0, city: "BLR", kind: "address", code: null },
  destination: { name: "Connaught Place", lat: 0, lon: 0, city: "DEL", kind: "address", code: null },
  journeys: [
    journey({ id: "JA", labels: ["recommended", "fastest"], cost_inr: 7000, duration_min: 400, score: 0.1 }),
    journey({ id: "JB", labels: ["cheapest"], cost_inr: 3400, duration_min: 2400, score: 0.5 }),
  ],
  considered: 140,
  pareto_size: 20,
  rejected: { over_budget: 3 },
  relaxation_hints: [],
  time_objective: "arrival",
  data_mode: "mock",
};

describe("PlanPage", () => {
  it("searches, sorts and swaps", async () => {
    mockApi({ "GET /api/v1/places": { body: { places: [] } }, "POST /api/v1/journeys/search": { body: result } });
    render(<PlanPage onBook={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Swap start and destination" }));
    expect(screen.getByLabelText("From")).toHaveValue("Connaught Place");
    fireEvent.click(screen.getByRole("button", { name: "Swap start and destination" }));

    fireEvent.click(screen.getByRole("button", { name: /Plan door to door/ }));
    const results = await screen.findByRole("region", { name: "Results" });
    expect(within(results).getByText(/140 options checked, 20 on the Pareto front · 3 over budget/)).toBeInTheDocument();
    const order = () => within(results).getAllByRole("article").map((a) => a.getAttribute("aria-label"));
    expect(order()).toEqual(["Journey JA", "Journey JB"]);
    fireEvent.click(screen.getByRole("button", { name: "Cheapest" }));
    expect(order()).toEqual(["Journey JB", "Journey JA"]);
    expect(screen.getByRole("button", { name: "Cheapest" })).toHaveAttribute("aria-pressed", "true");
  });
});
