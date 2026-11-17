import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mockApi } from "../test/fixtures";
import { SearchForm } from "./SearchForm";

describe("SearchForm", () => {
  it("submits hard limits and mode preferences", () => {
    mockApi({ "GET /api/v1/places": { body: { places: [] } } });
    const onSearch = vi.fn();
    render(<SearchForm onSearch={onSearch} />);
    fireEvent.change(screen.getByLabelText("Budget, ₹ (hard limit)"), { target: { value: "8000" } });
    fireEvent.change(screen.getByLabelText("Arrive by (hard limit)"), { target: { value: "2026-11-24T10:00" } });
    fireEvent.click(screen.getByLabelText("Prefer Train"));
    fireEvent.click(screen.getByLabelText("Avoid Flight"));
    fireEvent.click(screen.getByRole("button", { name: "Plan door to door" }));
    expect(onSearch).toHaveBeenCalledWith({
      origin: "Udayapalya, Bengaluru",
      destination: "Connaught Place",
      arrive_by: "2026-11-24T10:00",
      budget_inr: 8000,
      prefer_modes: ["train"],
      avoid_modes: ["flight"],
    });
  });
});
