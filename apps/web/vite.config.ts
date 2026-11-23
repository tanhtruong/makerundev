import { readFileSync } from "node:fs";
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

import { SERVER_PATHS } from "./src/lib/server-pages";

const SERVER = "http://127.0.0.1:8000";
const FONTS = ["barlow", "barlow-semi-condensed", "barlow-condensed"];

function fontLicenses(): Plugin {
  return {
    name: "font-licenses",
    apply: "build",
    generateBundle() {
      for (const font of FONTS) {
        this.emitFile({
          type: "asset",
          fileName: `licenses/${font}.txt`,
          source: readFileSync(path.resolve(import.meta.dirname, "node_modules/@fontsource", font, "LICENSE")),
        });
      }
    },
  };
}

export default defineConfig({
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
      routesDirectory: "src/app/routes",
      generatedRouteTree: "src/app/route-tree.gen.ts",
      routeFileIgnorePattern: "\\.test\\.",
    }),
    react(),
    tailwindcss(),
    fontLicenses(),
  ],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  build: {
    outDir: "../server/src/makerundev_server/web",
    emptyOutDir: true,
    license: { fileName: "third-party-licenses.md" },
  },
  server: {
    proxy: Object.fromEntries(SERVER_PATHS.map((prefix) => [prefix, SERVER])),
  },
  test: {
    environment: "jsdom",
    env: { TZ: "Europe/Copenhagen" },
    setupFiles: ["src/testing/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
