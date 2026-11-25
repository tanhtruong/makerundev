import { layers, namedFlavor } from "@protomaps/basemaps";
import { addProtocol } from "maplibre-gl";
import { Protocol } from "pmtiles";

import type { Style } from "@/features/map/utils/map-style";

const FONT = "Noto Sans Regular";
const SOURCE = "protomaps";

let registered = false;

function register() {
  if (registered) return;
  addProtocol("pmtiles", new Protocol().tile);
  registered = true;
}

function oneFont(value: unknown): unknown {
  if (typeof value === "string") return value.startsWith("Noto Sans") ? FONT : value;
  if (Array.isArray(value)) return value.map(oneFont);
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, oneFont(entry)]));
  }
  return value;
}

function withOneFont(layer: Style["layers"][number]): Style["layers"][number] {
  const mapped = oneFont(layer) as Style["layers"][number];
  if (mapped.type !== "symbol" || mapped.layout?.["text-field"] === undefined) return mapped;
  return { ...mapped, layout: { ...mapped.layout, "text-font": [FONT] } };
}

export function localStyle(url: string, dark: boolean): Style {
  register();
  const origin = window.location.origin;
  const flavor = dark ? "dark" : "light";
  return {
    version: 8,
    glyphs: `${origin}/assets/map/fonts/{fontstack}/{range}.pbf`,
    sprite: `${origin}/assets/map/sprites/v4/${flavor}`,
    sources: { [SOURCE]: { type: "vector", url: `pmtiles://${url}` } },
    layers: layers(SOURCE, namedFlavor(flavor), { lang: "en" }).map(withOneFont),
  };
}
