import { gpx } from "./gpx";
import { expect, test } from "./server";

test("saving settings shows the API's field errors, then recomputes TRIMP and keeps the values", async ({
  page,
  request,
}) => {
  const imported = await request.post("/api/activities", {
    multipart: {
      files: {
        name: "steady.gpx",
        mimeType: "application/gpx+xml",
        buffer: Buffer.from(
          gpx("Steady", "2026-03-01T07:00:00Z", 1, { heartRate: (point) => (point === 5 ? 172 : 150) }),
        ),
      },
    },
  });
  expect(imported.ok()).toBe(true);

  await page.goto("/settings");
  const maxHeartRate = page.getByLabel("Max heart rate");
  await expect(maxHeartRate).toHaveAccessibleDescription("Highest recorded in your activities: 172 bpm");

  await maxHeartRate.fill("190");
  await page.getByLabel("Resting heart rate").fill("50");
  await page.getByLabel("Zone model").selectOption("hr_reserve_percent");
  await page.getByLabel("Zone 4 starts at").fill("65");
  await page.getByLabel("Body mass").fill("68.5");
  await page.getByLabel("Timezone").fill("Europe/Copenhagen");
  await page.getByRole("button", { name: "Save", exact: true }).click();

  await expect(page.getByRole("alert")).toHaveText("Some values need fixing. Nothing was saved.");
  await expect(page.getByLabel("Zone 4 starts at")).toHaveAccessibleDescription(
    "Each zone must start above the one before it.",
  );

  await page.getByLabel("Zone 4 starts at").fill("80");
  await page.getByRole("button", { name: "Save", exact: true }).click();

  await expect(page.getByRole("status")).toHaveText("Settings saved. TRIMP recomputed for 1 activity.");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByLabel("Zone 2 starts at")).toHaveAccessibleDescription("134 bpm");

  await page.reload();
  await expect(page.getByLabel("Max heart rate")).toHaveValue("190");
  await expect(page.getByLabel("Zone model")).toHaveValue("hr_reserve_percent");
  await expect(page.getByLabel("Zone 4 starts at")).toHaveValue("80");
  await expect(page.getByLabel("Body mass")).toHaveValue("68.5");
  await expect(page.getByLabel("Zone 2 starts at")).toHaveAccessibleDescription("134 bpm");
});
