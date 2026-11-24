import { Link } from "@tanstack/react-router";

import { PAGE_WIDTH } from "@/components/layouts/page-width";

const FOCUS = "focus-visible:outline-tartan-foreground";
const ITEM = `border-b-2 border-transparent py-1 font-medium whitespace-nowrap hover:border-tartan-foreground/60 data-[status=active]:border-tartan-foreground ${FOCUS}`;

export function AppHeader() {
  return (
    <header className="bg-tartan text-tartan-foreground">
      <div className={`${PAGE_WIDTH} flex flex-col gap-x-8 gap-y-1 py-2.5 sm:h-14 sm:flex-row sm:items-center sm:py-0`}>
        <Link to="/" className={`shrink-0 font-condensed text-xl font-bold tracking-wide ${FOCUS}`}>
          makerundev
        </Link>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-x-5 gap-y-1 sm:gap-x-6">
          <Link
            to="/"
            className={ITEM}
            activeOptions={{ exact: true, includeSearch: false }}
            activeProps={{ "aria-current": "page" }}
          >
            Activities
          </Link>
          <Link
            to="/load"
            className={ITEM}
            activeOptions={{ includeSearch: false }}
            activeProps={{ "aria-current": "page" }}
          >
            Training load
          </Link>
          <Link to="/strava" className={ITEM} activeProps={{ "aria-current": "page" }}>
            Strava
          </Link>
          <Link to="/garmin" className={ITEM} activeProps={{ "aria-current": "page" }}>
            Garmin
          </Link>
          <Link to="/settings" className={ITEM} activeProps={{ "aria-current": "page" }}>
            Settings
          </Link>
        </nav>
      </div>
      <div className="h-[3px] bg-tartan-foreground" />
      <div className="h-1.5 bg-tartan" />
    </header>
  );
}
