import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { journey, mockApi, trippass } from "../test/fixtures";
import { BookingDialog } from "./BookingDialog";

const hold = {
  id: "H1",
  journey_id: "J1",
  journey: journey(),
  passengers: 1,
  legs: [],
  total_due_now_inr: 6200,
  pay_later_estimate_inr: 700,
  expires_at: "2026-11-23T06:10:00+05:30",
  status: "held",
};

describe("BookingDialog", () => {
  it("needs two consents and sends idempotency keys", async () => {
    const calls = mockApi({
      "POST /api/v1/holds": { status: 201, body: hold },
      "POST /api/v1/bookings": { status: 201, body: trippass() },
    });
    const onBooked = vi.fn();
    render(<BookingDialog journey={journey()} onBooked={onBooked} onClose={() => undefined} />);

    const holdBtn = screen.getByRole("button", { name: "Hold seats" });
    expect(holdBtn).toBeDisabled();
    fireEvent.click(screen.getByLabelText("I want to hold these seats"));
    fireEvent.click(holdBtn);

    const pay = await screen.findByRole("button", { name: "Confirm and pay ₹6,200" });
    expect(pay).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I agree to pay ₹6,200 now/));
    fireEvent.click(pay);
    await waitFor(() => expect(onBooked).toHaveBeenCalled());

    const holdCall = calls.find((c) => c.key === "POST /api/v1/holds")!;
    const bookCall = calls.find((c) => c.key === "POST /api/v1/bookings")!;
    const holdKey = new Headers(holdCall.init!.headers).get("Idempotency-Key");
    const bookKey = new Headers(bookCall.init!.headers).get("Idempotency-Key");
    expect(holdKey).toBeTruthy();
    expect(bookKey).toBeTruthy();
    expect(holdKey).not.toEqual(bookKey);
    expect(JSON.parse(String(bookCall.init!.body))).toEqual({
      hold_id: "H1",
      expected_total_inr: 6200,
      consent: true,
    });
  });

  it("shows a clear error when the hold fails", async () => {
    mockApi({
      "POST /api/v1/holds": {
        status: 409,
        body: { detail: { code: "hold_failed", message: "Could not hold IndiGo: not enough seats left. Nothing was held." } },
      },
    });
    render(<BookingDialog journey={journey()} onBooked={vi.fn()} onClose={() => undefined} />);
    fireEvent.click(screen.getByLabelText("I want to hold these seats"));
    fireEvent.click(screen.getByRole("button", { name: "Hold seats" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Nothing was held");
  });
});

describe("BookingDialog keyboard", () => {
  it("closes on Escape and shows the step indicator", () => {
    mockApi({});
    const onClose = vi.fn();
    render(<BookingDialog journey={journey()} onBooked={vi.fn()} onClose={onClose} />);
    expect(screen.getByRole("list", { name: "Booking steps" })).toBeInTheDocument();
    expect(screen.getByText("Review")).toHaveAttribute("aria-current", "step");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    return waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
