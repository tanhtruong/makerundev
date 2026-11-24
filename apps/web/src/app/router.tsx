import { createRouter, type RouterHistory } from "@tanstack/react-router";

import { routeTree } from "@/app/route-tree.gen";
import { parseSearch, stringifySearch } from "@/lib/search-params";

export function createAppRouter(history?: RouterHistory) {
  return createRouter({
    routeTree,
    history,
    defaultPreload: "intent",
    scrollRestoration: true,
    parseSearch,
    stringifySearch,
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
