import type { ReactNode } from "react";

const COLUMNS = { 2: "sm:grid-cols-2", 4: "grid-cols-2 sm:grid-cols-4" };

export function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="mb-3 font-condensed text-2xl leading-tight font-bold">
      {children}
    </h2>
  );
}

export function Figures({ columns, children }: { columns: keyof typeof COLUMNS; children: ReactNode }) {
  return <dl className={`grid gap-x-6 border-y border-border ${COLUMNS[columns]}`}>{children}</dl>;
}

export function Figure({
  label,
  value,
  detail,
  missing,
}: {
  label: string;
  value?: ReactNode;
  detail?: ReactNode;
  missing?: string;
}) {
  return (
    <div className="flex flex-col gap-1 py-4">
      <dt className="font-semi-condensed text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </dt>
      {value === undefined ? (
        <dd className="max-w-[65ch] text-muted-foreground">{missing}</dd>
      ) : (
        <dd className="font-condensed text-3xl leading-none font-bold">{value}</dd>
      )}
      {detail && <dd className="text-sm text-muted-foreground">{detail}</dd>}
    </div>
  );
}
