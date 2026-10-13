/* Унифицированные обложки: без src или с ошибкой загрузки → «♫». */
import { useEffect, useState } from "react";
import clsx from "clsx";

export function Cover({
  src,
  size = 48,
  alt = "",
  className,
}: {
  src?: string | null;
  size?: 32 | 40 | 48 | 120 | 200 | number;
  alt?: string;
  className?: string;
}) {
  const [err, setErr] = useState(false);
  useEffect(() => setErr(false), [src]);
  return (
    <div className={clsx("cover", `cover-${size}`, className)}>
      {src && !err ? (
        <img src={src} loading="lazy" alt={alt} onError={() => setErr(true)} />
      ) : (
        <span aria-hidden="true">♫</span>
      )}
    </div>
  );
}
