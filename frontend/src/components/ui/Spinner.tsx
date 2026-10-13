/* Строковая загрузка-приглушение. */
import { useTranslation } from "react-i18next";

export function Spinner({ text }: { text?: string }) {
  const { t } = useTranslation();
  return <div className="empty">{text ?? t("common.loading")}</div>;
}
