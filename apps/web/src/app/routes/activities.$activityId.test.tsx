import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { AppProvider } from "@/app/provider";
import { createAppRouter } from "@/app/router";
import type { ActivityDetail } from "@/lib/api/model/activity-detail.gen";
import type { SettingsView } from "@/lib/api/model/settings-view.gen";
import { server } from "@/testing/server";

function detail(overrides: Partial<ActivityDetail>): ActivityDetail {
  return {
    id: 7,
    name: null,
    filename: "ride.fit",
    sport: "cycling",
    device: null,
    source_format: "fit",
    start_time: "2026-03-01T07:00:00Z",
    distance_m: 20000,
    elapsed_s: 3600,
    moving_s: 3600,
    pace_s_per_km: 180,
    avg_heart_rate_bpm: 140,
    max_heart_rate_bpm: 160,
    elevation_gain_m: 100,
    trimp: 50,
    external_source: null,
    external_id: null,
    strava_url: null,
    is_running: false,
    settings_set: true,
    body_mass_kg: 70,
    counts_for_performance: false,
    excluded_from_performance: false,
    grade_adjusted_pace_s_per_km: 175,
    aerobic_decoupling_percent: 3.2,
    avg_power_w: 210,
    avg_power_w_per_kg: 3,
    estimated_power_w: 190,
    estimated_power_w_per_kg: 2.71,
    running_dynamics: { ground_contact_time_ms: null, vertical_oscillation_mm: null, step_length_m: null },
    splits: [],
    laps: [],
    best_efforts: [],
    zones: [],
    series: [],
    series_bounds: { pace_s_per_km: null, heart_rate_bpm: null, altitude_m: null },
    route: null,
    route_shape: null,
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
            body_mass_kg: 70,
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

function renderActivity(activity: ActivityDetail, timezone: string | null) {
  server.use(
    http.get("/api/activities/7", () => HttpResponse.json(activity)),
    settingsIn(timezone),
  );
  const router = createAppRouter(createMemoryHistory({ initialEntries: ["/activities/7"] }));
  render(
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>,
  );
}

describe("the activity page", () => {
  it.each([
    ["America/New_York", "Cycling on 1 Mar 2026 at 02:00"],
    [null, "Cycling on 1 Mar 2026 at 07:00"],
  ])("shows the start in the athlete's timezone (%s), not the browser's", async (timezone, heading) => {
    renderActivity(detail({}), timezone);

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(heading);
  });

  it.each([
    [
      "a ride leaves out the running-only figures",
      detail({}),
      ["Distance", "Moving time", "Pace", "Avg power", "Avg heart rate", "Climb", "Elapsed", "TRIMP"],
    ],
    [
      "a run shows grade-adjusted pace, estimated power and decoupling",
      detail({ sport: "running", is_running: true }),
      [
        "Distance",
        "Moving time",
        "Pace",
        "Grade-adjusted pace",
        "Avg power",
        "Estimated power",
        "Avg heart rate",
        "Aerobic decoupling",
        "Climb",
        "Elapsed",
        "TRIMP",
      ],
    ],
  ])("%s", async (_, activity, terms) => {
    renderActivity(activity, "Europe/Copenhagen");

    const summary = await screen.findByLabelText("Summary");

    expect(
      within(summary)
        .getAllByRole("term")
        .map((term) => term.textContent),
    ).toEqual(terms);
  });
});
