import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// `npm run dev` proxies to the engine (python -m bluxtech_engine, port 8766); open http://localhost:5173/boot/<token>
// once (the engine prints the token), or start the engine with --no-auth. `npm run build` writes dist/, which the
// engine serves and the installer copies into the app's resources.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8766", changeOrigin: false },
      "/media": { target: "http://127.0.0.1:8766", changeOrigin: false },
      "/boot": { target: "http://127.0.0.1:8766", changeOrigin: false },
    },
  },
  build: { outDir: "dist", emptyOutDir: true, target: "es2022" },
});
