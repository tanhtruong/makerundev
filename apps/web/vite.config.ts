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
const MAP_LICENSES = {
  "noto-sans.txt": "public/assets/map/fonts/OFL.txt",
  "protomaps-sprites.txt": "public/assets/map/sprites/LICENSE.md",
};

function assetLicenses(): Plugin {
  return {
    name: "asset-licenses",
    apply: "build",
    generateBundle() {
      const sources: [string, string][] = [
        ...FONTS.map((font): [string, string] => [`${font}.txt`, `node_modules/@fontsource/${font}/LICENSE`]),
        ...Object.entries(MAP_LICENSES),
      ];
      for (const [name, source] of sources) {
        this.emitFile({
          type: "asset",
          fileName: `licenses/${name}`,
          source: readFileSync(path.resolve(import.meta.dirname, source)),
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
    assetLicenses(),
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
