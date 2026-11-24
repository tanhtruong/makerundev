import { cn } from "cn";
import { Label as LabelPrimitive } from "radix-ui";
import type * as React from "react";

export function Label({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root data-slot="label" className={cn("text-sm font-medium select-none", className)} {...props} />
  );
}
