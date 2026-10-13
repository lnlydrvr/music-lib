import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { fmtDate, fmtSize } from "../src/lib/format";
import { changeLanguage } from "../src/i18n";

describe("locale-aware formatters", () => {
  it("formats sizes in the active locale", async () => {
    await changeLanguage("en");
    expect(fmtSize(1024 * 1024)).toBe("1.0 MB");

    await changeLanguage("ru");
    expect(fmtSize(1024 * 1024)).toBe("1,0 МБ");
  });

  it("formats a UTC-midnight instant in the selected locale and explicit timezone", () => {
    const formatInTimezone = (timeZone: string, expectedDate: string) => execFileSync(
      process.execPath,
      ["./node_modules/vitest/vitest.mjs", "run", "tests/format-timezone.fixture.test.ts"],
      {
        encoding: "utf8",
        env: { ...process.env, TZ: timeZone, FMT_DATE_EXPECTED: expectedDate },
      },
    );

    expect(formatInTimezone("America/Los_Angeles", "12/31/2023")).toContain("1 passed");
    expect(formatInTimezone("UTC", "01/01/2024")).toContain("1 passed");
  });
});
