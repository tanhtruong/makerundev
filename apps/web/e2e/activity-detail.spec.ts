import { gpx } from "./gpx";
import { expect, test } from "./server";

const SETTINGS = {
  max_heart_rate_bpm: 190,
  resting_heart_rate_bpm: 50,
  trimp_coefficients: "male",
  zone_model: "max_hr_percent",
  zone_thresholds_percent: [60, 70, 80, 90],
  body_mass_kg: 70,
  timezone: "America/New_York",
};

function tempo(): string {
  let point = 0;
  return gpx("Canal tempo", "2026-03-01T07:00:00Z", 3).replace(/<time>[^<]+<\/time>/g, (time) => {
    const hr = point < 15 ? 140 : 155;
    const ele = 10 + point;
    point += 1;
    return `<ele>${ele}</ele>${time}<extensions><hr>${hr}</hr><power>250</power></extensions>`;
  });
}

test("an activity page draws the run, links its charts on hover and excludes it from VDOT", async ({
  page,
  request,
}) => {
  expect((await request.put("/api/settings", { data: SETTINGS })).ok()).toBe(true);
  const imported = await request.post("/api/activities", {
    multipart: { files: { name: "canal.gpx", mimeType: "application/gpx+xml", buffer: Buffer.from(tempo()) } },
  });
  const { results } = (await imported.json()) as { results: { activity_id: number }[] };

  await page.goto(`/activities/${results[0]?.activity_id}`);

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Running on 1 Mar 2026 at 02:00");
  await expect(page).toHaveTitle("Canal tempo - makerundev");
  await expect(page.getByText("Canal tempo · canal.gpx")).toBeVisible();
  const summary = page.getByLabel("Summary");
  await expect(summary.getByRole("definition").first()).toHaveText("3.00 km");
  await expect(summary.getByText("3.57 W/kg")).toBeVisible();
  await expect(page.getByRole("region", { name: "Splits" }).getByRole("row")).toHaveCount(4);
  await expect(page.getByRole("img", { name: "Route shape, north up" })).toBeVisible();
  const zones = page.getByRole("region", { name: "Time in zones" });
  await expect(zones.getByRole("row")).toHaveCount(6);
  await expect(zones.getByTestId("zone-bar")).toHaveCount(2);

  const pace = await page.getByRole("application", { name: "Pace over distance" }).boundingBox();
  if (!pace) throw new Error("the pace chart is not on screen");
  const heartRate = page.getByTestId("heart_rate_bpm-readout");
  await expect(heartRate).toHaveText("140 bpm - 155 bpm");
  await page.mouse.move(pace.x + pace.width * 0.25, pace.y + pace.height / 2);
  await expect(heartRate).toHaveText("140 bpm");
  await expect(page.getByTestId("pace_s_per_km-readout")).toHaveText(/^\d:\d\d \/km$/);
  await page.mouse.move(pace.x + pace.width * 0.75, pace.y + pace.height / 2);
  await expect(heartRate).toHaveText("155 bpm");

  await page.getByRole("button", { name: "Exclude from VDOT and critical speed" }).click();
  await expect(page.getByText("Excluded from VDOT and critical speed on the training load page.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "Include in VDOT and critical speed" })).toBeVisible();
});
