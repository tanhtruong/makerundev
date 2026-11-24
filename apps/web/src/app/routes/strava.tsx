import { createFileRoute } from "@tanstack/react-router";

import { StravaPage } from "@/features/strava/components/strava-page";
import { CONNECT_NOTICES, type ConnectNotice } from "@/features/strava/utils/connect-notices";

type StravaSearch = { notice?: ConnectNotice };

function isNotice(value: unknown): value is ConnectNotice {
  return typeof value === "string" && Object.hasOwn(CONNECT_NOTICES, value);
}

export const Route = createFileRoute("/strava")({
  validateSearch: (search: Record<string, unknown>): StravaSearch =>
    isNotice(search.notice) ? { notice: search.notice } : {},
  component: StravaRoute,
});

function StravaRoute() {
  const { notice } = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <StravaPage
      notice={notice}
      onNoticeRead={() => {
        void navigate({ search: {}, replace: true });
      }}
    />
  );
}
