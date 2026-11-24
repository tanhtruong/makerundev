import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppProvider } from "@/app/provider";
import { createAppRouter } from "@/app/router";
import type { ActivitySummary } from "@/lib/api/model/activity-summary.gen";
import type { SettingsView } from "@/lib/api/model/settings-view.gen";
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

function settingsIn(timezone: string | null) {
  const view: SettingsView = {
    settings:
      timezone === null
        ? null
        : {
            max_heart_rate_bpm: 190,
            resting_heart_rate_bpm: 50,
            trimp_coefficients: "male",
            zone_model: "max_hr_percent",
            zone_thresholds_percent: [60, 70, 80, 90],
            body_mass_kg: null,
            timezone,
          },
    defaults: {
      trimp_coefficients: "male",
      zone_model: "max_hr_percent",
      zone_thresholds_percent: [60, 70, 80, 90],
      timezone: "Europe/Copenhagen",
    },
    zone_starts_bpm: null,
    highest_heart_rate_bpm: null,
    timezones: [],
  };
  return http.get("/api/settings", () => HttpResponse.json(view));
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
  it("shows each activity in the athlete's timezone with its lane drawn to scale against the longest", async () => {
    server.use(
      settingsIn("America/New_York"),
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
    expect(date).toHaveTextContent("1 Mar 2026");
    expect(date).toHaveTextContent("18:30");
    expect(name && within(name).getByRole("link")).toHaveTextContent("Harbour loop");
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "Run",
      "10.00 km",
      "50:00",
      "5:00 /km148 bpm",
      "148",
      "25 m",
      "-",
    ]);
    expect(within(unnamed).getByRole("link")).toHaveTextContent("run-1.fit");
    expect(within(unnamed).getByRole("link")).toHaveAttribute("href", "/activities/1");
    expect(screen.getAllByTestId("lane").map((lane) => lane.style.width)).toEqual(["100%", "25%"]);
    expect(screen.getByText("2 activities")).toBeInTheDocument();
  });

  it("shows times in UTC before the athlete's timezone is saved", async () => {
    server.use(
      settingsIn(null),
      http.get("/api/activities", () =>
        HttpResponse.json({ items: [activity(1, { start_time: "2026-03-01T23:30:00Z" })], total: 1 }),
      ),
    );

    renderAt("/");

    const [, row] = await screen.findAllByRole("row");
    expect(row && within(row).getAllByRole("cell")[0]).toHaveTextContent("1 Mar 202623:30");
  });

  it("pages through activities fifty at a time", async () => {
    const offsets: (string | null)[] = [];
    server.use(
      settingsIn(null),
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

  describe("reads its filters, sort and page from the URL", () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    function recordRequests() {
      const sent: URLSearchParams[] = [];
      server.use(
        http.get("/api/activities", ({ request }) => {
          sent.push(new URL(request.url).searchParams);
          return HttpResponse.json({ items: [activity(1, {})], total: 1 });
        }),
      );
      return sent;
    }

    it("asks the API for that view, with this month counted in the athlete's timezone", async () => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date("2026-03-31T12:00:00Z"));
      server.use(settingsIn("Pacific/Auckland"));
      const sent = recordRequests();

      renderAt(
        "/?q=harbour&sport=running&sport=trail_running&min_km=5&max_km=12.5&sort=-distance_m&page=2&period=this_month",
      );

      await screen.findByText("1 activity");
      expect(sent.map((params) => [...params])).toEqual([
        [
          ["limit", "50"],
          ["offset", "50"],
          ["q", "harbour"],
          ["sport", "running"],
          ["sport", "trail_running"],
          ["min_distance_m", "5000"],
          ["max_distance_m", "12500"],
          ["from", "2026-04-01"],
          ["sort", "-distance_m"],
        ],
      ]);
    });

    it("drops values it cannot use instead of sending them", async () => {
      server.use(settingsIn(null));
      const sent = recordRequests();

      renderAt("/?sport=jogging&sort=name&min_km=-3&max_km=x&from=2026-02-30&to=soon&period=week&page=abc&q=%20");

      await screen.findByText("1 activity");
      expect(sent.map((params) => [...params])).toEqual([
        [
          ["limit", "50"],
          ["offset", "0"],
        ],
      ]);
    });
  });
});
