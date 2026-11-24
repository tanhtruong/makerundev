import type { APIRequestContext } from "@playwright/test";

import { expect, test } from "./server";

const DAY_MS = 86_400_000;
const LOCAL_DAY = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Europe/Copenhagen",
});

function daysAgo(days: number): Date {
  const start = new Date(Date.now() - days * DAY_MS);
  start.setUTCHours(10, 0, 0, 0);
  return start;
}

function tcx(start: Date, metres: number, seconds: number, heartRate: number | null): string {
  const points = Array.from({ length: seconds + 1 }, (_, i) => {
    const time = new Date(start.getTime() + i * 1000).toISOString().replace(".000", "");
    const hr = heartRate === null ? "" : `<HeartRateBpm><Value>${heartRate}</Value></HeartRateBpm>`;
    return `<Trackpoint><Time>${time}</Time><DistanceMeters>${((metres * i) / seconds).toFixed(3)}</DistanceMeters>${hr}</Trackpoint>`;
  });
  return `<?xml version="1.0"?><TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Activities><Activity Sport="Running"><Id>${start.toISOString()}</Id><Lap StartTime="${start.toISOString()}"><Track>${points.join("")}</Track></Lap></Activity></Activities></TrainingCenterDatabase>`;
}

async function seed(request: APIRequestContext, runs: { file: string; xml: string }[]): Promise<void> {
  const settings = await request.put("/api/settings", {
    data: {
      max_heart_rate_bpm: 190,
      resting_heart_rate_bpm: 50,
      trimp_coefficients: "male",
      zone_model: "max_hr_percent",
      zone_thresholds_percent: [60, 70, 80, 90],
      body_mass_kg: null,
      timezone: "Europe/Copenhagen",
    },
  });
  expect(settings.ok()).toBe(true);
  for (const run of runs) {
    const imported = await request.post("/api/activities", {
      multipart: {
        files: { name: run.file, mimeType: "application/vnd.garmin.tcx+xml", buffer: Buffer.from(run.xml) },
      },
    });
    expect(imported.ok()).toBe(true);
  }
}

test("training load shows current performance, switches range in the URL and lists the weeks", async ({
  page,
  request,
}) => {
  const reps = daysAgo(4);
  const tempo = daysAgo(2);
  await seed(request, [
    { file: "reps.tcx", xml: tcx(reps, 1000, 200, 170) },
    { file: "tempo.tcx", xml: tcx(tempo, 5000, 1250, 165) },
    { file: "old.tcx", xml: tcx(daysAgo(200), 3000, 900, null) },
  ]);
  const origins = new Set<string>();
  page.on("request", (sent) => origins.add(new URL(sent.url()).origin));

  await page.goto("/load");

  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Training load" }),
  ).toHaveAttribute("aria-current", "page");
  const performance = page.getByRole("region", { name: "Performance, last 6 weeks" });
  await expect(performance).toContainText(`VDOT52.21 km in 3:20, reps.tcx, ${LOCAL_DAY.format(reps)}`);
  await expect(performance).toContainText("Critical speed4:32 /kmD′ 213 m");
  await expect(performance.getByRole("list", { name: "Critical speed fitted on" }).getByRole("listitem")).toHaveText([
    `1 km in 3:20, reps.tcx, ${LOCAL_DAY.format(reps)}`,
    `1 mile in 6:42, tempo.tcx, ${LOCAL_DAY.format(tempo)}`,
    `3 km in 12:30, tempo.tcx, ${LOCAL_DAY.format(tempo)}`,
  ]);

  const ranges = page.getByRole("navigation", { name: "Range" });
  const load = page.getByRole("region", { name: "Fitness, fatigue and form" });
  const weeks = page.getByRole("table", { name: "By week" }).getByRole("row");
  await expect(ranges.getByRole("link", { name: "180 days" })).toHaveAttribute("aria-current", "page");
  await expect(weeks).toHaveCount(27);
  await expect(page.getByRole("img", { name: "Fitness and fatigue by day" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Form by day" })).toBeVisible();

  await ranges.getByRole("link", { name: "90 days" }).click();
  await expect(page).toHaveURL(/\/load\?days=90$/);
  await expect(weeks).toHaveCount(14);
  await expect(load).toContainText("Activities2");
  await expect(load).not.toContainText("had no heart rate");

  await ranges.getByRole("link", { name: "All" }).click();
  await expect(page).toHaveURL(/\/load\?days=all$/);
  await expect(load).toContainText("Activities3");
  await expect(load).toContainText("1 activity in this range had no heart rate, so it counts as 0.");
  expect([...origins]).toEqual([new URL(page.url()).origin]);

  await page.goto("/load?days=7");
  await expect(ranges.getByRole("link", { name: "180 days" })).toHaveAttribute("aria-current", "page");
  await expect(weeks).toHaveCount(27);
});
