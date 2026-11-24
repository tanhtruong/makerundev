import { describe, expect, it } from "vitest";

import { parseForm, type SettingsFormValues } from "@/features/settings/utils/settings-form";

const FILLED: SettingsFormValues = {
  max_heart_rate_bpm: " 190 ",
  resting_heart_rate_bpm: "50",
  trimp_coefficients: "female",
  zone_model: "hr_reserve_percent",
  zone_thresholds_percent: ["60", "72.5", "80", "90"],
  body_mass_kg: "",
  timezone: " Europe/Copenhagen ",
};

describe("reading the settings form", () => {
  it("sends every number as typed, out of range or not, with a blank body mass as none", () => {
    expect(
      parseForm({ ...FILLED, resting_heart_rate_bpm: "-5", zone_thresholds_percent: ["60", "72.5", "80", ".9e2"] }),
    ).toEqual({
      settings: {
        max_heart_rate_bpm: 190,
        resting_heart_rate_bpm: -5,
        trimp_coefficients: "female",
        zone_model: "hr_reserve_percent",
        zone_thresholds_percent: [60, 72.5, 80, 90],
        body_mass_kg: null,
        timezone: "Europe/Copenhagen",
      },
    });
  });

  it("names each field that holds no number of the type the API takes", () => {
    expect(
      parseForm({
        ...FILLED,
        max_heart_rate_bpm: "190.5",
        resting_heart_rate_bpm: " ",
        zone_thresholds_percent: ["60", "70", "eighty", "90"],
        body_mass_kg: "heavy",
      }),
    ).toEqual({
      errors: {
        max_heart_rate_bpm: "Enter a whole number of beats per minute.",
        resting_heart_rate_bpm: "Enter a whole number of beats per minute.",
        "zone_thresholds_percent.2": "Enter a percentage.",
        body_mass_kg: "Enter a body mass in kilograms.",
      },
    });
  });
});
