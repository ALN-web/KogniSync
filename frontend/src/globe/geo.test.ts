import { describe, expect, it } from "vitest";
import { journey, leg } from "../test/fixtures";
import {
  SURFACE_LIFT,
  angleBetween,
  arcPoints,
  cumulativeLengths,
  framing,
  journeyPaths,
  latLonToXyz,
  legColor,
  length,
  pointAt,
  sphereDots,
} from "./geo";

const BLR = latLonToXyz(13.1986, 77.7066);
const DEL = latLonToXyz(28.5562, 77.1);

describe("globe geometry", () => {
  it("puts points on the unit sphere with the north pole up", () => {
    expect(length(BLR)).toBeCloseTo(1, 9);
    expect(latLonToXyz(90, 0)[1]).toBeCloseTo(1, 9);
    expect(latLonToXyz(-90, 0)[1]).toBeCloseTo(-1, 9);
  });

  it("measures great-circle angles (BLR to DEL is about 1,700 km)", () => {
    const km = angleBetween(BLR, DEL) * 6371;
    expect(km).toBeGreaterThan(1650);
    expect(km).toBeLessThan(1800);
  });

  it("arcs flights above the surface and keeps ground legs on it", () => {
    const flight = arcPoints(BLR, DEL, "flight");
    const train = arcPoints(BLR, DEL, "train");
    expect(length(flight[0])).toBeCloseTo(1 + SURFACE_LIFT, 6);
    expect(length(flight[flight.length - 1])).toBeCloseTo(1 + SURFACE_LIFT, 6);
    expect(length(flight[Math.floor(flight.length / 2)])).toBeGreaterThan(1.05);
    expect(Math.max(...train.map(length))).toBeCloseTo(1 + SURFACE_LIFT, 6);
  });

  it("builds one path per leg and colors disrupted legs", () => {
    const j = journey();
    const paths = journeyPaths(j, { L1: "cancelled" });
    expect(paths.map((p) => p.mode)).toEqual(["cab", "flight"]);
    expect(legColor(paths[1])).toBe("#ff3b30");
    expect(legColor(paths[0])).toBe("#d7dbe0");
  });

  it("frames close for a city trip and far for an intercity one", () => {
    const local = journeyPaths(
      journey({
        legs: [
          leg({
            mode: "cab",
            origin: { name: "A", lat: 12.93, lon: 77.62, city: "BLR", kind: "address", code: null },
            destination: { name: "B", lat: 12.97, lon: 77.75, city: "BLR", kind: "address", code: null },
          }),
        ],
      }),
    ).flatMap((p) => p.points);
    const intercity = arcPoints(BLR, DEL, "flight");
    expect(framing(local).distance).toBeLessThan(framing(intercity).distance);
    expect(framing(local).distance).toBeGreaterThan(1);
  });

  it("moves the traveler at constant speed along the path", () => {
    const pts = arcPoints(BLR, DEL, "train", 10);
    const lens = cumulativeLengths(pts);
    expect(pointAt(pts, lens, 0)).toEqual(pts[0]);
    const end = pointAt(pts, lens, 1);
    pts[pts.length - 1].forEach((v, i) => expect(end[i]).toBeCloseTo(v, 9));
  });

  it("spaces land-dot candidates evenly (fewer near the poles)", () => {
    const dots = sphereDots(2);
    const equator = dots.filter((d) => d.lat === 0).length;
    const high = dots.filter((d) => d.lat === 80).length;
    expect(equator).toBe(180);
    expect(high).toBeLessThan(equator / 4);
  });
});
