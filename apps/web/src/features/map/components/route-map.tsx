import { lazy, type ReactNode, Suspense } from "react";

import { MapNote } from "@/features/map/components/map-note";
import { useGetMapSource } from "@/lib/api/endpoints/map/map.gen";
import type { RoutePoint } from "@/lib/api/model/route-point.gen";

const MapCanvas = lazy(() =>
  import("@/features/map/components/map-canvas").then((module) => ({ default: module.MapCanvas })),
);

export function RouteMap({ points, fallback }: { points: RoutePoint[]; fallback: ReactNode }) {
  const query = useGetMapSource({ query: { staleTime: Infinity } });
  const source = query.data?.source ?? null;
  const shape = <div className="grid">{fallback}</div>;

  if (source === null || points.length < 2) {
    return (
      <div data-testid="route-map" data-map={query.isPending ? "pending" : "none"} className="grid">
        {shape}
      </div>
    );
  }
  if (source.file_missing) {
    return (
      <div data-testid="route-map" data-map="file-missing" className="relative grid">
        {shape}
        <MapNote>The tile file {source.file} is not in the data directory.</MapNote>
      </div>
    );
  }
  return (
    <div data-testid="route-map" data-map={source.kind} className="grid">
      <Suspense fallback={shape}>
        <MapCanvas source={source} points={points} fallback={fallback} />
      </Suspense>
    </div>
  );
}
