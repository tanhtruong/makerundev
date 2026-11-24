import { describe, expect, it } from "vitest";

import { syncOutcome } from "@/features/garmin/utils/sync-outcome";

const NOW = new Date("2026-11-21T12:00:00Z");

describe("how the last Garmin sync ended", () => {
  it.each([
    ["2026-11-21T12:02:00Z", "Garmin asked to slow down. Sync again in 2 minutes."],
    ["2026-11-21T12:01:01Z", "Garmin asked to slow down. Sync again in 2 minutes."],
    ["2026-11-21T12:00:30Z", "Garmin asked to slow down. Sync again in 1 minute."],
    ["2026-11-21T12:00:00Z", "Garmin asked to slow down. Sync again later."],
  ])("a pause until %s reads %s", (resumeAt, expected) => {
    expect(syncOutcome({ outcome: "paused", resume_at: resumeAt }, NOW)).toBe(expected);
  });
});
