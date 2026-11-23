import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { AppProvider } from "@/app/provider";
import { createAppRouter } from "@/app/router";
import type { ActivitySummary } from "@/lib/api/model/activity-summary.gen";
import { server } from "@/testing/server";

function activity(id: number, overrides: Partial<ActivitySummary>): ActivitySummary {
  return {
    id,
    name: null,
    filename: `run-${id}.fit`,
    sport: "running",
    device: null,
    source_format: "fit",
    start_time: "2026-03-01T07:00:00Z",
    distance_m: 5000,
    elapsed_s: 1800,
    moving_s: 1800,
    pace_s_per_km: 360,
    avg_heart_rate_bpm: null,
    max_heart_rate_bpm: null,
    elevation_gain_m: 0,
    trimp: null,
    external_source: null,
    external_id: null,
    ...overrides,
  };
}

function renderAt(path: string) {
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }));
  render(
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>,
  );
}

describe("the activity list", () => {
  it("shows each activity with its lane drawn to scale against the longest", async () => {
    server.use(
      http.get("/api/activities", () =>
        HttpResponse.json({
          items: [
            activity(2, {
              name: "Harbour loop",
              start_time: "2026-03-01T23:30:00Z",
              distance_m: 10000,
              moving_s: 3000.5,
              pace_s_per_km: 300.5,
              avg_heart_rate_bpm: 148.5,
              elevation_gain_m: 25,
            }),
            activity(1, { distance_m: 2500 }),
          ],
          total: 2,
        }),
      ),
    );

    renderAt("/");

    const [, harbour, unnamed] = await screen.findAllByRole("row");
    if (!harbour || !unnamed) throw new Error("expected two activity rows");
    const [date, name, ...cells] = within(harbour).getAllByRole("cell");
    expect(date).toHaveTextContent("2 Mar 2026");
    expect(date).toHaveTextContent("00:30");
    expect(name && within(name).getByRole("link")).toHaveTextContent("Harbour loop");
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "Run",
      "10.00 km",
      "50:00",
      "5:00 /km148 bpm",
      "148",
      "25 m",
    ]);
    expect(within(unnamed).getByRole("link")).toHaveTextContent("run-1.fit");
    expect(within(unnamed).getByRole("link")).toHaveAttribute("href", "/activities/1");
    expect(screen.getAllByTestId("lane").map((lane) => lane.style.width)).toEqual(["100%", "25%"]);
    expect(screen.getByText("2 activities")).toBeInTheDocument();
  });

  it("pages through activities fifty at a time", async () => {
    const offsets: (string | null)[] = [];
    server.use(
      http.get("/api/activities", ({ request }) => {
        const url = new URL(request.url);
        offsets.push(url.searchParams.get("offset"));
        const offset = Number(url.searchParams.get("offset"));
        const count = Math.min(50, 120 - offset);
        return HttpResponse.json({
          items: Array.from({ length: count }, (_, i) => activity(120 - offset - i, {})),
          total: 120,
        });
      }),
    );
    const user = userEvent.setup();

    renderAt("/");
    const pages = await screen.findByRole("navigation", { name: "Pages" });
    expect(within(pages).getByText("1-50 of 120")).toBeInTheDocument();
    expect(within(pages).getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(within(pages).getByRole("link", { name: "Next" }));
    expect(await within(pages).findByText("51-100 of 120")).toBeInTheDocument();
    await user.click(within(pages).getByRole("link", { name: "Next" }));

    expect(await within(pages).findByText("101-120 of 120")).toBeInTheDocument();
    expect(within(pages).getByRole("button", { name: "Next" })).toBeDisabled();
    expect(offsets).toEqual(["0", "50", "100"]);
  });
});
