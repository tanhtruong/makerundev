import "maplibre-gl/dist/maplibre-gl.css";

import { cn } from "cn";
import {
  AttributionControl,
  GPUInitializationError,
  LngLatBounds,
  Map as MapLibre,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { MapNote } from "@/features/map/components/map-note";
import { prefersDark, routeColors, usePrefersDark } from "@/features/map/utils/color-scheme";
import { escapeHtml } from "@/features/map/utils/escape-html";
import { isRouteSource, rasterStyle, styleUrl, withRoute } from "@/features/map/utils/map-style";
import type { MapSource } from "@/lib/api/model/map-source.gen";
import type { RoutePoint } from "@/lib/api/model/route-point.gen";

setWorkerUrl(workerUrl);

type MapState = "loading" | "ready" | "tiles-failed" | "style-failed" | "unsupported";

const MAX_ZOOM = 16;
const PADDING = 32;

type Shown = { live: () => boolean; failed: () => void };

function show(map: MapLibre, source: MapSource, dark: boolean, points: RoutePoint[], shown: Shown) {
  const colors = routeColors();
  const url = styleUrl(source, dark);
  if (source.rendering === "pmtiles") {
    import("@/features/map/utils/local-style").then(({ localStyle }) => {
      if (shown.live()) map.setStyle(withRoute(localStyle(url, dark), points, colors));
    }, shown.failed);
  } else if (source.rendering === "raster") {
    map.setStyle(withRoute(rasterStyle(url, colors), points, colors));
  } else {
    map.setStyle(url, { transformStyle: (_, next) => withRoute(next, points, colors) });
  }
}

export function MapCanvas({
  source,
  points,
  fallback,
}: {
  source: MapSource;
  points: RoutePoint[];
  fallback: ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibre | null>(null);
  const shownDark = useRef<boolean | null>(null);
  const [state, setState] = useState<MapState>("loading");
  const dark = usePrefersDark();

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const bounds = points.reduce(
      (box, point) => box.extend([point.longitude_deg, point.latitude_deg]),
      new LngLatBounds(),
    );
    let created: MapLibre;
    try {
      created = new MapLibre({
        container: element,
        bounds,
        fitBoundsOptions: { padding: PADDING, maxZoom: MAX_ZOOM },
        cooperativeGestures: true,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
    } catch (error) {
      if (error instanceof GPUInitializationError) {
        queueMicrotask(() => {
          setState("unsupported");
        });
        return;
      }
      throw error;
    }
    map.current = created;
    created.touchZoomRotate.disableRotation();
    created.addControl(new NavigationControl({ showCompass: false }), "top-right");
    created.addControl(
      new AttributionControl({ compact: false, customAttribution: escapeHtml(source.attribution) }),
      "bottom-right",
    );

    let styleLoaded = false;
    let loaded = false;
    let tileErrors = 0;
    let tilesLoaded = 0;
    created.on("style.load", () => {
      styleLoaded = true;
    });
    created.on("error", (event) => {
      if ("tile" in event && event.tile) {
        tileErrors += 1;
      } else if (!styleLoaded || (!loaded && "sourceId" in event && !isRouteSource(String(event.sourceId)))) {
        setState("style-failed");
      }
    });
    created.on("sourcedata", (event) => {
      if (event.tile !== undefined && !isRouteSource(event.sourceId)) tilesLoaded += 1;
    });
    created.once("load", () => {
      loaded = true;
      setState((current) => (current === "loading" ? "ready" : current));
    });
    created.on("idle", () => {
      if (tileErrors > 0 && tilesLoaded === 0) setState("tiles-failed");
    });

    const initialDark = prefersDark();
    shownDark.current = initialDark;
    show(created, source, initialDark, points, {
      live: () => map.current === created,
      failed: () => {
        setState("style-failed");
      },
    });

    return () => {
      map.current = null;
      created.remove();
    };
  }, [source, points]);

  useEffect(() => {
    const current = map.current;
    if (!current || shownDark.current === dark) return;
    shownDark.current = dark;
    show(current, source, dark, points, {
      live: () => map.current === current,
      failed: () => {
        setState("style-failed");
      },
    });
  }, [dark, source, points]);

  const mapShown = state === "ready" || state === "tiles-failed";
  const note = <MapNote>Map tiles could not be loaded from {source.provider}.</MapNote>;

  return (
    <div className="relative grid">
      <div className={cn("col-start-1 row-start-1 grid", mapShown && "invisible")} aria-hidden={mapShown}>
        {fallback}
      </div>
      {state !== "unsupported" && (
        <figure
          className={cn("col-start-1 row-start-1 flex flex-col", !mapShown && "invisible")}
          aria-hidden={!mapShown}
        >
          <figcaption className="mb-2 type-label">Route</figcaption>
          <div className="relative min-h-0 flex-1 border-y border-border">
            <div className="absolute inset-0">
              <div ref={container} className="size-full" />
            </div>
            {state === "tiles-failed" && note}
          </div>
        </figure>
      )}
      {state === "style-failed" && note}
    </div>
  );
}
