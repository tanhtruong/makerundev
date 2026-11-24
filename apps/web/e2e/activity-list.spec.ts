import { gpx } from "./gpx";
import { expect, test } from "./server";

test("runs imported through the form are reported per file, listed newest first and open their activity page", async ({
  page,
}) => {
  const origins = new Set<string>();
  page.on("request", (sent) => origins.add(new URL(sent.url()).origin));
  const tempo = Buffer.from(gpx("Tempo along the canal", "2026-03-03T23:30:00Z", 4));

  await page.goto("/");
  await expect(page.getByText("No activities yet.")).toBeVisible();
  await page.getByLabel("Import activities").setInputFiles([
    {
      name: "harbour.gpx",
      mimeType: "application/gpx+xml",
      buffer: Buffer.from(gpx("Harbour loop", "2026-03-01T07:00:00Z", 2)),
    },
    { name: "tempo.gpx", mimeType: "application/gpx+xml", buffer: tempo },
    { name: "tempo-again.gpx", mimeType: "application/gpx+xml", buffer: tempo },
    { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not an activity") },
  ]);
  await page.getByRole("button", { name: "Import", exact: true }).click();

  const results = page.getByRole("list", { name: "Import results" }).getByRole("listitem");
  await expect(results).toHaveText([
    /^harbour\.gpx\s*Imported$/,
    /^tempo\.gpx\s*Imported$/,
    /^tempo-again\.gpx\s*Already imported$/,
    /^notes\.txt\s*unsupported file: expected FIT, GPX or TCX$/,
  ]);
  const rows = page.getByRole("row");
  await expect(rows.nth(1)).toContainText("3 Mar 202623:30Tempo along the canal");
  await expect(rows.nth(2)).toContainText("1 Mar 202607:00Harbour loop");
  await expect(page.getByRole("navigation", { name: "Pages" }).getByText("1-2 of 2")).toBeVisible();
  expect([...origins]).toEqual([new URL(page.url()).origin]);

  await results.first().getByRole("link", { name: "harbour.gpx" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Running on 2026-03-01");
  await page.goBack();

  const lane = await rows.nth(1).getByTestId("lane").boundingBox();
  if (!lane) throw new Error("the lane bar is not on screen");
  await page.mouse.click(lane.x + lane.width / 2, lane.y + lane.height / 2);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Running on 2026-03-03 23:30");
});
