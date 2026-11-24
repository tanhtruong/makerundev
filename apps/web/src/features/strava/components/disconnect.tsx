import { Button } from "@/components/ui/button";
import { useDisconnectStrava } from "@/lib/api/endpoints/strava/strava.gen";

export function Disconnect({ onDisconnected }: { onDisconnected: (removed: number) => void }) {
  const disconnect = useDisconnectStrava({
    mutation: {
      onSuccess: (result) => {
        onDisconnected(result.removed_activities);
      },
    },
  });

  return (
    <details className="mt-10 max-w-[65ch]">
      <summary className="cursor-pointer text-muted-foreground">Disconnect</summary>
      <p className="mt-3">
        Disconnecting revokes this instance&apos;s access and deletes every activity that came only from Strava.
        Activities imported from files stay.
      </p>
      <Button
        className="mt-3"
        disabled={disconnect.isPending}
        onClick={() => {
          disconnect.mutate();
        }}
      >
        Disconnect and delete synced activities
      </Button>
      {disconnect.isError && <p className="mt-2 text-sm">Strava could not be disconnected. Try again.</p>}
    </details>
  );
}
