/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Read VITE_* variables from the single repo-root .env file.
  envDir: "..",
  server: {
    port: 5173,
    // In local dev the frontend calls /api/... and Vite forwards it to FastAPI.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    // The lazily loaded 3D globe chunk (three.js + land data) is ~160 kB gzipped by design.
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
