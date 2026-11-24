import type { SyncStatus } from "@/lib/api/model/sync-status.gen";

const OUTCOMES: Partial<Record<NonNullable<SyncStatus["outcome"]>, string>> = {
  up_to_date: "Up to date.",
  failed: "The sync stopped on an unexpected error. See the server log.",
  interrupted: "The last sync was interrupted. Sync again to continue.",
  paused: "Garmin asked to slow down. Sync again later.",
  rejected:
    "Garmin no longer accepts this key: it has expired or was revoked. Create a new one in Garmin Connect under Settings, Personal API Key, and save it below.",
  unreachable: "Garmin could not be reached. Sync again later.",
};

export function syncOutcome(sync: Pick<SyncStatus, "outcome" | "resume_at">, now: Date): string {
  if (sync.outcome === "paused" && sync.resume_at !== null) {
    const left = Date.parse(sync.resume_at) - now.getTime();
    if (left > 0) {
      const minutes = Math.ceil(left / 60_000);
      return `Garmin asked to slow down. Sync again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`;
    }
  }
  return sync.outcome ? (OUTCOMES[sync.outcome] ?? "") : "";
}
