import { createFileRoute, notFound } from "@tanstack/react-router";

import { ActivityDetail } from "@/features/activities/components/activity-detail";
import { RouteMap } from "@/features/map/components/route-map";

export const Route = createFileRoute("/activities/$activityId")({
  params: {
    parse: ({ activityId }) => {
      if (!/^[1-9]\d{0,15}$/.test(activityId)) {
        throw notFound();
      }
      return { activityId: Number(activityId) };
    },
    stringify: ({ activityId }) => ({ activityId: String(activityId) }),
  },
  component: ActivityPage,
});

function ActivityPage() {
  const { activityId } = Route.useParams();
  return (
    <ActivityDetail activityId={activityId} route={(points, shape) => <RouteMap points={points} fallback={shape} />} />
  );
}
