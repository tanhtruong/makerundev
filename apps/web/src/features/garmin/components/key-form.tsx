import { type SubmitEvent, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSaveGarminKey } from "@/lib/api/endpoints/garmin/garmin.gen";
import type { GarminStatus } from "@/lib/api/model/garmin-status.gen";
import type { HTTPValidationError } from "@/lib/api/model/httpvalidation-error.gen";
import type { ApiError } from "@/lib/api-client";

function keyError(error: ApiError): string {
  if (error.status === 422) {
    const message = (error.body as HTTPValidationError | null)?.detail?.[0]?.msg;
    if (message) {
      return message;
    }
  }
  if (error.status === 502) {
    return "Garmin could not be reached to check the key. Try again later.";
  }
  return "The key could not be saved. Try again.";
}

export function KeyForm({ replacing, onSaved }: { replacing: boolean; onSaved: (status: GarminStatus) => void }) {
  const id = useId();
  const [key, setKey] = useState("");
  const save = useSaveGarminKey<ApiError>({
    mutation: {
      onSuccess: (status) => {
        setKey("");
        onSaved(status);
      },
    },
  });

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate({ data: { key } });
  }

  return (
    <form onSubmit={submit} className="mt-10 grid max-w-md gap-2">
      <Label htmlFor={`${id}-key`}>{replacing ? "Replace the key" : "Personal API key"}</Label>
      <Input
        id={`${id}-key`}
        type="password"
        autoComplete="off"
        spellCheck={false}
        required
        value={key}
        onChange={(event) => {
          setKey(event.target.value);
        }}
        aria-invalid={save.isError}
        aria-describedby={save.isError ? `${id}-error` : undefined}
      />
      {save.isError && (
        <p id={`${id}-error`} className="text-sm">
          {keyError(save.error)}
        </p>
      )}
      <Button type="submit" disabled={save.isPending} className="mt-1 justify-self-start">
        {save.isPending ? "Checking key" : "Save key"}
      </Button>
    </form>
  );
}
