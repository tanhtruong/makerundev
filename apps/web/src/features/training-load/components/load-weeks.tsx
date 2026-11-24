import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SectionHeading } from "@/features/training-load/components/figures";
import type { LoadWeek } from "@/lib/api/model/load-week.gen";
import { calendarDay, signed, wholeNumber } from "@/lib/format";

const NUMBER = "text-right font-semi-condensed font-medium";

export function LoadWeeks({ weeks }: { weeks: LoadWeek[] }) {
  return (
    <section aria-labelledby="weeks-heading" className="mt-12 max-w-3xl">
      <SectionHeading id="weeks-heading">By week</SectionHeading>
      <Table aria-labelledby="weeks-heading">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Week ending</TableHead>
            <TableHead className={NUMBER}>TRIMP</TableHead>
            <TableHead className={NUMBER}>Fitness</TableHead>
            <TableHead className={NUMBER}>Fatigue</TableHead>
            <TableHead className={NUMBER}>Form</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {weeks.map((week) => (
            <TableRow key={week.week_ending}>
              <TableCell>{calendarDay(week.week_ending)}</TableCell>
              <TableCell className={NUMBER}>{wholeNumber(week.trimp)}</TableCell>
              <TableCell className={NUMBER}>{wholeNumber(week.fitness)}</TableCell>
              <TableCell className={NUMBER}>{wholeNumber(week.fatigue)}</TableCell>
              <TableCell className={NUMBER}>{signed(week.form)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
