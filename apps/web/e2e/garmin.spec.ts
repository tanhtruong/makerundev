import { expect, test } from "./server";

const TEST_KEY = "personal-api-key-0123456789";
const ATHLETE_ZONE = "America/Los_Angeles";
const DAY = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: ATHLETE_ZONE,
});
const HOUR = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", hourCycle: "h23", timeZone: ATHLETE_ZONE });

function lastSyncNow(): string {
  const now = new Date();
  return `Last sync ${DAY.format(now)} ${HOUR.format(now)}:`;
}

test.use({ app: "garmin_e2e_server:create" });

test("a saved key syncs from Garmin while the page follows its progress in the athlete's timezone, and removing it keeps the runs", async ({
  page,
  request,
}) => {
  const { defaults } = (await (await request.get("/api/settings")).json()) as { defaults: object };
  const saved = await request.put("/api/settings", {
    data: {
      ...defaults,
      max_heart_rate_bpm: 190,
      resting_heart_rate_bpm: 50,
      body_mass_kg: null,
      timezone: ATHLETE_ZONE,
    },
  });
  expect(saved.ok()).toBe(true);
  const origins = new Set<string>();
  page.on("request", (sent) => origins.add(new URL(sent.url()).origin));
  await page.goto("/garmin");
  await expect(page.getByRole("heading", { name: "Create your Personal API key" })).toBeVisible();

  const key = page.getByLabel("Personal API key");
  await key.fill("a-key-from-another-account");
  await page.getByRole("button", { name: "Save key" }).click();
  await expect(key).toHaveAccessibleDescription(
    "Garmin did not accept that key. Check it was copied whole and has not expired.",
  );

  await key.fill(TEST_KEY);
  await page.getByRole("button", { name: "Save key" }).click();
  await expect(page.getByRole("status")).toHaveText("Key saved. Start a sync to bring your activities in.");
  await expect(page.getByText("Nothing synced yet.")).toBeVisible();

  const sync = page.getByRole("region", { name: "Sync" });
  await sync.getByRole("button", { name: "Sync now" }).click();
  await expect(sync.getByRole("definition").first()).toHaveText("Syncing");
  await expect(sync.getByRole("button", { name: "Sync now" })).toBeDisabled();

  expect((await request.post("/e2e/garmin/release")).ok()).toBe(true);

  const outcome = sync.getByText(/^Up to date\. Last sync /);
  await expect(outcome).toBeVisible();
  await expect.poll(async () => ((await outcome.textContent()) ?? "").includes(lastSyncNow())).toBe(true);
  await expect(sync.getByRole("definition")).toHaveText(["Key saved", "2", "0", "Complete"]);
  await expect(sync.getByRole("button", { name: "Sync now" })).toBeEnabled();
  const skipped = page.getByRole("row").filter({ hasText: "Run 3" });
  await expect(skipped).toContainText("3 Mar 2026Run 3a manual entry, with no file");
  await expect(skipped.getByRole("link", { name: "Run 3" })).toHaveAttribute(
    "href",
    "https://connect.garmin.com/modern/activity/3",
  );
  expect([...origins]).toEqual([new URL(page.url()).origin]);

  await page.locator("summary", { hasText: "Remove key" }).click();
  await page.getByRole("button", { name: "Remove key" }).click();
  await expect(page.getByRole("status")).toHaveText("Key removed. Activities imported from Garmin stay.");
  await expect(page.getByRole("heading", { name: "Create your Personal API key" })).toBeVisible();

  await page.getByRole("link", { name: "Activities" }).click();
  await expect(page.getByRole("row").nth(1)).toContainText("Run 2");
  await expect(page.getByRole("row").nth(2)).toContainText("Run 1");
});
