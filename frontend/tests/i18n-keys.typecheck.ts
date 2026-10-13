import i18n from "../src/i18n";

i18n.t("nav.home");

// This directive must remain necessary: an unknown catalog key is a type error.
// @ts-expect-error Translation keys must exist in the English source catalog.
i18n.t("nav.not_a_real_key");
