import type { MapOptions } from "maplibre-gl";

import type { MapSource } from "@/lib/api/model/map-source.gen";
import type { RoutePoint } from "@/lib/api/model/route-point.gen";

export type Style = Exclude<NonNullable<MapOptions["style"]>, string>;
type Layer = Style["layers"][number];
export type RouteColors = { line: string; casing: string; background: string };

const ROUTE = "route";
const BASEMAP = "basemap";
const RASTER_TILE_SIZE = 256;
const RASTER_MAX_ZOOM = 19;

export function styleUrl(source: MapSource, dark: boolean): string {
  return dark && source.dark_url !== null ? source.dark_url : source.url;
}

export function rasterStyle(url: string, colors: RouteColors): Style {
  return {
    version: 8,
    sources: { [BASEMAP]: { type: "raster", tiles: [url], tileSize: RASTER_TILE_SIZE, maxzoom: RASTER_MAX_ZOOM } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": colors.background } },
      { id: BASEMAP, type: "raster", source: BASEMAP },
    ],
  };
}

export function withRoute(style: Style, points: RoutePoint[], colors: RouteColors): Style {
  const coordinates = points.map((point) => [point.longitude_deg, point.latitude_deg]);
  const sources = Object.fromEntries(
    Object.entries(style.sources).map(([id, spec]) => [id, { ...spec, attribution: undefined }]),
  ) as Style["sources"];
  return {
    ...style,
    sources: {
      ...sources,
      [ROUTE]: {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [
            { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates } },
            { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: coordinates[0] ?? [0, 0] } },
          ],
        },
      },
    },
    layers: [...style.layers.filter((layer) => !layer.id.startsWith(`${ROUTE}-`)), ...routeLayers(colors)],
  };
}

function routeLayers(colors: RouteColors): Layer[] {
  const join = { "line-join": "round", "line-cap": "round" } as const;
  return [
    {
      id: `${ROUTE}-casing`,
      type: "line",
      source: ROUTE,
      filter: ["==", ["geometry-type"], "LineString"],
      layout: join,
      paint: { "line-color": colors.casing, "line-width": 6 },
    },
    {
      id: `${ROUTE}-line`,
      type: "line",
      source: ROUTE,
      filter: ["==", ["geometry-type"], "LineString"],
      layout: join,
      paint: { "line-color": colors.line, "line-width": 3 },
    },
    {
      id: `${ROUTE}-start`,
      type: "circle",
      source: ROUTE,
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-radius": 6,
        "circle-color": colors.line,
        "circle-stroke-color": colors.casing,
        "circle-stroke-width": 2,
      },
    },
  ];
}

export function isRouteSource(sourceId: string | undefined): boolean {
  return sourceId === ROUTE;
}
