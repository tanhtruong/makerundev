import type { Sport } from "@/lib/api/model/sport.gen";

const LABELS: Record<Sport, string> = {
  running: "Run",
  trail_running: "Trail run",
  treadmill_running: "Treadmill",
  walking: "Walk",
  hiking: "Hike",
  cycling: "Ride",
  swimming: "Swim",
  other: "Other",
};

export function sportLabel(sport: Sport): string {
  return LABELS[sport];
}
