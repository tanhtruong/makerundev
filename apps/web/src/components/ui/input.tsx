import { cn } from "cn";
import type * as React from "react";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      className={cn(
        "h-8 w-full min-w-0 border border-rule bg-background px-2.5 text-[15px] placeholder:text-muted-foreground aria-invalid:bg-muted",
        className,
      )}
      {...props}
    />
  );
}
