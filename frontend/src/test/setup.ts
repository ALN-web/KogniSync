import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom has no canvas implementation; return null like a browser without WebGL instead of
// logging "Not implemented" errors.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement["getContext"];
window.scrollTo = (() => undefined) as typeof window.scrollTo;
