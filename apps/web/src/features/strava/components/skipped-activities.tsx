import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SectionHeading } from "@/features/strava/components/prose";
import type { SkippedActivity } from "@/lib/api/model/skipped-activity.gen";
import { localDay } from "@/lib/format";

export function SkippedActivities({ skipped, timeZone }: { skipped: SkippedActivity[]; timeZone: string }) {
  if (skipped.length === 0) {
    return null;
  }
  return (
    <section className="mt-10">
      <SectionHeading>Skipped activities</SectionHeading>
      <p className="mt-2 text-muted-foreground">These have nothing to chart and are not tried again.</p>
      <Table className="mt-4">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Date</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Why</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {skipped.map((item) => (
            <TableRow key={item.id}>
              <TableCell className="font-semibold">{localDay(item.start_time, timeZone)}</TableCell>
              <TableCell>
                <a href={item.url} rel="noopener noreferrer" className="font-semibold underline">
                  {item.name}
                </a>
              </TableCell>
              <TableCell className="whitespace-normal">{item.reason}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
