/* Общие детали карточек настроек: свитчер, поле, карточка, выбор каталога
   (нативный диалог + фолбэк-дерево). */
import { useEffect, useState, type ReactNode } from "react";
import { get, post } from "../../lib/api";
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { Spinner } from "../../components/ui/Spinner";
import { useTranslation } from "react-i18next";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../../i18n/messages";

/* iOS-стиль свитчер вместо чекбокса. */
export function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <span className="switch">
      <input type="checkbox" className="switch-input" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="switch-track" />
    </span>
  );
}

export function SwitchRow({ text, checked, onChange }: { text: ReactNode; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="set-switch-row">
      <span>{text}</span>
      <Switch checked={checked} onChange={onChange} />
    </label>
  );
}

export function Field({ label, children, hint = "" }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="set-field" style={{ display: "block" }}>
      <div className="set-label">{label}</div>
      {children}
      {hint ? <div className="set-hint">{hint}</div> : null}
    </label>
  );
}

export function Card({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <div className="panel set-card">
      <h2>{title}</h2>
      {sub ? <div className="comment set-sub">{sub}</div> : null}
      {children}
    </div>
  );
}

export function Details({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="set-details">
      <summary>{title}</summary>
      <div className="set-details-body">{children}</div>
    </details>
  );
}

/* Выбор пути: сначала нативный системный диалог (Finder/проводник), при
   ошибке/отсутствии — кастомная модалка с деревом папок. */
export async function openBrowse(current: string, kind: "folder" | "file"): Promise<string | null> {
  try {
    const res = await post<{ path: string | null }>("/api/fs/pick", { kind, start: current || "" });
    return res.path || null; // отмена
  } catch {
    /* система без диалога (Linux без zenity и т.п.) — модалка */
  }
  const picked = await getDialogs().open({
    title: { code: "settings.browse.folder_title" },
    build: ({ close }) => <BrowseBody startDir={current} onPick={(p) => close(p)} />,
    actions: [{ title: { code: "dialogs.close" }, class: "ghost", value: null, ok: true }],
  });
  return (picked as string | null) ?? null;
}

function BrowseBody({ startDir, onPick }: { startDir: string; onPick: (path: string) => void }) {
  const { t } = useTranslation();
  const [dir, setDir] = useState(startDir);
  const [data, setData] = useState<{ parent?: string; dirs: { name: string; path: string }[] } | null>(null);
  const [error, setError] = useState<RenderableMessage>("");

  useEffect(() => {
    let alive = true;
    get<{ parent?: string; dirs: { name: string; path: string }[] }>("/api/fs/browse", { dir })
      .then((d) => {
        if (alive) {
          setData(d);
          setError("");
        }
      })
      .catch((e) => alive && setError(asRenderableMessage(e)));
    return () => {
      alive = false;
    };
  }, [dir]);

  if (error) return <div className="panel" style={{ borderColor: "var(--danger)" }}>{t("settings.browse.error", { reason: resolveMessage(error) })}</div>;
  if (!data) return <Spinner text={t("settings.browse.loading")} />;
  return (
    <div className="set-browse">
      <div className="row" style={{ marginBottom: 8 }}>
        {t("settings.browse.folder")} <b>{dir || "~"}</b>
      </div>
      {data.parent ? (
        <div className="pick-row" style={{ cursor: "pointer" }} onClick={() => setDir(data.parent!)}>
          <b>↑ ..</b>
        </div>
      ) : null}
      {data.dirs.map((d) => (
        <div key={d.path} className="pick-row" style={{ cursor: "pointer" }} onClick={() => onPick(d.path)} data-pick={d.path}>
          <span>{d.name}</span>
          <span className="muted" style={{ fontSize: 12, marginInlineStart: 8 }}>{d.path}</span>
        </div>
      ))}
    </div>
  );
}
