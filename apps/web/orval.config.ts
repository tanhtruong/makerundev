import { defineConfig } from "orval";

export default defineConfig({
  makerundev: {
    input: { target: "../server/openapi.json" },
    output: {
      mode: "tags-split",
      target: "src/lib/api/endpoints",
      schemas: "src/lib/api/model",
      client: "react-query",
      httpClient: "fetch",
      fileExtension: ".gen.ts",
      namingConvention: "kebab-case",
      clean: true,
      indexFiles: false,
      override: {
        mutator: { path: "src/lib/api-client.ts", name: "apiFetch" },
        fetch: { includeHttpResponseReturnType: false },
      },
    },
  },
});
