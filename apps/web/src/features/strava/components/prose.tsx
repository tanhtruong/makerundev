import type { ReactNode } from "react";

export function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="font-condensed text-2xl leading-none font-bold">{children}</h2>;
}

export function InlineCode({ children }: { children: ReactNode }) {
  return <code className="bg-muted px-1 text-foreground">{children}</code>;
}
