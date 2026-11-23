import { RouterProvider } from "@tanstack/react-router";
import { useState } from "react";

import { AppProvider } from "@/app/provider";
import { createAppRouter } from "@/app/router";

export function App() {
  const [router] = useState(() => createAppRouter());
  return (
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>
  );
}
