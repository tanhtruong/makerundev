import type { GetTrainingLoadDays } from "@/lib/api/model/get-training-load-days.gen";

export const LOAD_RANGES = [90, 180, 365, "all"] as const;

export type LoadRange = (typeof LOAD_RANGES)[number];

export const DEFAULT_RANGE: LoadRange = 180;

export function parseRange(value: unknown): LoadRange | undefined {
  return LOAD_RANGES.find((range) => range === value || String(range) === value);
}

export function rangeLabel(range: LoadRange): string {
  return range === "all" ? "All" : `${range} days`;
}

export function apiDays(range: LoadRange): GetTrainingLoadDays {
  return String(range) as GetTrainingLoadDays;
}
