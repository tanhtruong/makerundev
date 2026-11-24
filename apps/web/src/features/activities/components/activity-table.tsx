import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DEFAULT_SORT } from "@/features/activities/utils/list-search";
import { nextSort, type SortKey, sortParts } from "@/features/activities/utils/sorting";
import { sportLabel } from "@/features/activities/utils/sport-label";
import type { ListActivitiesSort } from "@/lib/api/model/list-activities-sort.gen";
import type { ActivitySummary } from "@/lib/api/model/activity-summary.gen";
import { distance, duration, localDay, localTime, pace, wholeNumber } from "@/lib/format";

const FROM_MD = "hidden md:table-cell";
const FROM_SM = "hidden sm:table-cell";
const NUMBER = "text-right font-semi-condensed font-medium";
const START_LINE = "relative before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-rule";

export function ActivityTable({
  activities,
  timeZone,
  sort,
}: {
  activities: ActivitySummary[];
  timeZone: string;
  sort: ListActivitiesSort;
}) {
  const header = (key: SortKey, className: string, children: ReactNode) => (
    <SortHeader sortKey={key} current={sort} className={className}>
      {children}
    </SortHeader>
  );
  const longest = Math.max(...activities.map((activity) => activity.distance_m));

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          {header("start_time", FROM_SM, "Date")}
          <TableHead>Name</TableHead>
          <TableHead className={FROM_MD}>Sport</TableHead>
          {header("distance_m", "w-[32%] text-right sm:min-w-40", "Distance")}
          {header("moving_s", `${FROM_MD} ${NUMBER}`, "Moving")}
          {header("pace_s_per_km", NUMBER, "Pace")}
          {header("avg_heart_rate_bpm", `${FROM_SM} ${NUMBER}`, "Avg HR")}
          {header("elevation_gain_m", `${FROM_MD} ${NUMBER}`, "Climb")}
          {header("trimp", `${FROM_MD} ${NUMBER}`, "TRIMP")}
        </TableRow>
      </TableHeader>
      <TableBody>
        {activities.map((activity) => (
          <TableRow key={activity.id}>
            <TableCell className={FROM_SM}>
              <span className="font-semibold">{localDay(activity.start_time, timeZone)}</span>
              <span className="ml-2 text-muted-foreground">{localTime(activity.start_time, timeZone)}</span>
            </TableCell>
            <TableCell className="max-w-44 whitespace-normal sm:max-w-72 sm:truncate sm:whitespace-nowrap">
              <Link
                to="/activities/$activityId"
                params={{ activityId: activity.id }}
                className="line-clamp-2 after:absolute after:inset-0 after:z-10 hover:underline sm:line-clamp-none"
              >
                {activity.name ?? activity.filename}
              </Link>
              <div className="text-sm text-muted-foreground sm:hidden">
                {localDay(activity.start_time, timeZone)} {localTime(activity.start_time, timeZone)}
              </div>
            </TableCell>
            <TableCell className={FROM_MD}>{sportLabel(activity.sport)}</TableCell>
            <TableCell className={START_LINE}>
              <div className="flex flex-col-reverse gap-1.5 sm:flex-row sm:items-center sm:gap-3">
                <div className="h-2 w-full sm:min-w-6 sm:flex-1" aria-hidden>
                  <div
                    data-testid="lane"
                    className="h-full bg-lane"
                    style={{ width: `${longest > 0 ? (activity.distance_m / longest) * 100 : 0}%` }}
                  />
                </div>
                <span className={`${NUMBER} sm:w-20`}>{distance(activity.distance_m)}</span>
              </div>
            </TableCell>
            <TableCell className={`${FROM_MD} ${NUMBER}`}>{duration(activity.moving_s)}</TableCell>
            <TableCell className={NUMBER}>
              {pace(activity.pace_s_per_km)}
              {activity.avg_heart_rate_bpm !== null && (
                <div className="text-sm font-normal text-muted-foreground sm:hidden">
                  {wholeNumber(activity.avg_heart_rate_bpm, "bpm")}
                </div>
              )}
            </TableCell>
            <TableCell className={`${FROM_SM} ${NUMBER}`}>{wholeNumber(activity.avg_heart_rate_bpm)}</TableCell>
            <TableCell className={`${FROM_MD} ${NUMBER}`}>{wholeNumber(activity.elevation_gain_m, "m")}</TableCell>
            <TableCell className={`${FROM_MD} ${NUMBER}`}>{wholeNumber(activity.trimp)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function SortHeader({
  sortKey,
  current,
  className,
  children,
}: {
  sortKey: SortKey;
  current: ListActivitiesSort;
  className: string;
  children: ReactNode;
}) {
  const { key, direction } = sortParts(current);
  const sorted = key === sortKey;
  const next = nextSort(current, sortKey);
  const arrow = (
    <span aria-hidden className={`inline-block w-3 text-center ${sorted ? "" : "invisible"}`}>
      {direction === "asc" ? "↑" : "↓"}
    </span>
  );
  const right = className.includes("text-right");

  return (
    <TableHead
      aria-sort={sorted ? (direction === "asc" ? "ascending" : "descending") : undefined}
      className={className}
    >
      <Link
        to="/"
        search={(previous) => ({ ...previous, sort: next === DEFAULT_SORT ? undefined : next, page: undefined })}
        className={`inline-flex items-center gap-1 hover:text-foreground hover:underline ${sorted ? "text-foreground" : ""}`}
      >
        {right && arrow}
        {children}
        {!right && arrow}
      </Link>
    </TableHead>
  );
}
