import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { journey, mockApi } from "../test/fixtures";
import { Copilot } from "./Copilot";

const reply = {
  answer: "I found 5 options from Udayapalya to Connaught Place (demo data).",
  ai_mode: "fallback",
  tool_calls: [{ name: "search_journeys", args: {}, ok: true }],
  journeys: [
    {
      journey_id: "J1",
      labels: ["recommended"],
      route: "cab -> flight (IndiGo 6E-123, fare live)",
      depart: "Mon 23 Nov 08:30",
      arrive: "Mon 23 Nov 14:10",
      duration: "5 h 40 min",
      cost_inr: 6900,
      cost_display: "₹6,900",
      cost_provenance: "estimated",
      carbon_kg: 180.2,
    },
  ],
  proposed_action: {
    type: "hold",
    journey_id: "J1",
    passengers: 1,
    cost_inr: 6900,
    cost_provenance: "estimated",
    summary: "cab -> flight",
  },
  grounding: { verified: true, ungrounded_amounts: [] },
  notice: null,
};

describe("Copilot", () => {
  it("chats, shows tool use and hands proposals to the booking flow", async () => {
    const calls = mockApi({
      "GET /api/v1/copilot/status": { body: { gemini_configured: false, model: "m", omni_model: "m" } },
      "POST /api/v1/copilot/chat": { body: reply },
      "GET /api/v1/journeys/J1": { body: journey() },
    });
    const onReview = vi.fn();
    render(<Copilot trippassId="TP-1" onReviewJourney={onReview} />);
    expect(await screen.findByText("Offline planner (no API key)")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Udayapalya to CP Delhi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/I found 5 options/)).toBeInTheDocument();
    expect(screen.getByText(/tools: search_journeys/)).toBeInTheDocument();
    expect(screen.getByText(/prices verified/)).toBeInTheDocument();
    const body = JSON.parse(String(calls.find((c) => c.key === "POST /api/v1/copilot/chat")!.init!.body));
    expect(body.context.trippass_id).toBe("TP-1");

    fireEvent.click(screen.getByRole("button", { name: "Review and hold (₹6,900)" }));
    await waitFor(() => expect(onReview).toHaveBeenCalledWith(expect.objectContaining({ id: "J1" })));
  });

  it("explains that photos need a Gemini key", async () => {
    mockApi({
      "GET /api/v1/copilot/status": { body: { gemini_configured: false, model: "m", omni_model: "m" } },
      "POST /api/v1/copilot/vision": { status: 503, body: { detail: { code: "ai_not_configured" } } },
    });
    const { container } = render(<Copilot onReviewJourney={vi.fn()} />);
    const input = container.querySelector('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File(["x"], "t.jpg", { type: "image/jpeg" })] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("needs a Gemini API key");
  });
});
