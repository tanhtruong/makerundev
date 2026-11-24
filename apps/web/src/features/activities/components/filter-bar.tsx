import { useNavigate } from "@tanstack/react-router";
import { type ReactNode, useCallback, useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DEFAULT_SORT,
  filterCount,
  isFiltered,
  type ListSearch,
  withoutFilters,
} from "@/features/activities/utils/list-search";
import { sortChoices } from "@/features/activities/utils/sorting";
import { sportLabel } from "@/features/activities/utils/sport-label";
import { ListActivitiesSort } from "@/lib/api/model/list-activities-sort.gen";
import { Sport } from "@/lib/api/model/sport.gen";

const TOGGLE =
  "border-b-2 border-transparent py-1 font-medium whitespace-nowrap text-muted-foreground hover:border-rule/40 hover:text-foreground aria-pressed:border-rule aria-pressed:text-foreground";
const SELECT = "h-8 border border-rule bg-background px-2 text-[15px]";
const LABEL = "w-20 shrink-0 type-label text-muted-foreground";
const SEARCH_WAIT_MS = 300;

type Change = (update: (previous: ListSearch) => ListSearch, replace?: boolean) => void;

function useChange(): Change {
  const navigate = useNavigate({ from: "/" });
  return useCallback(
    (update, replace = false) => {
      void navigate({ search: (previous) => ({ ...update(previous), page: undefined }), replace });
    },
    [navigate],
  );
}

export function FilterBar({ search }: { search: ListSearch }) {
  const change = useChange();
  const [open, setOpen] = useState(false);
  const [clears, setClears] = useState(0);
  const panel = useId();
  const count = filterCount(search);

  return (
    <section aria-label="Filters" className="mb-6 space-y-3 border-b border-border pb-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <SearchBox q={search.q} change={change} />
        <Button
          className="sm:hidden"
          aria-expanded={open}
          aria-controls={panel}
          onClick={() => {
            setOpen(!open);
          }}
        >
          {count > 0 ? `Filters · ${count}` : "Filters"}
        </Button>
        <SortSelect sort={search.sort ?? DEFAULT_SORT} change={change} />
      </div>
      <div id={panel} className={`space-y-2 ${open ? "" : "hidden sm:block"}`}>
        <DateChoices key={clears} search={search} change={change} />
        <Choices label="Sport">
          {Object.values(Sport).map((sport) => {
            const chosen = search.sport?.includes(sport) ?? false;
            return (
              <button
                key={sport}
                type="button"
                aria-pressed={chosen}
                className={TOGGLE}
                onClick={() => {
                  change((previous) => {
                    const sports = (previous.sport ?? []).filter((option) => option !== sport);
                    const next = chosen ? sports : [...sports, sport];
                    return { ...previous, sport: next.length > 0 ? next : undefined };
                  });
                }}
              >
                {sportLabel(sport)}
              </button>
            );
          })}
        </Choices>
        <DistanceRange search={search} change={change}>
          <Button
            className="ml-auto"
            disabled={!isFiltered(search)}
            onClick={() => {
              setClears(clears + 1);
              change(withoutFilters);
            }}
          >
            Clear
          </Button>
        </DistanceRange>
      </div>
    </section>
  );
}

function Choices({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <div role="group" aria-labelledby={id} className="flex items-start gap-x-5">
      <span id={id} className={`${LABEL} leading-8`}>
        {label}
      </span>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-1">{children}</div>
    </div>
  );
}

