import type { ReactNode } from "react";

import type { ActivityDetail } from "@/lib/api/model/activity-detail.gen";
import { centimetres, decimal, decoupling, distance, duration, pace, perKg, power, wholeNumber } from "@/lib/format";

type Stat = { label: string; value: string; detail?: string | null };

function withPerKg(watts: number | null, wattsPerKg: number | null): Pick<Stat, "value" | "detail"> {
  return { value: power(watts), detail: wattsPerKg === null ? null : perKg(wattsPerKg) };
}

function stats(activity: ActivityDetail): Stat[] {
  const running = activity.is_running;
  const dynamics = activity.running_dynamics;
  const list: (Stat | false)[] = [
    { label: "Distance", value: distance(activity.distance_m) },
    { label: "Moving time", value: duration(activity.moving_s) },
    { label: "Pace", value: pace(activity.pace_s_per_km) },
    running && { label: "Grade-adjusted pace", value: pace(activity.grade_adjusted_pace_s_per_km) },
    activity.avg_power_w !== null && {
      label: "Avg power",
      ...withPerKg(activity.avg_power_w, activity.avg_power_w_per_kg),
    },
    running &&
      activity.body_mass_kg !== null && {
        label: "Estimated power",
        ...withPerKg(activity.estimated_power_w, activity.estimated_power_w_per_kg),
      },
    { label: "Avg heart rate", value: wholeNumber(activity.avg_heart_rate_bpm, "bpm") },
    running && { label: "Aerobic decoupling", value: decoupling(activity.aerobic_decoupling_percent) },
    { label: "Climb", value: wholeNumber(activity.elevation_gain_m, "m") },
    { label: "Elapsed", value: duration(activity.elapsed_s) },
    dynamics.ground_contact_time_ms !== null && {
      label: "Ground contact",
      value: wholeNumber(dynamics.ground_contact_time_ms, "ms"),
    },
    dynamics.vertical_oscillation_mm !== null && {
      label: "Vertical oscillation",
      value: centimetres(dynamics.vertical_oscillation_mm),
    },
    dynamics.step_length_m !== null && {
      label: "Step length",
      value: `${decimal(dynamics.step_length_m, 2)} m`,
    },
    activity.settings_set && { label: "TRIMP", value: wholeNumber(activity.trimp) },
  ];
  return list.filter((stat) => stat !== false);
}

export function SummaryStats({ activity }: { activity: ActivityDetail }) {
  return (
    <dl aria-label="Summary" className="grid grid-cols-2 border-t border-rule sm:grid-cols-3 lg:grid-cols-7">
      {stats(activity).map((stat) => (
        <Tile key={stat.label} label={stat.label}>
          {stat.value}
          {stat.detail && (
            <span className="ml-2 font-sans text-sm font-normal text-muted-foreground">{stat.detail}</span>
          )}
        </Tile>
      ))}
    </dl>
  );
}

function Tile({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="border-b border-border py-3.5 pr-4">
      <dt className="font-semi-condensed text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="mt-1 font-semi-condensed text-2xl font-semibold whitespace-nowrap">{children}</dd>
    </div>
  );
}
