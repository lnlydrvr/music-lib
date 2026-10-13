/* Унифицированный переключатель сегментов (aria-pressed). */
import clsx from "clsx";

export interface SegOption<T extends string> {
  value: T;
  label: string;
}

export function SegControl<T extends string>({
  options,
  current,
  onChange,
  extraClass = "",
  label,
}: {
  options: [T, string][] | SegOption<T>[];
  current: T;
  onChange: (v: T) => void;
  extraClass?: string;
  /* aria-label группы (например «Источник поиска»). */
  label?: string;
}) {
  const normalized: SegOption<T>[] = options.map((o) =>
    Array.isArray(o) ? { value: o[0], label: o[1] } : o,
  );
  return (
    <div className={clsx("seg", extraClass)} role="group" aria-label={label}>
      {normalized.map((o) => {
        const on = o.value === current;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            className={on ? "active" : undefined}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
