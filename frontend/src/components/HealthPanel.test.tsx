import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HealthPanel } from "./HealthPanel";

function mockFetch(routes: Record<string, { status: number; body: unknown }>) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const route = routes[String(input)];
    if (!route) throw new TypeError("Failed to fetch");
    return new Response(JSON.stringify(route.body), { status: route.status });
  });
}

const liveness = {
  status: "ok",
  service: "KogniSync API",
  version: "0.1.0",
  environment: "local",
  time: "2026-11-17T00:00:00Z",
};

describe("HealthPanel", () => {
  it("shows ready status and each dependency", async () => {
    mockFetch({
      "/api/v1/health": { status: 200, body: liveness },
      "/api/v1/health/ready": {
        status: 200,
        body: {
          status: "ready",
          dependencies: [
            { name: "postgres", status: "not_configured", detail: null },
            { name: "gemini", status: "ok", detail: null },
          ],
        },
      },
    });

    render(<HealthPanel />);

    expect(await screen.findByText("ready")).toBeInTheDocument();
    expect(screen.getByText("postgres")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText("OK")).toBeInTheDocument();
  });

  it("shows degraded state from a 503 readiness response", async () => {
    mockFetch({
      "/api/v1/health": { status: 200, body: liveness },
      "/api/v1/health/ready": {
        status: 503,
        body: {
          status: "degraded",
          dependencies: [{ name: "redis", status: "error", detail: "unreachable" }],
        },
      },
    });

    render(<HealthPanel />);

    expect(await screen.findByText("degraded")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("shows an alert when the backend is unreachable", async () => {
    mockFetch({});

    render(<HealthPanel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unreachable");
  });
});
