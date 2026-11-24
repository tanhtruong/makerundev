import { Button } from "@/components/ui/button";
import { useRemoveGarminKey } from "@/lib/api/endpoints/garmin/garmin.gen";
import type { GarminStatus } from "@/lib/api/model/garmin-status.gen";

export function RemoveKey({ onRemoved }: { onRemoved: (status: GarminStatus) => void }) {
  const remove = useRemoveGarminKey({ mutation: { onSuccess: onRemoved } });

  return (
    <details className="mt-10 max-w-[65ch]">
      <summary className="cursor-pointer text-muted-foreground">Remove key</summary>
      <p className="mt-3">
        Removing the key deletes it and the sync progress from this instance. Activities already imported from Garmin
        stay, like any other file.
      </p>
      <Button
        className="mt-3"
        disabled={remove.isPending}
        onClick={() => {
          remove.mutate();
        }}
      >
        Remove key
      </Button>
      {remove.isError && <p className="mt-2 text-sm">The key could not be removed. Try again.</p>}
    </details>
  );
}
