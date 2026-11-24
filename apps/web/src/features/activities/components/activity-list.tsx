import { keepPreviousData, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Page, PageHeading } from "@/components/layouts/page";
import { LoadError } from "@/components/load-error";
import { Button } from "@/components/ui/button";
import { ActivityTable } from "@/features/activities/components/activity-table";
import { useTimeZone } from "@/hooks/use-time-zone";
import { useListActivities } from "@/lib/api/endpoints/activities/activities.gen";
import type { ActivityPage } from "@/lib/api/model/activity-page.gen";

const PAGE_SIZE = 50;

function activityCount(total: number): string {
  return `${total} ${total === 1 ? "activity" : "activities"}`;
}

export function ActivityList({ page }: { page: number }) {
  const offset = (page - 1) * PAGE_SIZE;
  const query = useListActivities({ limit: PAGE_SIZE, offset }, { query: { placeholderData: keepPreviousData } });
  const timeZone = useTimeZone();
  const total = query.data?.total ?? 0;

  return (
    <Page>
      <PageHeading aside={total > 0 && <span className="text-muted-foreground">{activityCount(total)}</span>}>
        Activities
      </PageHeading>
      <ListBody query={query} timeZone={timeZone} page={page} />
    </Page>
  );
}

function ListBody({
  query,
  timeZone,
  page,
}: {
  query: UseQueryResult<ActivityPage, unknown>;
  timeZone: UseQueryResult<string, unknown>;
  page: number;
}): ReactNode {
  if (query.isPending || timeZone.isPending) {
    return <LoadingRows />;
  }
  if (query.isError || timeZone.isError) {
    return (
      <LoadError
        onRetry={() => {
          void query.refetch();
          void timeZone.refetch();
        }}
      >
        The activity list could not be loaded.
      </LoadError>
    );
  }
  const { items, total } = query.data;
  if (total === 0) {
    return <EmptyState />;
  }
  if (items.length === 0) {
    return (
      <p className="border-y border-border py-6">
        There is no page {page}.{" "}
        <Link to="/" search={{ page: 1 }} className="underline">
          Go to the newest activities
        </Link>
        .
      </p>
    );
  }
  return (
    <div aria-busy={query.isPlaceholderData} className="transition-opacity duration-150 aria-busy:opacity-60">
      <ActivityTable activities={items} timeZone={timeZone.data} />
      <Paging page={page} shown={items.length} total={total} loading={query.isPlaceholderData} />
    </div>
  );
}

function Paging({ page, shown, total, loading }: { page: number; shown: number; total: number; loading: boolean }) {
  const offset = (page - 1) * PAGE_SIZE;

  return (
    <nav aria-label="Pages" className="mt-5 flex items-center justify-between gap-4">
      <span className="text-muted-foreground">
        {loading ? `Loading page ${page}` : `${offset + 1}-${offset + shown} of ${total}`}
      </span>
      <div className="flex gap-2">
        <PageLink page={page - 1} enabled={page > 1 && !loading}>
          Previous
        </PageLink>
        <PageLink page={page + 1} enabled={offset + shown < total && !loading}>
          Next
        </PageLink>
      </div>
    </nav>
  );
}

function PageLink({ page, enabled, children }: { page: number; enabled: boolean; children: ReactNode }) {
  if (!enabled) {
    return <Button disabled>{children}</Button>;
  }
  return (
    <Button asChild>
      <Link to="/" search={{ page }}>
        {children}
      </Link>
    </Button>
  );
}

function LoadingRows() {
  return (
    <div aria-busy="true" aria-label="Loading activities" className="border-t border-rule">
      {Array.from({ length: 8 }, (_, row) => (
        <div key={row} className="flex items-center gap-6 border-b border-border py-3.5">
          <div className="h-3 w-28 bg-muted" />
          <div className="h-3 w-48 bg-muted" />
          <div className="h-2 flex-1 bg-muted" />
          <div className="h-3 w-16 bg-muted" />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="border-y border-border py-10">
      <p className="font-semibold">No activities yet.</p>
      <p className="mt-2 max-w-[65ch] text-muted-foreground">
        Export a FIT, GPX or TCX file from your watch and{" "}
        <a href="/import" className="text-foreground underline">
          import it
        </a>
        , or sync from{" "}
        <a href="/strava" className="text-foreground underline">
          Strava
        </a>{" "}
        or{" "}
        <Link to="/garmin" className="text-foreground underline">
          Garmin Connect
        </Link>
        .
      </p>
    </div>
  );
}
