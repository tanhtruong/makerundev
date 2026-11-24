import { Link } from "@tanstack/react-router";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { sportLabel } from "@/features/activities/utils/sport-label";
import type { ActivitySummary } from "@/lib/api/model/activity-summary.gen";
import { distance, duration, localDay, localTime, pace, wholeNumber } from "@/lib/format";

const FROM_MD = "hidden md:table-cell";
const FROM_SM = "hidden sm:table-cell";
const NUMBER = "text-right font-semi-condensed font-medium";
const START_LINE = "relative before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-rule";

export function ActivityTable({ activities, timeZone }: { activities: ActivitySummary[]; timeZone: string }) {
  const longest = Math.max(...activities.map((activity) => activity.distance_m));

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className={FROM_SM}>Date</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className={FROM_MD}>Sport</TableHead>
          <TableHead className="w-[32%] text-right sm:min-w-40">Distance</TableHead>
          <TableHead className={`${FROM_MD} ${NUMBER}`}>Moving</TableHead>
          <TableHead className={NUMBER}>Pace</TableHead>
          <TableHead className={`${FROM_SM} ${NUMBER}`}>Avg HR</TableHead>
          <TableHead className={`${FROM_MD} ${NUMBER}`}>Climb</TableHead>
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
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
