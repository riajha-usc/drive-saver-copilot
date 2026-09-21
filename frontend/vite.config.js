import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In production the API and this app are the same origin, served by FastAPI out
// of one container, so every call is a relative path and there is no CORS.
// `npm run dev` runs on its own port, so these prefixes are proxied to a local
// API to keep those relative paths working while developing.
const API_PREFIXES = ["/health", "/model", "/datasets", "/telemetry", "/recommendations", "/docs", "/openapi.json"];
const target = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PREFIXES.map((p) => [p, { target, changeOrigin: true }])
    ),
  },
  build: {
    outDir: "dist",
    // Not the Vite default of "assets". The API serves this app from the same
    // origin, and /assets/:id is the natural client route for an asset page, so
    // the build output would sit exactly where the dashboard wants to route.
    assetsDir: "static",
  },
});
