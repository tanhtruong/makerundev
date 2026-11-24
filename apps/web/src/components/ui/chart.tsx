import { cn } from "cn";
import type * as React from "react";
import { useId } from "react";
import * as RechartsPrimitive from "recharts";

const INITIAL_DIMENSION = { width: 320, height: 200 } as const;

export type ChartConfig = Record<string, { label: string; color: string }>;

export function ChartContainer({
  className,
  children,
  config,
  ...props
}: React.ComponentProps<"div"> & {
  config: ChartConfig;
  children: React.ComponentProps<typeof RechartsPrimitive.ResponsiveContainer>["children"];
}) {
  const chartId = `chart-${useId().replace(/:/g, "")}`;

  return (
    <div
      data-slot="chart"
      data-chart={chartId}
      className={cn(
        "flex justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line[stroke='#ccc']]:stroke-border [&_.recharts-curve.recharts-tooltip-cursor]:stroke-rule [&_.recharts-layer]:outline-hidden [&_.recharts-reference-line_[stroke='#ccc']]:stroke-border [&_.recharts-surface]:outline-hidden",
        className,
      )}
      {...props}
    >
      <ChartStyle id={chartId} config={config} />
      <RechartsPrimitive.ResponsiveContainer initialDimension={INITIAL_DIMENSION}>
        {children}
      </RechartsPrimitive.ResponsiveContainer>
    </div>
  );
}

function ChartStyle({ id, config }: { id: string; config: ChartConfig }) {
  const colors = Object.entries(config).map(([key, item]) => `--color-${key}: ${item.color};`);
  return <style>{`[data-chart=${id}] { ${colors.join(" ")} }`}</style>;
}

export const ChartTooltip = RechartsPrimitive.Tooltip;
