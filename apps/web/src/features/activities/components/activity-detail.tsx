import { Link } from "@tanstack/react-router";
import { useEffect } from "react";

import { Page, PageHeading } from "@/components/layouts/page";
import { Button } from "@/components/ui/button";
import { ActivityCharts } from "@/features/activities/components/activity-charts";
import { ActivityBreakdown } from "@/features/activities/components/activity-breakdown";
import { ExclusionToggle } from "@/features/activities/components/exclusion-toggle";
import { RouteShape } from "@/features/activities/components/route-shape";
import { SummaryStats } from "@/features/activities/components/summary-stats";
import { sportName } from "@/features/activities/utils/sport-label";
import { useTimeZone } from "@/hooks/use-time-zone";
import { ApiError } from "@/lib/api-client";
import { useGetActivity } from "@/lib/api/endpoints/activities/activities.gen";
import type { ActivityDetail as Detail } from "@/lib/api/model/activity-detail.gen";
import { localDay, localTime } from "@/lib/format";

export function ActivityDetail({ activityId }: { activityId: number }) {
  const query = useGetActivity(activityId, {
    query: { retry: (failures, error) => !isMissing(error) && failures < 1 },
  });
  const timeZone = useTimeZone();

  if (query.isPending || timeZone.isPending) {
    return <Loading />;
  }
  if (query.isError || timeZone.isError) {
    const missing = isMissing(query.error);
    return (
      <Page>
        <PageHeading>{missing ? "Activity not found" : "Activity"}</PageHeading>
        <div role="alert" className="flex items-center gap-4 border-y border-border py-6">
          {missing ? (
            <span>
              There is no activity with this id.{" "}
              <Link to="/" className="underline">
                Go to your activities
              </Link>
              .
            </span>
          ) : (
            <>
              <span>The activity could not be loaded.</span>
              <Button
                onClick={() => {
                  void query.refetch();
                  void timeZone.refetch();
                }}
              >
                Try again
              </Button>
            </>
          )}
        </div>
      </Page>
    );
  }
  return <Loaded activity={query.data} timeZone={timeZone.data} />;
}

function isMissing(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

function Loaded({ activity, timeZone }: { activity: Detail; timeZone: string }) {
  const showZoneNotice = activity.zones.length === 0 && !activity.settings_set && activity.avg_heart_rate_bpm !== null;
  const title = `${activity.name ?? activity.filename} - makerundev`;

  useEffect(() => {
    const previous = document.title;
    document.title = title;
    return () => {
      document.title = previous;
    };
  }, [title]);

  return (
    <Page>
      <Link to="/" className="mb-3 inline-block text-sm text-muted-foreground hover:text-foreground hover:underline">
        All activities
      </Link>
      <PageHeading>
        {sportName(activity.sport)} on {localDay(activity.start_time, timeZone)} at{" "}
        {localTime(activity.start_time, timeZone)}
      </PageHeading>
      <Meta activity={activity} />
      <SummaryStats activity={activity} />
      {(activity.route_shape !== null || activity.series.length > 0) && (
        <div className="mt-10 grid gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          {activity.route_shape !== null && <RouteShape shape={activity.route_shape} />}
          {activity.series.length > 0 && (
            <ActivityCharts
              series={activity.series}
              bounds={activity.series_bounds}
              className={activity.route_shape === null ? "lg:col-span-2" : undefined}
            />
          )}
        </div>
      )}
      <ActivityBreakdown activity={activity} />
      {showZoneNotice && (
        <p className="mt-10 max-w-[65ch] text-muted-foreground">
          Set your max and resting heart rate in{" "}
          <a href="/settings" className="text-foreground underline">
            Settings
          </a>{" "}
          to see time in zones and TRIMP.
        </p>
      )}
      {activity.counts_for_performance && (
        <ExclusionToggle activityId={activity.id} excluded={activity.excluded_from_performance} />
      )}
    </Page>
  );
}

function Meta({ activity }: { activity: Detail }) {
  const parts = [
    ...(activity.name && activity.name !== activity.filename ? [activity.name] : []),
    activity.filename,
    ...(activity.device ? [activity.device] : []),
  ];

  return (
    <p className="-mt-3 mb-8 text-muted-foreground">
      {parts.join(" · ")}
      {activity.strava_url !== null && (
        <>
          {" · "}
          <a href={activity.strava_url} rel="noopener" className="text-foreground underline">
            View on Strava
          </a>
        </>
      )}
    </p>
  );
}

function Loading() {
  return (
    <Page>
      <div aria-busy="true" aria-label="Loading the activity">
        <div className="mb-6 h-10 w-96 max-w-full bg-muted" />
        <div className="grid grid-cols-2 border-t border-rule sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }, (_, tile) => (
            <div key={tile} className="border-b border-border py-4 pr-4">
              <div className="h-3 w-20 bg-muted" />
              <div className="mt-3 h-6 w-24 bg-muted" />
            </div>
          ))}
        </div>
        <div className="mt-10 h-72 bg-muted" />
      </div>
    </Page>
  );
}
