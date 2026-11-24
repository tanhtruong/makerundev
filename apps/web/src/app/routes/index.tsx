import { createFileRoute } from "@tanstack/react-router";

import { ActivityList } from "@/features/activities/components/activity-list";
import { parseListSearch } from "@/features/activities/utils/list-search";

export const Route = createFileRoute("/")({
  validateSearch: parseListSearch,
  component: ActivitiesPage,
});

function ActivitiesPage() {
  return <ActivityList search={Route.useSearch()} />;
}
