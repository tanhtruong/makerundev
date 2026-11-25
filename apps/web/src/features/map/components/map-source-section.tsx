import { LoadError } from "@/components/load-error";
import { MapSourceForm } from "@/features/map/components/map-source-form";
import { useGetMapSource } from "@/lib/api/endpoints/map/map.gen";

export function MapSourceSection() {
  const query = useGetMapSource({ query: { staleTime: Infinity } });

  return (
    <section aria-label="Map settings" className="mt-12">
      {query.isPending ? (
        <div
          aria-busy="true"
          aria-label="Loading the map setting"
          className="grid max-w-2xl gap-3 border-t border-rule pt-3"
        >
          <div className="h-3 w-24 bg-muted" />
          <div className="h-24 w-64 bg-muted" />
        </div>
      ) : query.isError ? (
        <LoadError onRetry={() => void query.refetch()}>The map setting could not be loaded.</LoadError>
      ) : (
        <MapSourceForm view={query.data} />
      )}
    </section>
  );
}
