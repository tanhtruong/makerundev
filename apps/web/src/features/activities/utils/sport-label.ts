import type { Sport } from "@/lib/api/model/sport.gen";

const SPORTS: Record<Sport, { label: string; name: string }> = {
  running: { label: "Run", name: "Running" },
  trail_running: { label: "Trail run", name: "Trail running" },
  treadmill_running: { label: "Treadmill", name: "Treadmill running" },
  walking: { label: "Walk", name: "Walking" },
  hiking: { label: "Hike", name: "Hiking" },
  cycling: { label: "Ride", name: "Cycling" },
  swimming: { label: "Swim", name: "Swimming" },
  other: { label: "Other", name: "Other" },
};

export function sportLabel(sport: Sport): string {
  return SPORTS[sport].label;
}

export function sportName(sport: Sport): string {
  return SPORTS[sport].name;
}
