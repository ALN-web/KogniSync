/** Land dot positions from Natural Earth (public domain), shared by every 3D scene. */
import { geoEquirectangular, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import land110 from "world-atlas/land-110m.json";
import { latLonToXyz, sphereDots } from "./geo";

function landMask(width: number, height: number): (lat: number, lon: number) => boolean {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return () => false;
  const projection = geoEquirectangular()
    .scale(width / (2 * Math.PI))
    .translate([width / 2, height / 2]);
  const topo = land110 as unknown as Topology;
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  geoPath(projection, ctx)(feature(topo, topo.objects.land));
  ctx.fill();
  const data = ctx.getImageData(0, 0, width, height).data;
  return (lat, lon) => {
    const x = Math.min(width - 1, Math.floor(((lon + 180) / 360) * width));
    const y = Math.min(height - 1, Math.floor(((90 - lat) / 180) * height));
    return data[(y * width + x) * 4] > 128;
  };
}

const cache = new Map<string, Float32Array>();

/** xyz triples for dots on land, `stepDeg` apart, at `radius`. */
export function landPositions(stepDeg = 0.75, radius = 1.001): Float32Array {
  const key = `${stepDeg}:${radius}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const isLand = landMask(1024, 512);
  const dots = sphereDots(stepDeg).filter((d) => isLand(d.lat, d.lon));
  const out = new Float32Array(dots.length * 3);
  dots.forEach((d, i) => out.set(latLonToXyz(d.lat, d.lon, radius), i * 3));
  cache.set(key, out);
  return out;
}
