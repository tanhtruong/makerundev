export const SERVER_NAV = [{ href: "/settings", label: "Settings" }];

export const SERVER_PATHS = [
  "/api",
  "/static",
  "/activities",
  "/strava/connect",
  "/strava/callback",
  ...SERVER_NAV.map((page) => page.href),
];