function SearchBox({ q, change }: { q: string | undefined; change: Change }) {
  const id = useId();
  const [text, setText] = useState(q ?? "");
  const [shown, setShown] = useState(q);
  if (q !== shown) {
    setShown(q);
    setText(q ?? "");
  }
  const wanted = text.trim();

  useEffect(() => {
    if (wanted === (q ?? "")) return;
    const timer = setTimeout(() => {
      change((previous) => ({ ...previous, q: wanted || undefined }), true);
    }, SEARCH_WAIT_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [wanted, q, change]);

  return (
    <div className="flex w-full flex-col gap-1 sm:w-auto sm:flex-row sm:items-center sm:gap-x-5">
      <Label htmlFor={id} className={LABEL}>
        Search
      </Label>
      <Input
        id={id}
        type="search"
        className="w-full sm:w-80"
        placeholder="Name or file"
        maxLength={100}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
    </div>
  );
}

function SortSelect({ sort, change }: { sort: ListActivitiesSort; change: Change }) {
  const id = useId();
  return (
    <div className="flex items-center gap-x-2 md:hidden">
      <Label htmlFor={id} className="type-label text-muted-foreground">
        Sort
      </Label>
      <select
        id={id}
        value={sort}
        className={`block ${SELECT}`}
        onChange={(event) => {
          const next = Object.values(ListActivitiesSort).find((option) => option === event.target.value);
          change((previous) => ({ ...previous, sort: next === DEFAULT_SORT ? undefined : next }));
        }}
      >
        {sortChoices().map((choice) => (
          <option key={choice.sort} value={choice.sort}>
            {choice.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function DateChoices({ search, change }: { search: ListSearch; change: Change }) {
  const hasRange = search.from !== undefined || search.to !== undefined;
  const [custom, setCustom] = useState(hasRange);
  const [hadRange, setHadRange] = useState(hasRange);
  if (hasRange !== hadRange) {
    setHadRange(hasRange);
    setCustom(hasRange);
  }
  const showRange = custom || hasRange;
  const preset = (period: ListSearch["period"]) => {
    setCustom(false);
    change((previous) => ({ ...previous, period, from: undefined, to: undefined }));
  };
  const all = !search.period && !showRange;

  return (
    <Choices label="Date">
      <button
        type="button"
        aria-pressed={all}
        className={TOGGLE}
        onClick={() => {
          preset(undefined);
        }}
      >
        All
      </button>
      <button
        type="button"
        aria-pressed={search.period === "this_month"}
        className={TOGGLE}
        onClick={() => {
          preset("this_month");
        }}
      >
        This month
      </button>
      <button
        type="button"
        aria-pressed={search.period === "this_year"}
        className={TOGGLE}
        onClick={() => {
          preset("this_year");
        }}
      >
        This year
      </button>
      <button
        type="button"
        aria-pressed={showRange}
        className={TOGGLE}
        onClick={() => {
          setCustom(true);
          if (search.period) change((previous) => ({ ...previous, period: undefined }));
        }}
      >
        Custom
      </button>
      {showRange && (
        <span className="flex flex-wrap items-center gap-2">
          <DateField
            label="From"
            value={search.from}
            max={search.to}
            onChange={(from) => {
              change((previous) => ({ ...previous, from }));
            }}
          />
          <span className="text-muted-foreground">to</span>
          <DateField
            label="To"
            value={search.to}
            min={search.from}
            onChange={(to) => {
              change((previous) => ({ ...previous, to }));
            }}
          />
        </span>
      )}
    </Choices>
  );
}

function DateField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: string | undefined;
  min?: string;
  max?: string;
  onChange: (value: string | undefined) => void;
}) {
  const id = useId();
  return (
    <span>
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <Input
        id={id}
        type="date"
        className="w-40"
        value={value ?? ""}
        min={min}
        max={max}
        onChange={(event) => {
          onChange(event.target.value || undefined);
        }}
      />
    </span>
  );
}

function DistanceRange({ search, change, children }: { search: ListSearch; change: Change; children: ReactNode }) {
  return (
    <Choices label="Distance">
      <span className="flex items-center gap-2">
        <KilometreField
          label="Min km"
          value={search.min_km}
          onApply={(min_km) => {
            change((previous) => ({ ...previous, min_km }));
          }}
        />
        <span className="text-muted-foreground">to</span>
        <KilometreField
          label="Max km"
          value={search.max_km}
          onApply={(max_km) => {
            change((previous) => ({ ...previous, max_km }));
          }}
        />
        <span className="text-muted-foreground">km</span>
      </span>
      {children}
    </Choices>
  );
}

function KilometreField({
  label,
  value,
  onApply,
}: {
  label: string;
  value: number | undefined;
  onApply: (value: number | undefined) => void;
}) {
  const id = useId();
  const apply = (field: HTMLInputElement) => {
    const parsed = field.value === "" ? undefined : Number(field.value);
    const next = parsed !== undefined && Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
    if (next !== value) onApply(next);
    if (next === undefined && field.value !== "") field.value = value === undefined ? "" : String(value);
  };

  return (
    <span>
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <Input
        key={value ?? "none"}
        id={id}
        type="number"
        inputMode="decimal"
        min={0}
        step={0.1}
        className="w-20"
        defaultValue={value ?? ""}
        onBlur={(event) => {
          apply(event.target);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") apply(event.currentTarget);
        }}
      />
    </span>
  );
}
