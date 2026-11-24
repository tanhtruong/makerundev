import { keepPreviousData, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Page, PageHeading } from "@/components/layouts/page";
import { LoadError } from "@/components/load-error";
import { ActivityTable } from "@/features/activities/components/activity-table";
import { FilterBar } from "@/features/activities/components/filter-bar";
import { ImportForm } from "@/features/activities/components/import-form";
import { Paging } from "@/features/activities/components/paging";
import {
  apiParams,
  DEFAULT_SORT,
  isFiltered,
  type ListSearch,
  withoutFilters,
} from "@/features/activities/utils/list-search";
import { useTimeZone } from "@/hooks/use-time-zone";
import { useListActivities } from "@/lib/api/endpoints/activities/activities.gen";
import type { ActivityPage } from "@/lib/api/model/activity-page.gen";
import { activityCount } from "@/lib/format";

export function ActivityList({ search }: { search: ListSearch }) {
  const timeZone = useTimeZone();
  const params = apiParams(search, timeZone.data ?? "UTC", new Date());
  const query = useListActivities(params, {
    query: { placeholderData: keepPreviousData, enabled: !search.period || timeZone.isSuccess },
  });
  const total = query.data?.total ?? 0;
  const empty = query.isSuccess && total === 0 && !isFiltered(search);

  return (
    <Page>
      <PageHeading aside={total > 0 && <span className="text-muted-foreground">{activityCount(total)}</span>}>
        Activities
      </PageHeading>
      <ImportForm />
      {!empty && <FilterBar search={search} />}
      <ListBody query={query} timeZone={timeZone} search={search} />
    </Page>
  );
}

function ListBody({
  query,
  timeZone,
  search,
}: {
  query: UseQueryResult<ActivityPage, unknown>;
  timeZone: UseQueryResult<string, unknown>;
  search: ListSearch;
}): ReactNode {
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
  if (query.isPending || timeZone.isPending) {
    return <LoadingRows />;
  }
  const { items, total } = query.data;
  const page = search.page ?? 1;
  if (total === 0) {
    return isFiltered(search) ? <NoMatches search={search} /> : <EmptyState />;
  }
  if (items.length === 0) {
    return (
      <p className="border-y border-border py-6">
        There is no page {page}.{" "}
        <Link to="/" search={(previous) => ({ ...previous, page: undefined })} className="underline">
          Go to the first page
        </Link>
        .
      </p>
    );
  }
  return (
    <div aria-busy={query.isPlaceholderData} className="transition-opacity duration-150 aria-busy:opacity-60">
      <ActivityTable activities={items} timeZone={timeZone.data} sort={search.sort ?? DEFAULT_SORT} />
      <Paging page={page} shown={items.length} total={total} loading={query.isPlaceholderData} />
    </div>
  );
}

function NoMatches({ search }: { search: ListSearch }) {
  return (
    <p className="border-y border-border py-6">
      No activities match these filters.{" "}
      <Link to="/" search={withoutFilters(search)} className="underline">
        Clear the filters
      </Link>
      .
    </p>
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
        Export a FIT, GPX or TCX file from your watch and import it above, or sync from{" "}
        <Link to="/strava" className="text-foreground underline">
          Strava
        </Link>{" "}
        or{" "}
        <Link to="/garmin" className="text-foreground underline">
          Garmin Connect
        </Link>
        .
      </p>
    </div>
  );
}
