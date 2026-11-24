import type { RouteShape as Shape } from "@/lib/api/model/route-shape.gen";

const INSET = 24;

export function RouteShape({ shape }: { shape: Shape }) {
  const points = shape.points.map(({ x, y }) => `${(x + INSET).toFixed(1)},${(y + INSET).toFixed(1)}`).join(" ");
  const [start] = shape.points;

  return (
    <figure className="flex flex-col">
      <figcaption className="mb-2 font-semi-condensed text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        Route
      </figcaption>
      <div className="flex aspect-square max-h-[28rem] items-center justify-center border-y border-border p-4 lg:aspect-auto lg:flex-1">
        <svg
          viewBox={`0 0 ${(shape.width + 2 * INSET).toFixed(1)} ${(shape.height + 2 * INSET).toFixed(1)}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Route shape, north up"
          className="size-full max-h-96"
        >
          <polyline
            points={points}
            fill="none"
            stroke="var(--foreground)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
          {start && <circle cx={start.x + INSET} cy={start.y + INSET} r={14} fill="var(--foreground)" />}
        </svg>
      </div>
    </figure>
  );
}
