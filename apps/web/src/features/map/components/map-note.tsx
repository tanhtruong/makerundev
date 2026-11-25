import type { ReactNode } from "react";

export function MapNote({ children }: { children: ReactNode }) {
  return (
    <p className="absolute bottom-2 left-2 z-10 max-w-[calc(100%-1rem)] bg-background/90 px-2 py-1 text-sm">
      {children}
    </p>
  );
}
