import { Figure, Figures, SectionHeading } from "@/features/training-load/components/figures";
import { activityCount } from "@/features/training-load/utils/count";
import type { Performance } from "@/lib/api/model/performance.gen";
import type { PerformanceEffort } from "@/lib/api/model/performance-effort.gen";
import { calendarDay, decimal, distanceName, duration, pace, wholeNumber } from "@/lib/format";

const NO_VDOT = "No run in the last 6 weeks with an effort of 3 minutes to 5 hours.";
const NO_FIT_REASONS = {
  too_few_efforts: "Fewer than two efforts of 2 to 20 minutes in the last 6 weeks.",
  no_fit: "The efforts of 2 to 20 minutes don't fit a critical speed, usually because none was run hard.",
};

function EffortLink({ effort }: { effort: PerformanceEffort }) {
  return (
    <a href={`/activities/${effort.activity_id}`} className="underline">
      {distanceName(effort.distance_m)} in {duration(effort.elapsed_s)}, {effort.activity_name},{" "}
      {calendarDay(effort.date)}
    </a>
  );
}

export function PerformanceSummary({ performance }: { performance: Performance }) {
  const { vdot, vdot_effort, critical_speed, critical_speed_reason, fitted, excluded } = performance;

  return (
    <section aria-labelledby="performance-heading">
      <SectionHeading id="performance-heading">Performance, last 6 weeks</SectionHeading>
      <Figures columns={2}>
        <Figure
          label="VDOT"
          value={vdot === null ? undefined : decimal(vdot, 1)}
          detail={vdot_effort && <EffortLink effort={vdot_effort} />}
          missing={NO_VDOT}
        />
        <Figure
          label="Critical speed"
          value={critical_speed ? pace(critical_speed.pace_s_per_km) : undefined}
          detail={
            critical_speed && (
              <>
                D<span className="font-[system-ui]">′</span> {wholeNumber(critical_speed.d_prime_m, "m")}
              </>
            )
          }
          missing={NO_FIT_REASONS[critical_speed_reason ?? "no_fit"]}
        />
      </Figures>
      {critical_speed && fitted.length > 0 && (
        <div className="mt-4">
          <p className="text-sm text-muted-foreground">Critical speed fitted on</p>
          <ul aria-label="Critical speed fitted on" className="mt-1 space-y-0.5 text-sm">
            {fitted.map((effort) => (
              <li key={`${effort.activity_id}-${effort.distance_m}`}>
                <EffortLink effort={effort} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {excluded > 0 && (
        <p className="mt-3 text-sm text-muted-foreground">
          {activityCount(excluded)} in the last 6 weeks {excluded === 1 ? "is" : "are"} excluded.
        </p>
      )}
    </section>
  );
}
