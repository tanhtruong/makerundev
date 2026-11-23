import { createFileRoute } from "@tanstack/react-router";

import { ActivityList } from "@/features/activities/components/activity-list";

type ListSearch = { page?: number };

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>): ListSearch => {
    const page = Number(search.page);
    return Number.isInteger(page) && page > 1 ? { page } : {};
  },
  component: ActivitiesPage,
});

function ActivitiesPage() {
  const { page = 1 } = Route.useSearch();
  return <ActivityList page={page} />;
}
