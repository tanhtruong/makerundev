import { gpx } from "./gpx";
import { expect, test } from "./server";

function day(index: number): string {
  return new Date(Date.UTC(2026, 0, 1 + index, 7)).toISOString().replace(".000", "");
}

test("a search, a sort and a page survive together in the URL and reopen as the same view", async ({ page }) => {
  const runs = [
    ...Array.from({ length: 52 }, (_, i) => ({ name: `Harbour ${i + 1}`, km: 1 + (i % 4) })),
    { name: "Harbour long run", km: 12 },
    ...Array.from({ length: 3 }, (_, i) => ({ name: `Canal ${i + 1}`, km: 15 })),
  ];
  await page.goto("/");
  await page.getByLabel("Import activities").setInputFiles(
    runs.map((run, i) => ({
      name: `run-${i}.gpx`,
      mimeType: "application/gpx+xml",
      buffer: Buffer.from(gpx(run.name, day(i), run.km)),
    })),
  );
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await expect(page.getByText("56 activities")).toBeVisible();

  await page.getByLabel("Search").fill("harbour");
  await expect(page.getByText("53 activities")).toBeVisible();
  await expect(page).toHaveURL(/\?q=harbour$/);

  await page.getByRole("columnheader", { name: "Distance" }).getByRole("link").click();
  const rows = page.getByRole("row");
  await expect(rows.nth(1)).toContainText("Harbour long run");
  await expect(page.getByRole("columnheader", { name: "Distance" })).toHaveAttribute("aria-sort", "descending");

  const pages = page.getByRole("navigation", { name: "Pages" });
  await pages.getByRole("link", { name: "Page 2" }).click();
  await expect(pages.getByText("51-53 of 53")).toBeVisible();
  await expect(page).toHaveURL(/\?q=harbour&sort=-distance_m&page=2$/);

  await page.reload();
  await expect(pages.getByText("51-53 of 53")).toBeVisible();
  await expect(page.getByLabel("Search")).toHaveValue("harbour");
  await expect(rows.filter({ hasText: "Canal" })).toHaveCount(0);

  await page.getByRole("button", { name: "Clear" }).click();
  await expect(page.getByText("56 activities")).toBeVisible();
  await expect(rows.nth(1)).toContainText("Canal");
  await expect(page).toHaveURL(/\?sort=-distance_m$/);
});
