import { gpx } from "./gpx";
import { expect, test } from "./server";

const TILE_HOST = "https://tiles.e2e.test";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGO48eQCAAUkAo1S2BuqAAAAAElFTkSuQmCC",
  "base64",
);

async function importRun(request: import("@playwright/test").APIRequestContext): Promise<number> {
  const imported = await request.post("/api/activities", {
    multipart: {
      files: {
        name: "harbour.gpx",
        mimeType: "application/gpx+xml",
        buffer: Buffer.from(gpx("Harbour loop", "2026-03-01T07:00:00Z", 2)),
      },
    },
  });
  const { results } = (await imported.json()) as { results: { activity_id: number }[] };
  const id = results[0]?.activity_id;
  if (id === undefined) throw new Error("the run was not imported");
  return id;
}

test("a custom raster source saved in settings draws the route on a map from that host", async ({ page, request }) => {
  const tiles: string[] = [];
  await page.route(`${TILE_HOST}/**`, async (route) => {
    tiles.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: PNG,
    });
  });
  const activityId = await importRun(request);

  await page.goto("/settings");
  const map = page.getByRole("group", { name: "Map" });
  await map.getByRole("radio", { name: "Custom raster tiles" }).check();
  await map.getByLabel("Tile URL").fill(`${TILE_HOST}/{z}/{x}/{y}.png`);
  await map.getByLabel("Attribution").fill("© E2E Tiles & Co");
  await map.getByRole("button", { name: "Save map" }).click();
  await expect(map.getByRole("status")).toHaveText("Map source saved.");

  tiles.length = 0;
  await page.goto(`/activities/${activityId}`);

  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expect(page.getByText("© E2E Tiles & Co")).toBeVisible();
  await expect.poll(() => tiles.some((url) => /^https:\/\/tiles\.e2e\.test\/\d+\/\d+\/\d+\.png$/.test(url))).toBe(true);
});

test("with no map source the activity page shows the route shape and asks no other host", async ({
  page,
  request,
  baseURL,
}) => {
  const activityId = await importRun(request);
  const elsewhere: string[] = [];
  page.on("request", (sent) => {
    if (new URL(sent.url()).origin !== baseURL) elsewhere.push(sent.url());
  });

  await page.goto(`/activities/${activityId}`);

  await expect(page.getByTestId("route-map")).toHaveAttribute("data-map", "none");
  await expect(page.getByRole("img", { name: "Route shape, north up" })).toBeVisible();
  expect(elsewhere).toEqual([]);
});
