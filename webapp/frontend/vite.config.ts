/// <reference types="vitest/config" />
// Dev server: `npm run dev` on :5173, forwarding the API to the FastAPI app on :8000.
// Build: static files in dist/, served by FastAPI (FRONTEND_DIR) in the Docker image.
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": backend, "/healthz": backend, "/docs": backend, "/openapi.json": backend },
  },
  test: { include: ["src/**/*.test.ts"] },
});
