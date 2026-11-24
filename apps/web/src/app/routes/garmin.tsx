import { createFileRoute } from "@tanstack/react-router";

import { GarminPage } from "@/features/garmin/components/garmin-page";

export const Route = createFileRoute("/garmin")({
  component: GarminPage,
});
