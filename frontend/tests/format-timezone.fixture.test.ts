import { expect, it } from "vitest";
import { changeLanguage } from "../src/i18n";
import { fmtDate } from "../src/lib/format";

const timestamp = 1704067200; // 2024-01-01T00:00:00Z
const expectedDate = process.env.FMT_DATE_EXPECTED;

const timezoneFixture = expectedDate ? it : it.skip;

timezoneFixture("formats through fmtDate in the process local timezone", async () => {
  // Exercise the application locale singleton rather than constructing a
  // parallel Intl formatter in this subprocess.
  await changeLanguage("en");
  expect(fmtDate(timestamp)).toBe(expectedDate!);
});
