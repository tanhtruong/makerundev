import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { getGetActivityQueryKey, useSetActivityExclusion } from "@/lib/api/endpoints/activities/activities.gen";

export function ExclusionToggle({ activityId, excluded }: { activityId: number; excluded: boolean }) {
  const queryClient = useQueryClient();
  const mutation = useSetActivityExclusion({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetActivityQueryKey(activityId) }),
    },
  });

  return (
    <div className="mt-10 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-5">
      <Button
        disabled={mutation.isPending}
        onClick={() => {
          mutation.mutate({ activityId, data: { excluded: !excluded } });
        }}
      >
        {excluded ? "Include in VDOT and critical speed" : "Exclude from VDOT and critical speed"}
      </Button>
      {mutation.isError ? (
        <span role="alert">The change could not be saved. Try again.</span>
      ) : (
        excluded && (
          <span className="text-muted-foreground">
            Excluded from VDOT and critical speed on the training load page.
          </span>
        )
      )}
    </div>
  );
}
