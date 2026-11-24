import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Page, PageHeading } from "@/components/layouts/page";
import { LoadError } from "@/components/load-error";
import { KeyForm } from "@/features/garmin/components/key-form";
import { KeySteps } from "@/features/garmin/components/key-steps";
import { RemoveKey } from "@/features/garmin/components/remove-key";
import { SkippedActivities } from "@/features/garmin/components/skipped-activities";
import { SyncPanel } from "@/features/garmin/components/sync-panel";
import { useTimeZone } from "@/hooks/use-time-zone";
import { getGarminStatusQueryKey, useGarminStatus } from "@/lib/api/endpoints/garmin/garmin.gen";
import type { GarminStatus } from "@/lib/api/model/garmin-status.gen";

const POLL_MS = 2000;

export function GarminPage() {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const status = useGarminStatus({
    query: { refetchInterval: (query) => (query.state.data?.sync?.syncing ? POLL_MS : false) },
  });
  const timeZone = useTimeZone();

  function showStatus(next: GarminStatus, message: string | null) {
    queryClient.setQueryData(getGarminStatusQueryKey(), next);
    setNotice(message);
  }

  return (
    <Page>
      <div className="max-w-3xl">
        <PageHeading>Garmin</PageHeading>
        <p className="max-w-[65ch] text-muted-foreground">
          Bring your activities in from Garmin Connect as the original files your watch recorded. Your key stays in this
          instance&apos;s data directory.
        </p>
        {notice && (
          <p role="status" className="mt-5 max-w-[65ch] border-y border-border py-3">
            {notice}
          </p>
        )}
        {status.isPending || timeZone.isPending ? (
          <div aria-busy="true" aria-label="Loading Garmin status" className="mt-8 h-24 bg-muted" />
        ) : status.isError || timeZone.isError ? (
          <div className="mt-8">
            <LoadError
              onRetry={() => {
                void status.refetch();
                void timeZone.refetch();
              }}
            >
              The Garmin status could not be loaded.
            </LoadError>
          </div>
        ) : (
          <GarminStatusView sync={status.data.sync} timeZone={timeZone.data} showStatus={showStatus} />
        )}
      </div>
    </Page>
  );
}

function GarminStatusView({
  sync,
  timeZone,
  showStatus,
}: {
  sync: GarminStatus["sync"];
  timeZone: string;
  showStatus: (next: GarminStatus, message: string | null) => void;
}) {
  return (
    <>
      {sync ? (
        <>
          <SyncPanel
            sync={sync}
            timeZone={timeZone}
            onStarted={(next) => {
              showStatus(next, null);
            }}
          />
          <SkippedActivities skipped={sync.skipped} timeZone={timeZone} />
        </>
      ) : (
        <KeySteps />
      )}
      <KeyForm
        replacing={sync !== null}
        onSaved={(next) => {
          showStatus(next, "Key saved. Start a sync to bring your activities in.");
        }}
      />
      {sync && (
        <RemoveKey
          onRemoved={(next) => {
            showStatus(next, "Key removed. Activities imported from Garmin stay.");
          }}
        />
      )}
    </>
  );
}
