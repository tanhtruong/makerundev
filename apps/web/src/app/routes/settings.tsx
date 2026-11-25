import { createFileRoute } from "@tanstack/react-router";

import { MapSourceSection } from "@/features/map/components/map-source-section";
import { SettingsPage } from "@/features/settings/components/settings-page";

export const Route = createFileRoute("/settings")({
  component: Settings,
});

function Settings() {
  return (
    <SettingsPage>
      <MapSourceSection />
    </SettingsPage>
  );
}
