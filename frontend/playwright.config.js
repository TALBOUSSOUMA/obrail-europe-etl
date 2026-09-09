import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the already-running Docker Compose stack
// (frontend + api + db), not a separately-started dev server: this way
// we're testing exactly what an evaluator would run with
// `docker compose up --build`, not a dev-only code path.
//
// Prerequisite before running `npm run test:e2e`:
//   docker compose up -d
//   (and, once) POSTGRES_PORT=5433 python etl/run_pipeline.py
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:8081",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
