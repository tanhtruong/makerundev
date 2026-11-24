import type { ListActivitiesParams } from "@/lib/api/model/list-activities-params.gen";
import { ListActivitiesSort } from "@/lib/api/model/list-activities-sort.gen";
import { Sport } from "@/lib/api/model/sport.gen";

export const PERIODS = ["this_month", "this_year"] as const;
export type Period = (typeof PERIODS)[number];

export type ListSearch = {
  q?: string;
  period?: Period;
  from?: string;
  to?: string;
  sport?: Sport[];
  min_km?: number;
  max_km?: number;
  sort?: ListActivitiesSort;
  page?: number;
};

export const PAGE_SIZE = 50;
export const DEFAULT_SORT: ListActivitiesSort = "-start_time";
const MAX_QUERY_LENGTH = 100;
const SPORTS = Object.values(Sport);
const SORTS = Object.values(ListActivitiesSort);
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function text(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function listOf(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [value];
}

function day(value: unknown): string | undefined {
  const candidate = text(value);
  if (!candidate || !DATE.test(candidate)) return undefined;
  const parsed = new Date(`${candidate}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().startsWith(candidate) ? candidate : undefined;
}

function kilometres(value: unknown): number | undefined {
  const parsed = typeof value === "number" ? value : text(value)?.trim() ? Number(value) : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function ordered<T extends string | number>(low: T | undefined, high: T | undefined): [T | undefined, T | undefined] {
  return low !== undefined && high !== undefined && low > high ? [high, low] : [low, high];
}

export function parseListSearch(search: Record<string, unknown>): ListSearch {
  const q = text(search.q)?.trim().slice(0, MAX_QUERY_LENGTH);
  const period = PERIODS.find((option) => option === search.period);
  const [from, to] = period ? [undefined, undefined] : ordered(day(search.from), day(search.to));
  const sport = SPORTS.filter((option) => listOf(search.sport).includes(option));
  const [min_km, max_km] = ordered(kilometres(search.min_km), kilometres(search.max_km));
  const sort = SORTS.find((option) => option === search.sort && option !== DEFAULT_SORT);
  const page = Number(search.page);
  return {
    q: q || undefined,
    period,
    from,
    to,
    sport: sport.length > 0 ? sport : undefined,
    min_km,
    max_km,
    sort,
    page: Number.isInteger(page) && page > 1 ? page : undefined,
  };
}

export function filterCount(search: ListSearch): number {
  return [search.period ?? search.from ?? search.to, search.sport, search.min_km ?? search.max_km].filter(
    (value) => value !== undefined,
  ).length;
}

export function isFiltered(search: ListSearch): boolean {
  return filterCount(search) > 0 || search.q !== undefined;
}

export function withoutFilters(search: ListSearch): ListSearch {
  return search.sort ? { sort: search.sort } : {};
}

function today(timeZone: string, now: Date): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function periodStart(period: Period, timeZone: string, now: Date): string {
  const date = today(timeZone, now);
  return period === "this_month" ? `${date.slice(0, 7)}-01` : `${date.slice(0, 4)}-01-01`;
}

function metres(km: number | undefined): number | undefined {
  return km === undefined ? undefined : Math.round(km * 1000);
}

export function apiParams(search: ListSearch, timeZone: string, now: Date): ListActivitiesParams {
  return {
    limit: PAGE_SIZE,
    offset: ((search.page ?? 1) - 1) * PAGE_SIZE,
    q: search.q,
    sport: search.sport,
    min_distance_m: metres(search.min_km),
    max_distance_m: metres(search.max_km),
    from: search.period ? periodStart(search.period, timeZone, now) : search.from,
    to: search.period ? undefined : search.to,
    sort: search.sort,
  };
}
