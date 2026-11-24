import { cn } from "cn";
import { useState } from "react";
import { Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import type { Bounds } from "@/lib/api/model/bounds.gen";
import type { SeriesBounds } from "@/lib/api/model/series-bounds.gen";
import type { SeriesRow } from "@/lib/api/model/series-row.gen";
import { distance, duration, pace, wholeNumber } from "@/lib/format";

type Metric = keyof SeriesBounds;

const CHARTS: { metric: Metric; title: string; format: (value: number) => string; reversed?: boolean }[] = [
  { metric: "pace_s_per_km", title: "Pace", format: pace, reversed: true },
  { metric: "heart_rate_bpm", title: "Heart rate", format: (value) => wholeNumber(value, "bpm") },
  { metric: "altitude_m", title: "Elevation", format: (value) => wholeNumber(value, "m") },
];

function domain(bounds: Bounds): [number, number] {
  return bounds.high > bounds.low ? [bounds.low, bounds.high] : [bounds.low - 1, bounds.high + 1];
}

export function ActivityCharts({
  series,
  bounds,
  className,
}: {
  series: SeriesRow[];
  bounds: SeriesBounds;
  className?: string | undefined;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const point = hovered === null ? undefined : series[hovered];
  const charts = CHARTS.flatMap((chart) => {
    const metricBounds = bounds[chart.metric];
    return metricBounds ? [{ ...chart, bounds: metricBounds }] : [];
  });
  const last = charts.at(-1)?.metric;

  return (
    <div
      className={cn("flex flex-col gap-5", className)}
      onMouseLeave={() => {
        setHovered(null);
      }}
    >
      <div className="flex items-baseline justify-between font-semi-condensed text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        <span>Over distance</span>
        <span data-testid="hover-position" className="text-sm font-medium tracking-normal normal-case">
          {point ? `${distance(point.distance_m)} · ${duration(point.elapsed_s)}` : ""}
        </span>
      </div>
      {charts.map((chart) => {
        const value = point?.[chart.metric];
        return (
          <figure key={chart.metric}>
            <figcaption className="flex items-baseline justify-between gap-4">
              <span className="font-semibold">{chart.title}</span>
              <span data-testid={`${chart.metric}-readout`} className="font-semi-condensed font-medium">
                {point === undefined ? (
                  <span className="text-muted-foreground">
                    {chart.format(chart.bounds.low)} - {chart.format(chart.bounds.high)}
                  </span>
                ) : value === null || value === undefined ? (
                  "-"
                ) : (
                  chart.format(value)
                )}
              </span>
            </figcaption>
            <ChartContainer
              config={{ [chart.metric]: { label: chart.title, color: "var(--foreground)" } }}
              className="h-32 w-full"
            >
              <LineChart
                data={series}
                margin={{ top: 6, right: 0, bottom: 0, left: 0 }}
                onMouseMove={(state) => {
                  const index = Number(state.activeTooltipIndex);
                  setHovered(Number.isInteger(index) ? index : null);
                }}
                aria-label={`${chart.title} over distance`}
              >
                <XAxis
                  dataKey="distance_m"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  hide={chart.metric !== last}
                  tickFormatter={(metres: number) => distance(metres)}
                  tickLine={false}
                  axisLine={{ stroke: "var(--rule)" }}
                  minTickGap={48}
                />
                <YAxis hide domain={domain(chart.bounds)} reversed={chart.reversed} allowDataOverflow />
                <ChartTooltip content={() => null} cursor={false} isAnimationActive={false} />
                {point && <ReferenceLine x={point.distance_m} stroke="var(--muted-foreground)" ifOverflow="hidden" />}
                <Line
                  dataKey={chart.metric}
                  type="linear"
                  dot={false}
                  activeDot={false}
                  stroke={`var(--color-${chart.metric})`}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              </LineChart>
            </ChartContainer>
          </figure>
        );
      })}
    </div>
  );
}
