// apps/web/src/app.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { IndexRoute } from "@/routes/index";

export function App() {
  const [client] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={client}>
      <IndexRoute />
    </QueryClientProvider>
  );
}
