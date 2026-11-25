import { useSyncExternalStore } from "react";

import type { RouteColors } from "@/features/map/utils/map-style";

const DARK = "(prefers-color-scheme: dark)";

function subscribe(onChange: () => void): () => void {
  const query = window.matchMedia(DARK);
  query.addEventListener("change", onChange);
  return () => {
    query.removeEventListener("change", onChange);
  };
}

export function prefersDark(): boolean {
  return window.matchMedia(DARK).matches;
}

export function usePrefersDark(): boolean {
  return useSyncExternalStore(subscribe, prefersDark);
}

export function routeColors(): RouteColors {
  const style = getComputedStyle(document.documentElement);
  const read = (name: string) => style.getPropertyValue(name).trim();
  return { line: read("--foreground"), casing: read("--background"), background: read("--background") };
}
