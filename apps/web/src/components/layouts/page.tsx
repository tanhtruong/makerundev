import type { ReactNode } from "react";

import { PAGE_WIDTH } from "@/components/layouts/page-width";

export function Page({ children }: { children: ReactNode }) {
  return <div className={`${PAGE_WIDTH} py-8 sm:py-10`}>{children}</div>;
}

export function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="font-condensed text-2xl leading-none font-bold">{children}</h2>;
}

export function PageHeading({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-6 flex items-baseline justify-between gap-4">
      <h1 className="font-condensed text-[2.5rem] leading-none font-bold">{children}</h1>
      {aside}
    </div>
  );
}
