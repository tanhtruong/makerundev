import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Page, PageHeading } from "@/components/layouts/page";
import { Button } from "@/components/ui/button";
import { ConnectSteps } from "@/features/strava/components/connect-steps";
import { Disconnect } from "@/features/strava/components/disconnect";
import { InlineCode } from "@/features/strava/components/prose";
import { SkippedActivities } from "@/features/strava/components/skipped-activities";
import { SyncPanel } from "@/features/strava/components/sync-panel";
import { CONNECT_NOTICES, type ConnectNotice } from "@/features/strava/utils/connect-notices";
import { useTimeZone } from "@/hooks/use-time-zone";
import { getStravaStatusQueryKey, useStravaStatus } from "@/lib/api/endpoints/strava/strava.gen";
import type { StravaStatus } from "@/lib/api/model/strava-status.gen";

const POLL_MS = 2000;

function disconnectedNotice(removed: number): string {
  const activities = removed === 1 ? "activity" : "activities";
  return `Disconnected from Strava. ${removed} ${activities} that came only from Strava ${removed === 1 ? "was" : "were"} deleted.`;
}

export function StravaPage({ notice, onNoticeRead }: { notice?: ConnectNotice; onNoticeRead: () => void }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const status = useStravaStatus({
    query: { refetchInterval: (query) => (query.state.data?.sync?.syncing ? POLL_MS : false) },
  });
  const timeZone = useTimeZone();
  const shown = message ?? (notice ? CONNECT_NOTICES[notice] : null);

  function show(text: string | null) {
    setMessage(text);
    if (notice) {
      onNoticeRead();
    }
  }

  function syncStarted(next: StravaStatus) {
    queryClient.setQueryData(getStravaStatusQueryKey(), next);
    show(null);
  }

  function disconnected(removed: number) {
    void queryClient.invalidateQueries();
    show(disconnectedNotice(removed));
  }

  return (
    <Page>
      <PageHeading>Strava</PageHeading>
      <p className="max-w-[65ch] text-muted-foreground">
        Bring your activities in from Strava, with their full streams. Tokens stay in this instance&apos;s data
        directory.
      </p>
      {shown && (
        <p role="status" className="mt-5 max-w-[65ch] border-y border-border py-3">
          {shown}
        </p>
      )}
      {status.isPending || timeZone.isPending ? (
        <div aria-busy="true" aria-label="Loading Strava status" className="mt-8 h-24 max-w-xl bg-muted" />
      ) : status.isError || timeZone.isError ? (
        <div role="alert" className="mt-8 flex items-center gap-4 border-y border-border py-6">
          <span>The Strava status could not be loaded.</span>
          <Button onClick={() => void Promise.all([status.refetch(), timeZone.refetch()])}>Try again</Button>
        </div>
      ) : (
        <Connection
          status={status.data}
          timeZone={timeZone.data}
          onSyncStarted={syncStarted}
          onDisconnected={disconnected}
        />
      )}
      <p className="mt-12 text-sm text-muted-foreground">Powered by Strava</p>
    </Page>
  );
}

function Connection({
  status,
  timeZone,
  onSyncStarted,
  onDisconnected,
}: {
  status: StravaStatus;
  timeZone: string;
  onSyncStarted: (next: StravaStatus) => void;
  onDisconnected: (removed: number) => void;
}) {
  if (!status.configured) {
    return <ConnectSteps callbackDomain={status.callback_domain} />;
  }
  if (!status.connected || status.sync === null) {
    return (
      <section className="mt-8 max-w-[65ch]">
        <form method="post" action="/strava/connect">
          <Button type="submit">Connect with Strava</Button>
        </form>
        <p className="mt-3 text-muted-foreground">
          Strava will ask you to let this instance read your activities. The callback domain of your API application
          must be <InlineCode>{status.callback_domain}</InlineCode>.
        </p>
      </section>
    );
  }
  return (
    <>
      <SyncPanel sync={status.sync} timeZone={timeZone} onStarted={onSyncStarted} />
      <SkippedActivities skipped={status.sync.skipped} timeZone={timeZone} />
      <Disconnect onDisconnected={onDisconnected} />
    </>
  );
}
