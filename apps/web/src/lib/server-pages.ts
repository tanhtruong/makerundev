export const SERVER_NAV = [
  { href: "/strava", label: "Strava" },
  { href: "/settings", label: "Settings" },
];

export const SERVER_PATHS = ["/api", "/static", "/activities", ...SERVER_NAV.map((page) => page.href)];
