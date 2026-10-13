import i18n from "./index";
import { useTranslation } from "react-i18next";
import { resolveDownloadLabel, resolveRecommendationKey } from "./messages";

i18n.t("nav.home");

// These directives prove the production tsconfig loads the i18next augmentation.
// @ts-expect-error Translation keys must exist in the English source catalog.
i18n.t("nav.not_a_real_key");

const { t } = useTranslation();
t("nav.home");

// @ts-expect-error Translation keys must exist in the English source catalog.
t("nav.not_a_real_key");

resolveDownloadLabel("ytm.download.all_missing", { count: 1 });
resolveRecommendationKey("recommend.apply.like");

// @ts-expect-error Dynamic resolvers accept only their declared key family.
resolveDownloadLabel("nav.home");
// @ts-expect-error Dynamic resolvers accept only their declared key family.
resolveRecommendationKey("api.errors.file_not_found");
