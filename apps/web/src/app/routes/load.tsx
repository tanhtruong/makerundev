import { createFileRoute } from "@tanstack/react-router";

import { TrainingLoad } from "@/features/training-load/components/training-load";
import { DEFAULT_RANGE, type LoadRange, parseRange } from "@/features/training-load/utils/ranges";

type LoadSearch = { days?: LoadRange };

export const Route = createFileRoute("/load")({
  validateSearch: (search: Record<string, unknown>): LoadSearch => ({ days: parseRange(search.days) }),
  component: TrainingLoadPage,
});

function TrainingLoadPage() {
  const { days = DEFAULT_RANGE } = Route.useSearch();
  return <TrainingLoad range={days} />;
}
