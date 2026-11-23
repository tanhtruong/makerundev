import { cn } from "cn";
import { Slot } from "radix-ui";
import type * as React from "react";

const BUTTON =
  "inline-flex h-8 shrink-0 items-center justify-center rounded-md border border-rule bg-background px-3 text-sm font-medium whitespace-nowrap transition-colors duration-150 hover:bg-accent disabled:pointer-events-none disabled:border-dashed disabled:border-input disabled:text-muted-foreground";

export function Button({
  className,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp data-slot="button" className={cn(BUTTON, className)} {...props} />;
}
