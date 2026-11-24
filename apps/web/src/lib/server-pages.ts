export const SERVER_NAV = [
  { href: "/load", label: "Training load" },
  { href: "/strava", label: "Strava" },
  { href: "/settings", label: "Settings" },
];

export const SERVER_PATHS = ["/api", "/static", "/activities", ...SERVER_NAV.map((page) => page.href)];
