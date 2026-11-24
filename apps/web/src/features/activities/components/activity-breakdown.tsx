import type { ReactNode } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ActivityDetail } from "@/lib/api/model/activity-detail.gen";
import type { Zone } from "@/lib/api/model/zone.gen";
import { distance, distanceName, duration, pace, percent, zoneRange } from "@/lib/format";

const NUMBER = "text-right font-semi-condensed font-medium";

export function ActivityBreakdown({ activity }: { activity: ActivityDetail }) {
  const { splits, laps, zones, best_efforts: efforts } = activity;
  if (splits.length === 0 && laps.length === 0 && zones.length === 0 && efforts.length === 0) {
    return null;
  }

  return (
    <div className="mt-10 flex flex-wrap items-start gap-10">
      {splits.length > 0 && (
        <Section title="Splits">
          <Table>
            <TableHeader>
              <HeaderRow labels={["Split", "Distance", "Time", "Pace"]} />
            </TableHeader>
            <TableBody>
              {splits.map((split, index) => (
                <TableRow key={index}>
                  <TableCell className={NUMBER}>{index + 1}</TableCell>
                  <TableCell className={NUMBER}>{distance(split.distance_m)}</TableCell>
                  <TableCell className={NUMBER}>{duration(split.moving_s)}</TableCell>
                  <TableCell className={NUMBER}>{pace(split.pace_s_per_km)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}
      {laps.length > 0 && (
        <Section title="Laps">
          <Table>
            <TableHeader>
              <HeaderRow labels={["Lap", "Time", "Distance", "Pace"]} />
            </TableHeader>
            <TableBody>
              {laps.map((lap) => (
                <TableRow key={lap.number}>
                  <TableCell className={NUMBER}>{lap.number}</TableCell>
                  <TableCell className={NUMBER}>{lap.elapsed_s === null ? "-" : duration(lap.elapsed_s)}</TableCell>
                  <TableCell className={NUMBER}>{lap.distance_m === null ? "-" : distance(lap.distance_m)}</TableCell>
                  <TableCell className={NUMBER}>{pace(lap.pace_s_per_km)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}
      {zones.length > 0 && <Zones zones={zones} />}
      {efforts.length > 0 && (
        <Section title="Best efforts">
          <Table>
            <TableHeader>
              <HeaderRow labels={["Distance", "Time"]} first="left" />
            </TableHeader>
            <TableBody>
              {efforts.map((effort) => (
                <TableRow key={effort.distance_m}>
                  <TableCell>{distanceName(effort.distance_m)}</TableCell>
                  <TableCell className={NUMBER}>{duration(effort.elapsed_s)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}
    </div>
  );
}

function Zones({ zones }: { zones: Zone[] }) {
  return (
    <Section title="Time in zones" wide>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Zone</TableHead>
            <TableHead className="w-full">
              <span className="sr-only">Share</span>
            </TableHead>
            <TableHead className="text-right">Time</TableHead>
            <TableHead className="text-right">Share</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {zones.map((zone) => (
            <TableRow key={zone.name}>
              <TableCell>
                <div className="font-medium">{zone.name}</div>
                <div className="text-sm text-muted-foreground">{zoneRange(zone.low_bpm, zone.high_bpm)}</div>
              </TableCell>
              <TableCell aria-hidden>
                {zone.share > 0 && (
                  <div data-testid="zone-bar" className="h-2 bg-foreground" style={{ width: `${zone.share * 100}%` }} />
                )}
              </TableCell>
              <TableCell className={NUMBER}>{duration(zone.elapsed_s)}</TableCell>
              <TableCell className={NUMBER}>{percent(zone.share)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  );
}

function HeaderRow({ labels, first = "right" }: { labels: string[]; first?: "left" | "right" }) {
  return (
    <TableRow className="hover:bg-transparent">
      {labels.map((label, index) => (
        <TableHead key={label} className={index === 0 && first === "left" ? undefined : "text-right"}>
          {label}
        </TableHead>
      ))}
    </TableRow>
  );
}

function Section({ title, wide = false, children }: { title: string; wide?: boolean; children: ReactNode }) {
  return (
    <section aria-label={title} className={wide ? "min-w-0 flex-[2_1_24rem]" : "max-w-md min-w-0 flex-[1_1_17rem]"}>
      <h2 className="mb-2 font-condensed text-2xl leading-tight font-bold">{title}</h2>
      {children}
    </section>
  );
}
