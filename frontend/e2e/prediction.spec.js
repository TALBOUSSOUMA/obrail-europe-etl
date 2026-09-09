import { test, expect } from "@playwright/test";

// Main user flow: fill in a hypothetical rail service and get a
// prediction back from the ML model, through the real backend
// (api/main.py -> ml/predict.py -> the actual trained joblib model,
// not a stub) - this is the demo scenario for the ML integration.
test("estimating a weekly frequency returns a plausible result", async ({ page }) => {
  await page.goto("/prediction");

  await expect(page.getByRole("heading", { name: "Estimer une fréquence hebdomadaire" })).toBeVisible();

  await page.getByLabel("Distance (km)").fill("850");
  await page.getByLabel("Durée (heures)").fill("6.5");
  await page.getByLabel("Type de train").fill("TGV inOui");
  await page.getByLabel("Service").selectOption("Jour");

  // The operator and country dropdowns are only populated once /operateurs
  // and /pays have answered - wait for a real value before submitting, or
  // the form's native "required" validation blocks the click.
  await expect(page.getByLabel("Opérateur")).not.toHaveValue("");
  await expect(page.getByLabel("Pays de départ")).toHaveValue("FR");
  await expect(page.getByLabel("Pays d'arrivée")).toHaveValue("FR");

  await page.getByRole("button", { name: "Estimer" }).click();

  // Targeting the specific <strong> (not the surrounding <p>, which also
  // contains this text) to avoid Playwright's strict-mode ambiguity.
  const result = page.locator(".card strong");
  await expect(result).toBeVisible({ timeout: 10_000 });

  // The predicted frequency must be a real, in-range number (0-7 days/week),
  // not an error message or a stub value - this is what a client would
  // actually check when trusting this feature.
  const text = await result.textContent();
  const value = parseFloat(text);
  expect(value).toBeGreaterThanOrEqual(0);
  expect(value).toBeLessThanOrEqual(7);
});
