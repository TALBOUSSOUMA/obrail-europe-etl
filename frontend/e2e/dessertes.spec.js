import { test, expect } from "@playwright/test";

// Main user flow: search rail services and filter by departure city.
// This is the page an ObRail partner would open first (route "/").
test.describe("Dessertes search", () => {
  test("loads the unfiltered list of rail services on first visit", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Rechercher une desserte" })).toBeVisible();

    // The results table appears once the API has answered - it must
    // contain rows, proving the frontend successfully talked to a real,
    // populated backend (not a mocked/empty response).
    const rows = page.locator("table tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });
    expect(await rows.count()).toBeGreaterThan(0);
  });

  test("filtering by departure city only returns matching rows", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });

    await page.getByLabel("Ville de départ").fill("Paris");
    await page.getByRole("button", { name: "Rechercher" }).click();

    const rows = page.locator("table tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });

    // "Origine" is the 2nd column; every visible row must mention the
    // city just filtered on - the real regression this guards against is
    // the filter silently doing nothing and returning the full, unfiltered list.
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      await expect(rows.nth(i).locator("td").nth(1)).toContainText("Paris", { ignoreCase: true });
    }
  });

  test("resetting filters restores the full result count", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });

    const totalBefore = await page.locator("strong").first().textContent();

    await page.getByLabel("Ville de départ").fill("Paris");
    await page.getByRole("button", { name: "Rechercher" }).click();
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: "Réinitialiser" }).click();
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });

    const totalAfter = await page.locator("strong").first().textContent();
    expect(totalAfter).toBe(totalBefore);
  });
});
