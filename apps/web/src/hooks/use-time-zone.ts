import { useGetSettings } from "@/lib/api/endpoints/settings/settings.gen";
import type { SettingsView } from "@/lib/api/model/settings-view.gen";

function athleteTimeZone(view: SettingsView): string {
  return view.settings?.timezone ?? "UTC";
}

export function useTimeZone() {
  return useGetSettings({ query: { select: athleteTimeZone } });
}
