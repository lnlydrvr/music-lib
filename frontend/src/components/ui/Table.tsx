/* Таблица в обёртке с горизонтальным скроллом (.table-scroll). */
import type { ReactNode } from "react";

export function Table({ headers, children }: { headers: ReactNode[]; children?: ReactNode }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
