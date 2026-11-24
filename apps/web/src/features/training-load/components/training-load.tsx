import { keepPreviousData, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Page, PageHeading } from "@/components/layouts/page";
import { Button } from "@/components/ui/button";
import { LoadCharts } from "@/features/training-load/components/load-charts";
import { LoadWeeks } from "@/features/training-load/components/load-weeks";
import { PerformanceSummary } from "@/features/training-load/components/performance-summary";
import { Figure, Figures, SectionHeading } from "@/features/training-load/components/figures";
import { activityCount } from "@/features/training-load/utils/count";
import { apiDays, LOAD_RANGES, type LoadRange, rangeLabel } from "@/features/training-load/utils/ranges";
import { useGetTrainingLoad } from "@/lib/api/endpoints/training-load/training-load.gen";
import type { Load } from "@/lib/api/model/load.gen";
import type { TrainingLoad as TrainingLoadData } from "@/lib/api/model/training-load.gen";
import { signed, wholeNumber } from "@/lib/format";

export function TrainingLoad({ range }: { range: LoadRange }) {
  const query = useGetTrainingLoad({ days: apiDays(range) }, { query: { placeholderData: keepPreviousData } });

  return (
    <Page>
      <PageHeading>Training load</PageHeading>
      <LoadBody query={query} range={range} />
    </Page>
  );
}

function LoadBody({ query, range }: { query: UseQueryResult<TrainingLoadData, unknown>; range: LoadRange }): ReactNode {
  if (query.isPending) {
    return <LoadingBlocks />;
  }
  if (query.isError) {
    return (
      <div role="alert" className="flex items-center gap-4 border-y border-border py-6">
        <span>Training load could not be loaded.</span>
        <Button onClick={() => void query.refetch()}>Try again</Button>
      </div>
    );
  }
  const { settings_set, load, performance } = query.data;

  return (
    <div className="space-y-12">
      {performance && <PerformanceSummary performance={performance} />}
      <section aria-labelledby="load-heading">
        <SectionHeading id="load-heading">Fitness, fatigue and form</SectionHeading>
        <p className="mb-5 max-w-[65ch] text-muted-foreground">
          Fitness and fatigue are 42- and 7-day weighted averages of daily TRIMP. Form is fitness minus fatigue at the
          start of the day.
        </p>
        <LoadSection settingsSet={settings_set} load={load} range={range} loading={query.isPlaceholderData} />
      </section>
    </div>
  );
}

function LoadSection({
  settingsSet,
  load,
  range,
  loading,
}: {
  settingsSet: boolean;
  load: Load | null;
  range: LoadRange;
  loading: boolean;
}) {
  if (!settingsSet) {
    return (
      <p className="border-y border-border py-6">
        Set your max and resting heart rate in{" "}
        <a href="/settings" className="underline">
          Settings
        </a>{" "}
        to see training load.
      </p>
    );
  }
  if (!load) {
    return (
      <p className="border-y border-border py-6">
        No activities yet.{" "}
        <a href="/" className="underline">
          Import some
        </a>{" "}
        to see training load.
      </p>
    );
  }
  return (
    <>
      <RangeNav range={range} />
      <div aria-busy={loading} className="transition-opacity duration-150 aria-busy:opacity-60">
        <Figures columns={4}>
          <Figure label="Fitness" value={wholeNumber(load.today.fitness)} />
          <Figure label="Fatigue" value={wholeNumber(load.today.fatigue)} />
          <Figure label="Form" value={signed(load.today.form)} />
          <Figure label="Activities" value={load.activities} />
        </Figures>
        {load.without_heart_rate > 0 && (
          <p className="mt-3 text-sm text-muted-foreground">
            {activityCount(load.without_heart_rate)} in this range had no heart rate, so{" "}
            {load.without_heart_rate === 1 ? "it counts" : "they count"} as 0.
          </p>
        )}
        <LoadCharts load={load} />
        <LoadWeeks weeks={load.weeks} />
      </div>
    </>
  );
}

function RangeNav({ range }: { range: LoadRange }) {
  return (
    <nav aria-label="Range" className="mb-6 flex flex-wrap gap-x-5 gap-y-1">
      {LOAD_RANGES.map((option) => (
        <Link
          key={option}
          to="/load"
          search={{ days: option }}
          aria-current={option === range ? "page" : undefined}
          className="border-b-2 border-transparent py-1 font-medium whitespace-nowrap text-muted-foreground hover:border-rule/40 hover:text-foreground aria-[current=page]:border-rule aria-[current=page]:text-foreground"
        >
          {rangeLabel(option)}
        </Link>
      ))}
    </nav>
  );
}

function LoadingBlocks() {
  return (
    <div aria-busy="true" aria-label="Loading training load" className="space-y-6">
      <div className="grid grid-cols-2 gap-6 border-y border-border py-4 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, block) => (
          <div key={block} className="space-y-2">
            <div className="h-3 w-16 bg-muted" />
            <div className="h-7 w-12 bg-muted" />
          </div>
        ))}
      </div>
      <div className="h-56 bg-muted" />
      <div className="h-40 bg-muted" />
    </div>
  );
}
