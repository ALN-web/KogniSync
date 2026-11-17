import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { journey } from "../test/fixtures";
import { JourneyGlobe, declutter, routeDescription, webglAvailable } from "./JourneyGlobe";

describe("JourneyGlobe", () => {
  it("falls back to a text description without WebGL", () => {
    expect(webglAvailable()).toBe(false); // jsdom has no WebGL
    render(<JourneyGlobe journey={journey()} />);
    const fallback = screen.getByRole("img");
    expect(fallback).toHaveAccessibleName(/Route from BLR to DEL by cab, then flight/);
    expect(screen.getByText(/3D view needs WebGL/)).toBeInTheDocument();
  });

  it("drops overlapping hub labels but always keeps endpoints", () => {
    const at = (id: string, x: number, y: number, kind: "hub" | "endpoint") => ({
      id, text: id, x, y, visible: true, kind,
    });
    const kept = declutter([
      at("Delhi NCR", 100, 100, "hub"),
      at("Jaipur", 105, 104, "hub"),
      at("Connaught Place", 102, 102, "endpoint"),
      at("Chennai", 300, 300, "hub"),
      { ...at("Hidden", 500, 500, "hub"), visible: false },
    ]).map((l) => l.id);
    expect(kept).toEqual(["Connaught Place", "Chennai"]);
  });

  it("describes the hub view when no journey is selected", () => {
    expect(routeDescription(null)).toMatch(/14 KogniSync hub cities/);
  });
});
