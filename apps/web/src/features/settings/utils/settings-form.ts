import type { AthleteSettings } from "@/lib/api/model/athlete-settings.gen";
import type { SettingsView } from "@/lib/api/model/settings-view.gen";
import type { TrimpCoefficients } from "@/lib/api/model/trimp-coefficients.gen";
import type { ZoneModel } from "@/lib/api/model/zone-model.gen";

export type SettingsFormValues = {
  max_heart_rate_bpm: string;
  resting_heart_rate_bpm: string;
  trimp_coefficients: TrimpCoefficients;
  zone_model: ZoneModel;
  zone_thresholds_percent: string[];
  body_mass_kg: string;
  timezone: string;
};

export type FieldErrors = Record<string, string>;

export function fieldKey(path: readonly (string | number)[]): string {
  return path.join(".");
}

export function formValues(view: SettingsView): SettingsFormValues {
  const saved = view.settings;
  const chosen = saved ?? view.defaults;
  return {
    max_heart_rate_bpm: saved ? String(saved.max_heart_rate_bpm) : "",
    resting_heart_rate_bpm: saved ? String(saved.resting_heart_rate_bpm) : "",
    trimp_coefficients: chosen.trimp_coefficients,
    zone_model: chosen.zone_model,
    zone_thresholds_percent: chosen.zone_thresholds_percent.map(String),
    body_mass_kg: saved?.body_mass_kg == null ? "" : String(saved.body_mass_kg),
    timezone: chosen.timezone,
  };
}

function number(text: string): number | null {
  const value = Number(text.trim());
  return text.trim() === "" || !Number.isFinite(value) ? null : value;
}

export function parseForm(values: SettingsFormValues): { settings: AthleteSettings } | { errors: FieldErrors } {
  const errors: FieldErrors = {};

  function read(path: (string | number)[], text: string, message: string, whole = false): number {
    const value = number(text);
    if (value === null || (whole && !Number.isInteger(value))) {
      errors[fieldKey(path)] = message;
    }
    return value ?? 0;
  }

  const beats = "Enter a whole number of beats per minute.";
  const settings: AthleteSettings = {
    max_heart_rate_bpm: read(["max_heart_rate_bpm"], values.max_heart_rate_bpm, beats, true),
    resting_heart_rate_bpm: read(["resting_heart_rate_bpm"], values.resting_heart_rate_bpm, beats, true),
    trimp_coefficients: values.trimp_coefficients,
    zone_model: values.zone_model,
    zone_thresholds_percent: values.zone_thresholds_percent.map((text, index) =>
      read(["zone_thresholds_percent", index], text, "Enter a percentage."),
    ),
    body_mass_kg:
      values.body_mass_kg.trim() === ""
        ? null
        : read(["body_mass_kg"], values.body_mass_kg, "Enter a body mass in kilograms."),
    timezone: values.timezone.trim(),
  };
  return Object.keys(errors).length > 0 ? { errors } : { settings };
}

type Refusal = { loc?: unknown; msg?: unknown };

export function refusedFields(body: unknown): FieldErrors | null {
  if (typeof body !== "object" || body === null || !("detail" in body) || !Array.isArray(body.detail)) {
    return null;
  }
  const errors: FieldErrors = {};
  for (const refusal of body.detail as Refusal[]) {
    if (!Array.isArray(refusal.loc) || refusal.loc[0] !== "body" || typeof refusal.msg !== "string") {
      return null;
    }
    errors[fieldKey(refusal.loc.slice(1) as (string | number)[])] = refusal.msg;
  }
  return errors;
}
