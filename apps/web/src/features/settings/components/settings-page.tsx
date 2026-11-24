import { Page, PageHeading } from "@/components/layouts/page";
import { LoadError } from "@/components/load-error";
import { SettingsForm } from "@/features/settings/components/settings-form";
import { useGetSettings } from "@/lib/api/endpoints/settings/settings.gen";

export function SettingsPage() {
  const query = useGetSettings();

  return (
    <Page>
      <PageHeading>Settings</PageHeading>
      <p className="mb-8 max-w-[65ch] text-muted-foreground">
        Your heart rate and body mass. Zones, TRIMP and estimated power are computed from them.
      </p>
      {query.isPending ? (
        <LoadingFields />
      ) : query.isError ? (
        <LoadError onRetry={() => void query.refetch()}>Your settings could not be loaded.</LoadError>
      ) : (
        <SettingsForm view={query.data} />
      )}
    </Page>
  );
}

function LoadingFields() {
  return (
    <div aria-busy="true" aria-label="Loading settings" className="grid max-w-2xl gap-6">
      {Array.from({ length: 4 }, (_, section) => (
        <div key={section} className="grid gap-3 border-t border-rule pt-3">
          <div className="h-3 w-24 bg-muted" />
          <div className="h-8 w-48 bg-muted" />
        </div>
      ))}
    </div>
  );
}
