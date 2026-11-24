import { CartesianGrid, Line, LineChart, ReferenceLine, type TooltipContentProps, XAxis, YAxis } from "recharts";

import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import type { Bounds } from "@/lib/api/model/bounds.gen";
import type { Load } from "@/lib/api/model/load.gen";
import type { LoadDay } from "@/lib/api/model/load-day.gen";
import { calendarDay, signed, wholeNumber } from "@/lib/format";

const Y_AXIS_WIDTH = 40;
const END_LABEL_WIDTH = 64;
const MARGIN = { top: 10, right: END_LABEL_WIDTH, bottom: 10, left: 0 };
const PLOT = "aspect-auto h-56 w-full";
const ACTIVE_DOT = { r: 4, stroke: "var(--background)", strokeWidth: 2 };
const END_LABEL_GAP = 8;
const END_LABEL_SEPARATION = 7;

const LOAD_CONFIG = {
  fitness: { label: "Fitness", color: "var(--series-fitness)" },
  fatigue: { label: "Fatigue", color: "var(--series-fatigue)" },
} satisfies ChartConfig;

const FORM_CONFIG = {
  form: { label: "Form", color: "var(--series-form)" },
} satisfies ChartConfig;

type Series = keyof typeof LOAD_CONFIG;

const TOOLTIP_ROWS: {
  key: Exclude<keyof LoadDay, "date">;
  label: string;
  color?: string;
  format: (value: number) => string;
}[] = [
  { key: "fitness", ...LOAD_CONFIG.fitness, format: wholeNumber },
  { key: "fatigue", ...LOAD_CONFIG.fatigue, format: wholeNumber },
  { key: "form", ...FORM_CONFIG.form, format: signed },
  { key: "trimp", label: "TRIMP", format: wholeNumber },
];

export function LoadCharts({ load }: { load: Load }) {
  const { days, today, bounds } = load;
  const plottedDays = days.length === 1 ? [...days, ...days] : days;
  const labelledAbove: Series = today.fitness >= today.fatigue ? "fitness" : "fatigue";

  return (
    <div className="mt-8 space-y-10">
      <figure>
        <Caption title="Fitness and fatigue" unit="TRIMP per day" />
        <ul aria-label="Legend" className="mb-2 flex gap-4 text-sm text-muted-foreground">
          {Object.entries(LOAD_CONFIG).map(([key, item]) => (
            <li key={key} className="flex items-center gap-1.5">
              <span className="h-0.5 w-4" style={{ background: item.color }} />
              {item.label}
            </li>
          ))}
        </ul>
        <ChartContainer config={LOAD_CONFIG} className={PLOT} role="img" aria-label="Fitness and fatigue by day">
          <LineChart data={plottedDays} margin={MARGIN}>
            <Grid bounds={bounds.fitness_fatigue} format={wholeNumber} />
            <ChartTooltip cursor isAnimationActive={false} content={DayTooltip} />
            {(Object.keys(LOAD_CONFIG) as Series[]).map((series) => (
              <Line
                key={series}
                dataKey={series}
                stroke={`var(--color-${series})`}
                strokeWidth={2}
                dot={false}
                activeDot={ACTIVE_DOT}
                isAnimationActive={false}
                label={(props: EndLabelProps) => (
                  <EndLabel
                    {...props}
                    last={plottedDays.length - 1}
                    text={LOAD_CONFIG[series].label}
                    shift={series === labelledAbove ? -END_LABEL_SEPARATION : END_LABEL_SEPARATION}
                  />
                )}
              />
            ))}
          </LineChart>
        </ChartContainer>
        <DateAxis days={days} />
      </figure>
      <figure>
        <Caption title="Form" unit="fitness minus fatigue" />
        <ChartContainer config={FORM_CONFIG} className={PLOT} role="img" aria-label="Form by day">
          <LineChart data={plottedDays} margin={MARGIN}>
            <Grid bounds={bounds.form} format={signed} />
            <ReferenceLine y={0} stroke="var(--rule)" strokeWidth={1} />
            <ChartTooltip cursor isAnimationActive={false} content={DayTooltip} />
            <Line
              dataKey="form"
              stroke="var(--color-form)"
              strokeWidth={2}
              dot={false}
              activeDot={ACTIVE_DOT}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartContainer>
        <DateAxis days={days} />
      </figure>
    </div>
  );
}

function Caption({ title, unit }: { title: string; unit: string }) {
  return (
    <figcaption className="mb-2 flex items-baseline justify-between gap-4">
      <span className="font-semibold">{title}</span>
      <span className="text-sm text-muted-foreground">{unit}</span>
    </figcaption>
  );
}

function Grid({ bounds, format }: { bounds: Bounds; format: (value: number) => string }) {
  const ticks = bounds.low < 0 ? [bounds.low, 0, bounds.high] : [bounds.low, bounds.high];
  return (
    <>
      <CartesianGrid vertical={false} />
      <XAxis dataKey="date" hide />
      <YAxis
        domain={[bounds.low, bounds.high]}
        ticks={ticks}
        tickFormatter={(value: number) => format(value)}
        tickLine={false}
        axisLine={false}
        width={Y_AXIS_WIDTH}
        allowDataOverflow
      />
    </>
  );
}

function DateAxis({ days }: { days: LoadDay[] }) {
  const first = days[0];
  const last = days[days.length - 1];
  if (!first || !last) {
    return null;
  }
  return (
    <p
      className="flex justify-between text-xs text-muted-foreground"
      style={{ paddingLeft: Y_AXIS_WIDTH, paddingRight: END_LABEL_WIDTH }}
    >
      <span>{calendarDay(first.date)}</span>
      {last !== first && <span>{calendarDay(last.date)}</span>}
    </p>
  );
}

type EndLabelProps = { x?: number | string; y?: number | string; index?: number };

function EndLabel({ x, y, index, last, text, shift }: EndLabelProps & { last: number; text: string; shift: number }) {
  if (index !== last || typeof x !== "number" || typeof y !== "number") {
    return null;
  }
  return (
    <text x={x + END_LABEL_GAP} y={y + shift} dominantBaseline="central" className="fill-muted-foreground text-xs">
      {text}
    </text>
  );
}

function DayTooltip({ active, payload }: TooltipContentProps) {
  const day = payload[0]?.payload as LoadDay | undefined;
  if (!active || !day) {
    return null;
  }
  return (
    <div className="border border-rule bg-background px-3 py-2 text-sm">
      <p className="mb-1 font-semibold">{calendarDay(day.date)}</p>
      <dl className="grid grid-cols-[auto_auto] gap-x-4">
        {TOOLTIP_ROWS.map((row) => (
          <TooltipRow key={row.key} label={row.label} color={row.color} value={row.format(day[row.key])} />
        ))}
      </dl>
    </div>
  );
}

function TooltipRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <>
      <dt className="flex items-center gap-1.5 text-muted-foreground">
        <span className="h-0.5 w-3" style={{ background: color ?? "transparent" }} />
        {label}
      </dt>
      <dd className="text-right font-semi-condensed font-semibold">{value}</dd>
    </>
  );
}
