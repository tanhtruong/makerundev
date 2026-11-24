import js from "@eslint/js";
import checkFile from "eslint-plugin-check-file";
import importX from "eslint-plugin-import-x";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

const FEATURES = ["activities", "training-load", "settings", "strava", "garmin"];
const SHARED = ["./src/components", "./src/hooks", "./src/lib", "./src/testing", "./src/types", "./src/utils"];

export default tseslint.config(
  { ignores: ["dist", "playwright-report", "test-results", "src/lib/api/**", "src/app/route-tree.gen.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    plugins: {
      "import-x": importX,
      "check-file": checkFile,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    settings: { "import-x/resolver": { typescript: true } },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": "error",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "@typescript-eslint/only-throw-error": [
        "error",
        { allow: [{ from: "package", package: "@tanstack/router-core", name: "NotFoundError" }] },
      ],
      "no-restricted-imports": [
        "error",
        { patterns: [{ group: ["../*"], message: "Import with the @/ alias instead of a parent path." }] },
      ],
      "import-x/no-cycle": "error",
      "import-x/no-restricted-paths": [
        "error",
        {
          zones: [
            ...FEATURES.map((feature) => ({
              target: `./src/features/${feature}`,
              from: "./src/features",
              except: [`./${feature}`],
              message: "Features do not import from each other; move shared code to src/components or src/lib.",
            })),
            { target: "./src/features", from: "./src/app", message: "Features do not import the app." },
            {
              target: SHARED,
              from: ["./src/features", "./src/app"],
              message: "Shared code does not import features or the app.",
            },
          ],
        },
      ],
      "check-file/filename-naming-convention": [
        "error",
        { "src/**/*.{ts,tsx}": "KEBAB_CASE" },
        { ignoreMiddleExtensions: true },
      ],
      "check-file/folder-naming-convention": ["error", { "src/**/": "KEBAB_CASE" }],
      "check-file/filename-blocklist": [
        "error",
        { "src/{components,features,lib,hooks,testing,utils}/**/index.{ts,tsx}": "*.{ts,tsx} named for what it holds" },
      ],
    },
  },
  {
    files: ["src/app/routes/**"],
    rules: {
      "check-file/filename-naming-convention": "off",
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: ["*.config.ts", "e2e/**"],
    languageOptions: { globals: globals.node },
  },
);
