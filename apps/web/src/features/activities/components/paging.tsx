import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { PAGE_SIZE } from "@/features/activities/utils/list-search";

type PageItem = number | "gap-before" | "gap-after";

function pageItems(current: number, last: number): PageItem[] {
  const shown = [...new Set([1, current - 1, current, current + 1, last])]
    .filter((page) => page >= 1 && page <= last)
    .sort((a, b) => a - b);
  return shown.flatMap((page, index): PageItem[] => {
    const before = shown[index - 1];
    if (before === undefined || page - before === 1) return [page];
    if (page - before === 2) return [page - 1, page];
    return [page < current ? "gap-before" : "gap-after", page];
  });
}

const NUMBER =
  "inline-flex h-8 min-w-8 items-center justify-center border-b-2 border-transparent px-1 font-semi-condensed font-medium text-muted-foreground hover:border-rule/40 hover:text-foreground aria-[current=page]:border-rule aria-[current=page]:text-foreground";

export function Paging({
  page,
  shown,
  total,
  loading,
}: {
  page: number;
  shown: number;
  total: number;
  loading: boolean;
}) {
  const offset = (page - 1) * PAGE_SIZE;
  const last = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <nav aria-label="Pages" className="mt-5 flex flex-wrap items-center justify-between gap-4">
      <span className="text-muted-foreground">
        {loading ? `Loading page ${page}` : `${offset + 1}-${offset + shown} of ${total}`}
      </span>
      <div className="flex items-center gap-2">
        <PageLink page={page - 1} enabled={page > 1 && !loading}>
          Previous
        </PageLink>
        {last > 1 && (
          <ol className="hidden items-center gap-1 sm:flex">
            {pageItems(page, last).map((item) =>
              typeof item === "number" ? (
                <li key={item}>
                  <Link
                    to="/"
                    search={(previous) => ({ ...previous, page: item > 1 ? item : undefined })}
                    aria-current={item === page ? "page" : undefined}
                    aria-label={`Page ${item}`}
                    className={NUMBER}
                  >
                    {item}
                  </Link>
                </li>
              ) : (
                <li key={item} aria-hidden className="px-1 text-muted-foreground">
                  …
                </li>
              ),
            )}
          </ol>
        )}
        <PageLink page={page + 1} enabled={offset + shown < total && !loading}>
          Next
        </PageLink>
      </div>
    </nav>
  );
}

function PageLink({ page, enabled, children }: { page: number; enabled: boolean; children: ReactNode }) {
  if (!enabled) {
    return <Button disabled>{children}</Button>;
  }
  return (
    <Button asChild>
      <Link to="/" search={(previous) => ({ ...previous, page: page > 1 ? page : undefined })}>
        {children}
      </Link>
    </Button>
  );
}
