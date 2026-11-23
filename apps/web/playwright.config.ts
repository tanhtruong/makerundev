import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const PORT = 8777;
const dataDir = mkdtempSync(path.join(tmpdir(), "makerundev-e2e-"));

export default defineConfig({
  testDir: "e2e",
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], timezoneId: "Europe/Copenhagen" } }],
  webServer: {
    command: "uv run makerundev-server",
    cwd: path.resolve(import.meta.dirname, "../.."),
    url: `http://127.0.0.1:${PORT}/api/activities`,
    env: { MAKERUNDEV_DATA_DIR: dataDir, MAKERUNDEV_PORT: String(PORT) },
    reuseExistingServer: false,
  },
});
