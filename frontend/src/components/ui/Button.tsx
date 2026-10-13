/* Кнопка на cva с вариантами существующих классов styles.css. */
import type { ButtonHTMLAttributes } from "react";
import clsx from "clsx";
import { cva, type VariantProps } from "class-variance-authority";

const button = cva("", {
  variants: {
    variant: {
      primary: "",
      big: "btn-big",
      small: "small-btn",
      ghost: "ghost",
      smallGhost: "small-btn ghost",
      icon: "iconbtn",
      iconGhost: "ghost iconbtn",
    },
    danger: { true: "danger", false: "" },
  },
  defaultVariants: { variant: "primary", danger: false },
});

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export function Button({ variant, danger, className, type = "button", ...rest }: ButtonProps) {
  return <button type={type} className={clsx(button({ variant, danger }), className)} {...rest} />;
}
