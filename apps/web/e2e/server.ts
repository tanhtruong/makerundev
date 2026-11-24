import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { test as base } from "@playwright/test";

const ROOT = path.resolve(import.meta.dirname, "../../..");
const LAUNCHERS = "apps/server/tests";
const LISTENING = /Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/;

type ServerOptions = { app: string; serverEnv: Record<string, string> };

export const test = base.extend<ServerOptions & { server: string }>({
  app: ["makerundev_server.app:create_app", { option: true }],
  serverEnv: [{}, { option: true }],
  server: async ({ app, serverEnv }, provide) => {
    const dataDir = mkdtempSync(path.join(tmpdir(), "makerundev-e2e-"));
    const child = spawn(
      "uv",
      ["run", "uvicorn", app, "--factory", "--host", "127.0.0.1", "--port", "0", "--app-dir", LAUNCHERS],
      {
        cwd: ROOT,
        env: { ...process.env, ...serverEnv, MAKERUNDEV_DATA_DIR: dataDir },
        stdio: ["ignore", "ignore", "pipe"],
      },
    );
    const exited = new Promise<void>((resolve) => {
      child.once("exit", () => {
        resolve();
      });
    });
    try {
      const url = await new Promise<string>((resolve, reject) => {
        let log = "";
        child.stderr.on("data", (chunk: Buffer) => {
          log += chunk.toString();
          const match = LISTENING.exec(log);
          if (match?.[1]) resolve(match[1]);
        });
        child.once("exit", (code) => {
          reject(new Error(`${app} exited with ${String(code)} before it was listening:\n${log}`));
        });
      });
      await provide(url);
    } finally {
      if (child.exitCode === null) child.kill();
      await exited;
      rmSync(dataDir, { recursive: true, force: true });
    }
  },
  baseURL: async ({ server }, provide) => {
    await provide(server);
  },
});

export { expect } from "@playwright/test";
