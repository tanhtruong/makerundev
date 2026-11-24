import { Button } from "@/components/ui/button";
import { syncOutcome } from "@/features/garmin/utils/sync-outcome";
import { useStartGarminSync } from "@/lib/api/endpoints/garmin/garmin.gen";
import type { GarminStatus } from "@/lib/api/model/garmin-status.gen";
import type { SyncStatus } from "@/lib/api/model/sync-status.gen";
import { localDay, localTime } from "@/lib/format";

function progress(sync: SyncStatus, timeZone: string): string {
  if (sync.syncing) {
    return "Syncing now, about one activity a second. This page updates on its own.";
  }
  const outcome = syncOutcome(sync, new Date());
  if (sync.last_sync_at) {
    return `${outcome} Last sync ${localDay(sync.last_sync_at, timeZone)} ${localTime(sync.last_sync_at, timeZone)}.`.trim();
  }
  return outcome || "Nothing synced yet.";
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="type-label">{label}</dt>
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
  onStarted: (status: GarminStatus) => void;
}) {
  const start = useStartGarminSync({ mutation: { onSuccess: onStarted } });
  const historyNote =
    sync.backfill_before && !sync.backfill_done
      ? ` History reaches back to ${localDay(sync.backfill_before, timeZone)} so far.`
      : "";

  return (
    <section aria-label="Sync" className="mt-8">
      <dl className="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
        <Stat label="Status" value={sync.syncing ? "Syncing" : "Key saved"} />
        <Stat label="Imported" value={sync.imported} />
        <Stat label="Already here" value={sync.matched} />
        <Stat label="History" value={sync.backfill_done ? "Complete" : "In progress"} />
      </dl>
      <p className="mt-5 max-w-[65ch] text-muted-foreground">
        {progress(sync, timeZone)}
        {historyNote}
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
      {start.isError && <p className="mt-2 text-sm">The sync could not be started. Try again.</p>}
    </section>
  );
}
