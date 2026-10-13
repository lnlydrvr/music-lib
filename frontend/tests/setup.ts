import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import i18n from "../src/i18n";

afterEach(() => {
  cleanup();
});

beforeEach(async () => {
  await i18n.changeLanguage("ru");
  document.documentElement.lang = "ru";
});
