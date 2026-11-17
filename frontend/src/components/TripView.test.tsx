import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { journey, mockApi, trippass } from "../test/fixtures";
import { TripView } from "./TripView";

const critical = {
  severity: "critical",
  legs: [
    { leg_id: "L0", mode: "cab", provider: "Uber / Ola", status: "on_time", expected_arrive: null, delay_min: 0 },
    { leg_id: "L1", mode: "flight", provider: "IndiGo 6E-123", status: "cancelled", expected_arrive: null, delay_min: 0 },
  ],
  first_broken_leg: 1,
  expected_arrival: null,
  arrival_delay_min: null,
  deadline_missed: false,
  based_on_stale_data: false,
  summary: "IndiGo 6E-123 is cancelled. See recovery options.",
};

describe("TripView", () => {
  it("shows PNRs, simulates a cancellation and lists recovery options", async () => {
    let impact: unknown = { ...critical, severity: "none", summary: "No disruptions affect this trip.", legs: [] };
    const calls = mockApi({
      "GET /api/v1/trippass/TP-ABC12345/impact": () => ({ body: impact }),
      "DELETE /api/v1/disruptions": { status: 204 },
      "POST /api/v1/disruptions": () => {
        impact = critical;
        return { status: 201, body: {} };
      },
      "POST /api/v1/trippass/TP-ABC12345/recovery": {
        body: {
          impact: critical,
          replaces_from_leg: 1,
          options: [journey({ id: "J9", labels: ["recommended"] })],
          requires_consent: true,
          note: "Nothing changes until you choose one and confirm the booking.",
        },
      },
    });
    const onBook = vi.fn();
    render(<TripView trippass={trippass()} onBook={onBook} />);

    expect(screen.getByText("PNR XK42QZ")).toBeInTheDocument();
    expect(screen.getByAltText("QR code for TripPass TP-ABC12345")).toHaveAttribute(
      "src",
      "/api/v1/trippass/TP-ABC12345/qr.svg",
    );
    expect(await screen.findByText("No disruptions affect this trip.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel flight" }));
    expect(await screen.findByText(/is cancelled/)).toBeInTheDocument();
    const sim = calls.find((c) => c.key === "POST /api/v1/disruptions")!;
    expect(JSON.parse(String(sim.init!.body))).toEqual({ kind: "cancellation", service_id: "6E-123-2026-11-23" });

    fireEvent.click(screen.getByRole("button", { name: "Find recovery options" }));
    expect(await screen.findByText(/Nothing changes until you choose/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review and book" }));
    expect(onBook).toHaveBeenCalledWith(expect.objectContaining({ id: "J9" }));
  });
});
