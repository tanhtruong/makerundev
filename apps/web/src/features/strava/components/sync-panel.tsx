import { Button } from "@/components/ui/button";
import { useStartStravaSync } from "@/lib/api/endpoints/strava/strava.gen";
import type { StravaStatus } from "@/lib/api/model/strava-status.gen";
import type { SyncStatus } from "@/lib/api/model/sync-status.gen";
import { localDay, localTime } from "@/lib/format";

const OUTCOMES: Record<Exclude<NonNullable<SyncStatus["outcome"]>, "paused">, string> = {
  up_to_date: "Up to date.",
  failed: "The sync stopped on an unexpected error. See the server log.",
  interrupted: "The last sync was interrupted. Sync again to continue.",
  paused_short: "Paused at Strava's 15-minute rate limit. Sync again in a quarter of an hour.",
  paused_daily: "Paused at Strava's daily rate limit. Sync again after midnight UTC.",
  rejected: "Strava no longer accepts this connection. Disconnect and connect again.",
  unreachable: "Strava could not be reached. Sync again later.",
};

function progress(sync: SyncStatus, timeZone: string): string {
  if (sync.syncing) {
    return "Syncing now. This page updates on its own.";
  }
  const outcome = sync.outcome && sync.outcome !== "paused" ? OUTCOMES[sync.outcome] : "";
  if (sync.last_sync_at) {
    return `${outcome} Last sync ${localDay(sync.last_sync_at, timeZone)} ${localTime(sync.last_sync_at, timeZone)}.`.trim();
  }
  return outcome || "Nothing synced yet.";
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="font-semi-condensed text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="font-semi-condensed text-xl font-semibold">{value}</dd>
    </div>
  );
}

export function SyncPanel({
  sync,
  timeZone,
  onStarted,
}: {
  sync: SyncStatus;
  timeZone: string;
  onStarted: (status: StravaStatus) => void;
}) {
  const start = useStartStravaSync({ mutation: { onSuccess: onStarted } });
  const history =
    sync.backfill_before && !sync.backfill_done
      ? ` History reaches back to ${localDay(sync.backfill_before, timeZone)} so far.`
      : "";

  return (
    <section aria-label="Sync" className="mt-8">
      <dl className="grid max-w-3xl grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
        <Stat label="Status" value={sync.syncing ? "Syncing" : "Connected"} />
        <Stat label="Imported" value={sync.imported} />
        <Stat label="Matched to files" value={sync.matched} />
        <Stat label="History" value={sync.backfill_done ? "Complete" : "In progress"} />
      </dl>
      <p className="mt-5 max-w-[65ch] text-muted-foreground">
        {progress(sync, timeZone)}
        {history}
      </p>
      <Button
        className="mt-4"
        disabled={sync.syncing || start.isPending}
        onClick={() => {
          start.mutate();
        }}
      >
        Sync now
      </Button>
      {start.isError && <p className="mt-2 text-sm">The sync could not be started. Reload the page and try again.</p>}
    </section>
  );
}
