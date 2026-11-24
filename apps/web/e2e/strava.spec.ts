import { expect, test } from "./server";

test.use({
  app: "strava_e2e_server:create",
  serverEnv: { MAKERUNDEV_STRAVA_CLIENT_ID: "4242", MAKERUNDEV_STRAVA_CLIENT_SECRET: "application-secret" },
});

test("connecting Strava imports its activities while the page follows the sync, and disconnecting deletes them", async ({
  page,
  request,
}) => {
  await page.route(
    (url) => url.hostname.endsWith("strava.com"),
    (route) => route.abort(),
  );
  await page.route("**/strava/connect", async (route) => {
    const sent = await route.fetch({ maxRedirects: 0 });
    const authorize = new URL(sent.headers().location ?? "");
    expect(`${authorize.origin}${authorize.pathname}`).toBe("https://www.strava.com/oauth/authorize");
    const callback = new URL(authorize.searchParams.get("redirect_uri") ?? "");
    callback.search = new URLSearchParams({
      code: "good",
      scope: "read,activity:read_all",
      state: authorize.searchParams.get("state") ?? "",
    }).toString();
    await route.fulfill({ status: 302, headers: { location: callback.toString() } });
  });

  const settings = await request.put("/api/settings", {
    data: {
      max_heart_rate_bpm: 190,
      resting_heart_rate_bpm: 50,
      trimp_coefficients: "male",
      zone_model: "max_hr_percent",
      zone_thresholds_percent: [60, 70, 80, 90],
      body_mass_kg: null,
      timezone: "Pacific/Pago_Pago",
    },
  });
  expect(settings.ok()).toBe(true);

  await page.goto("/strava");
  await page.getByRole("button", { name: "Connect with Strava" }).click();

  await expect(page).toHaveURL(/\/strava\?notice=connected$/);
  await expect(page.getByRole("status")).toHaveText("Connected to Strava. Start a sync to bring your activities in.");
  const origins = new Set<string>();
  page.on("request", (sent) => origins.add(new URL(sent.url()).origin));

  const sync = page.getByRole("region", { name: "Sync" });
  await expect(sync.getByText("Nothing synced yet.")).toBeVisible();
  await sync.getByRole("button", { name: "Sync now" }).click();
  await expect(sync.getByRole("definition").first()).toHaveText("Syncing");
  await expect(sync.getByRole("button", { name: "Sync now" })).toBeDisabled();
  await expect(page).toHaveURL(/\/strava$/);

  expect((await request.post("/e2e/strava/release")).ok()).toBe(true);

  await expect(sync.getByText(/^Up to date\. Last sync /)).toBeVisible();
  await expect(sync.getByRole("definition")).toHaveText(["Connected", "1", "0", "Complete"]);
  await expect(sync.getByRole("button", { name: "Sync now" })).toBeEnabled();
  const skipped = page.getByRole("row").filter({ hasText: "Run 2" });
  await expect(skipped).toContainText("1 Mar 2026Run 2a manual entry, with no streams");
  await expect(skipped.getByRole("link", { name: "Run 2" })).toHaveAttribute(
    "href",
    "https://www.strava.com/activities/2",
  );
  expect([...origins]).toEqual([new URL(page.url()).origin]);

  await page.locator("summary", { hasText: "Disconnect" }).click();
  await page.getByRole("button", { name: "Disconnect and delete synced activities" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "Disconnected from Strava. 1 activity that came only from Strava was deleted.",
  );
  await expect(page.getByRole("button", { name: "Connect with Strava" })).toBeVisible();

  await page.getByRole("link", { name: "Activities" }).click();
  await expect(page.getByText("No activities yet.")).toBeVisible();
});
