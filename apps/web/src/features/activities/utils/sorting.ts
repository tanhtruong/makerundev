import type { ListActivitiesSort } from "@/lib/api/model/list-activities-sort.gen";

export type SortKey =
  "start_time" | "distance_m" | "moving_s" | "pace_s_per_km" | "avg_heart_rate_bpm" | "elevation_gain_m" | "trimp";

const SORT_OPTIONS: Record<SortKey, { first: "asc" | "desc"; asc: string; desc: string }> = {
  start_time: { first: "desc", desc: "Newest first", asc: "Oldest first" },
  distance_m: { first: "desc", desc: "Longest first", asc: "Shortest first" },
  moving_s: { first: "desc", desc: "Most moving time", asc: "Least moving time" },
  pace_s_per_km: { first: "asc", asc: "Fastest pace", desc: "Slowest pace" },
  avg_heart_rate_bpm: { first: "desc", desc: "Highest avg HR", asc: "Lowest avg HR" },
  elevation_gain_m: { first: "desc", desc: "Most climb", asc: "Least climb" },
  trimp: { first: "desc", desc: "Highest TRIMP", asc: "Lowest TRIMP" },
};

export function sortOf(key: SortKey, direction: "asc" | "desc"): ListActivitiesSort {
  return direction === "desc" ? `-${key}` : key;
}

export function sortParts(sort: ListActivitiesSort): { key: SortKey; direction: "asc" | "desc" } {
  return sort.startsWith("-")
    ? { key: sort.slice(1) as SortKey, direction: "desc" }
    : { key: sort as SortKey, direction: "asc" };
}

export function nextSort(current: ListActivitiesSort, key: SortKey): ListActivitiesSort {
  const { key: sorted, direction } = sortParts(current);
  if (sorted === key) return sortOf(key, direction === "asc" ? "desc" : "asc");
  return sortOf(key, SORT_OPTIONS[key].first);
}

export function sortChoices(): { sort: ListActivitiesSort; label: string }[] {
  return (Object.keys(SORT_OPTIONS) as SortKey[]).flatMap((key) => {
    const option = SORT_OPTIONS[key];
    const second = option.first === "asc" ? "desc" : "asc";
    return [
      { sort: sortOf(key, option.first), label: option[option.first] },
      { sort: sortOf(key, second), label: option[second] },
    ];
  });
}
