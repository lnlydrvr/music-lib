/* Строка трека вместо таблиц. */
import type { HTMLAttributes, ReactNode } from "react";
import clsx from "clsx";
import { Cover } from "./Cover";
import { useTranslation } from "react-i18next";

export interface TrackRowProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  coverSrc?: string;
  title?: ReactNode;
  coverAltTitle?: string;
  sub?: string;
  mainExtra?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}

export function TrackRow({ coverSrc, title, coverAltTitle, sub, mainExtra, meta, actions, className, ...rest }: TrackRowProps) {
  const { t } = useTranslation();
  return (
    <div className={clsx("trackrow", className)} {...rest}>
      <Cover src={coverSrc} size={48} alt={coverAltTitle || (typeof title === "string" ? t("common.cover_alt", { title }) : "")} />
      <div className="t-main">
        <div className="t-copy">
          <div className="t-title">{title || t("common.empty_value")}</div>
          {sub ? <div className="t-sub">{sub}</div> : null}
        </div>
        {mainExtra}
      </div>
      {meta ? <div className="t-meta">{meta}</div> : null}
      <div className="t-actions">{actions}</div>
    </div>
  );
}
