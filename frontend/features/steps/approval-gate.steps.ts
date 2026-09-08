/**
 * Step definitions for approval-gate.feature.
 *
 * Gherkin runs on the Playwright runner via playwright-bdd, so the feature files
 * are a readable surface over the same suite — parallel workers, webServer boot,
 * traces and the `page` fixture all still apply. There is no second browser
 * lifecycle to maintain and no assertion duplicated between the two.
 *
 * /process is stubbed: it is the only LLM call (real money, nondeterministic
 * output). Everything AFTER the gate — /approve, the conflict re-screen, the CSV
 * write — runs against the live backend, because that is what is under test.
 */
import { expect } from "@playwright/test";
import { test as base, createBdd } from "playwright-bdd";
import { readFileSync } from "node:fs";
import path from "node:path";

// A name the firm has actually opposed, read from the seeded history rather than
// hardcoded, so re-seeding the matter database cannot quietly void these tests.
// A verbatim opposing party scores 1.0, comfortably over the CONFLICT threshold.
const HISTORY = JSON.parse(
  readFileSync(path.join(__dirname, "../../../backend/samples/matter_history.json"), "utf-8"),
) as Array<{ client_name: string; opposing_party: string }>;
const ADVERSE_NAME = HISTORY[0].opposing_party;

/** A processed record as /process would return it: screened CLEAR, nobody adverse. */
function cleanRecord() {
  return {
    // Unique per run: /approve is idempotent by intake_id, so a fixed id would
    // come back "Already saved" on the second run and fail for the wrong reason.
    intake_id: `LF-bdd${Date.now().toString(36)}`,
    received_at: new Date().toISOString(),
    status: "needs_review",
    client_name: "Nobody Whatsoever",
    client_email: "nobody@example.com",
    client_phone: "(415) 555-0100",
    opposing_party: null,
    matter_type: "Employment",
    matter_type_confidence: "high",
    jurisdiction: "California",
    key_dates: [],
    summary: "Synthetic intake used by the end-to-end suite.",
    missing_fields: ["opposing_party"],
    draft_reply: "Thank you for getting in touch.",
    conflict: {
      status: "CLEAR",
      matches: [],
      returning_client_matters: [],
      checked_against: HISTORY.length,
      limitations: ["No opposing party was identified in the intake."],
    },
  };
}

// Per-scenario state. A fixture rather than a module-level variable, so scenarios
// running in parallel workers cannot see each other's writes.
export const test = base.extend<{ crmWrites: string[] }>({
  crmWrites: async ({}, use) => {
    await use([]);
  },
});

const { Given, When, Then } = createBdd(test);

Given('an intake has been processed and screened {string}', async ({ page, crmWrites }, verdict: string) => {
  // Registered before anything loads, so a premature write cannot slip past.
  page.on("request", (r) => {
    if (r.url().endsWith("/approve")) crmWrites.push(r.method());
  });
  await page.route(/\/process$/, (route) => route.fulfill({ json: { record: cleanRecord() } }));
  await page.goto("/");
  await page.getByPlaceholder(/Paste the client's email/i).fill("Synthetic intake text.");
  await page.getByRole("button", { name: /Process intake/i }).click();
  await expect(page.getByText(verdict)).toBeVisible();
});

When('the reviewer corrects the client name to a party the firm has opposed', async ({ page }) => {
  // The correction the UI exists to invite — the field's own help text says it
  // drives the conflict screen. The verdict on screen predates it.
  await page.getByLabel("Client name").fill(ADVERSE_NAME);
});

When('the reviewer edits the intake without approving it', async ({ page }) => {
  await page.getByLabel("Client name").fill("Edited Before Approval");
  await page.getByLabel("Jurisdiction").fill("Oregon");
});

When('the reviewer approves the intake', async ({ page }) => {
  await page.getByRole("button", { name: /Approve & save to CRM/i }).click();
});

Then('the verdict on screen still reads {string}', async ({ page }, verdict: string) => {
  await expect(page.getByText(verdict)).toBeVisible();
});

Then('the filed record reads {string}', async ({ page }, verdict: string) => {
  // The verdict the CRM received. If the server had trusted the posted CLEAR,
  // this record would be filed clean against a party the firm has opposed.
  await expect(page.getByText(verdict)).toBeVisible();
  await expect(page.getByText("No conflict found")).toHaveCount(0);
});

Then('nothing has been written to the CRM', async ({ crmWrites }) => {
  expect(crmWrites, "processing or editing must not persist anything").toEqual([]);
});

Then('the record is confirmed saved to the CRM', async ({ page }) => {
  await expect(page.getByText(/Approved & saved|Already saved/)).toBeVisible();
});

Then('exactly one write reached the CRM', async ({ crmWrites }) => {
  expect(crmWrites).toEqual(["POST"]);
});

Then('the reply can be copied', async ({ page }) => {
  await expect(page.getByRole("button", { name: /Copy reply/i })).toBeVisible();
});

Then('there is no way to send it', async ({ page }) => {
  // The post-approval panel is where a "Send" button would land if anyone added
  // one. No-auto-send is a stated product guarantee, so it gets an assertion
  // rather than a code comment a later refactor can quietly contradict.
  await expect(page.getByRole("button", { name: /send/i })).toHaveCount(0);
});
