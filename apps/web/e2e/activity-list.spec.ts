import { gpx } from "./gpx";
import { expect, test } from "./server";

test("imported runs are listed newest first and open their activity page", async ({ page, request }) => {
  for (const [file, name, start, km] of [
    ["harbour.gpx", "Harbour loop", "2026-03-01T07:00:00Z", 2],
    ["tempo.gpx", "Tempo along the canal", "2026-03-03T23:30:00Z", 4],
  ] as const) {
    const response = await request.post("/api/activities", {
      multipart: { files: { name: file, mimeType: "application/gpx+xml", buffer: Buffer.from(gpx(name, start, km)) } },
    });
    expect(response.ok()).toBe(true);
  }
  const origins = new Set<string>();
  page.on("request", (sent) => origins.add(new URL(sent.url()).origin));

  await page.goto("/");

  const rows = page.getByRole("row");
  await expect(rows.nth(1)).toContainText("3 Mar 202623:30Tempo along the canal");
  await expect(rows.nth(2)).toContainText("1 Mar 202607:00Harbour loop");
  await expect(page.getByText("1-2 of 2")).toBeVisible();
  expect([...origins]).toEqual([new URL(page.url()).origin]);

  const lane = await rows.nth(1).getByTestId("lane").boundingBox();
  if (!lane) throw new Error("the lane bar is not on screen");
  await page.mouse.click(lane.x + lane.width / 2, lane.y + lane.height / 2);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Running on 2026-03-03 23:30");
  await page.goBack();

  await page.getByRole("link", { name: "Harbour loop" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Running on 2026-03-01");
});
