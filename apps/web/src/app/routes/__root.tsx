import { createRootRoute, Outlet } from "@tanstack/react-router";

import { AppHeader } from "@/components/layouts/app-header";
import { Page, PageHeading } from "@/components/layouts/page";

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: NotFound,
});

function RootLayout() {
  return (
    <>
      <AppHeader />
      <main>
        <Outlet />
      </main>
    </>
  );
}

function NotFound() {
  return (
    <Page>
      <PageHeading>Page not found</PageHeading>
      <p className="text-muted-foreground">
        There is nothing at this address.{" "}
        <a href="/" className="text-foreground underline">
          Go to your activities
        </a>
        .
      </p>
    </Page>
  );
}
