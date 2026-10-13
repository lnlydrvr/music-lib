/* Модальные диалоги (base-ui Dialog) с Promise-API как в старом SPA:
   confirm/prompt/info/pick + низкоуровневый open() для кастомных модалок.
   Один модал одновременно; Esc/бекдрап закрывают; фокус-трап и возврат
   фокуса — base-ui. */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Dialog } from "@base-ui-components/react/dialog";
import clsx from "clsx";
import { useOverlays } from "../../stores/overlays";
import { useTranslation } from "react-i18next";
import { resolveMessage, type RenderableMessage } from "../../i18n/messages";

export interface DialogAction {
  title: RenderableMessage;
  class?: string;
  /* Async-обработчик: false → модалка остаётся открытой, иначе закрывается
     со значением результата. */
  onClick?: () => unknown | Promise<unknown>;
  /* Значение, которым закроется модалка (может быть функцией — ленивое
     вычисление на момент закрытия). */
  value?: unknown;
  ok?: boolean;
}

export interface OpenDialogOptions {
  title?: RenderableMessage;
  wide?: boolean;
  cls?: string;
  actions?: DialogAction[];
  /* Контент модалки; ctx.close(value) закрывает вручную (кастомные модалки). */
  build?: (ctx: { close: (value?: unknown) => void }) => ReactNode;
}

export interface PickItem {
  label: string;
  sub?: string;
  value?: unknown;
}

export interface DialogsApi {
  confirm(
    message: RenderableMessage,
    opts?: { defaultOk?: boolean; okTitle?: RenderableMessage; cancelTitle?: RenderableMessage },
  ): Promise<boolean>;
  prompt(label: RenderableMessage, opts?: { value?: string; hint?: RenderableMessage }): Promise<string | null>;
  info(title: RenderableMessage, message: RenderableMessage): Promise<true>;
  pick(
    title: string,
    items: PickItem[],
    opts?: { multiple?: boolean; defaultSelected?: Set<number>; okTitle?: RenderableMessage },
  ): Promise<number[] | number | null>;
  open(opts: OpenDialogOptions): Promise<unknown>;
}

const DialogsContext = createContext<DialogsApi | null>(null);

export function useDialogs(): DialogsApi {
  const api = useContext(DialogsContext);
  if (!api) throw new Error("useDialogs вне DialogProvider");
  return api;
}

/* Синглтон смонтированного провайдера — для вне-React вызовов
   (trackEditorDialog/runMetaflow со старыми сигнатурами). */
let sharedApi: DialogsApi | null = null;

export function getDialogs(): DialogsApi {
  if (!sharedApi) throw new Error("DialogProvider не смонтирован");
  return sharedApi;
}

interface ModalRequest extends OpenDialogOptions {
  title: RenderableMessage;
}

function createDialogsApi(
  open: (opts: OpenDialogOptions) => Promise<unknown>,
): DialogsApi {
  return {
    confirm(message, opts = {}) {
      const { defaultOk = true, okTitle = { code: "dialogs.yes" }, cancelTitle = { code: "dialogs.cancel" } } = opts;
      const actions: DialogAction[] = defaultOk
        ? [{ title: okTitle, value: true, ok: true }, { title: cancelTitle, class: "ghost", value: false, ok: true }]
        : [{ title: cancelTitle, class: "ghost", value: false, ok: true }, { title: okTitle, value: true, ok: true }];
      return open({ title: { code: "dialogs.confirm.title" }, build: () => <div>{resolveMessage(message)}</div>, actions }).then((v) => v === true);
    },
    prompt(label, opts = {}) {
      const box = { value: opts.value ?? "" };
      return open({
        title: { code: "dialogs.prompt.title" },
        build: () => <PromptBody label={label} hint={opts.hint} box={box} />,
        actions: [{ title: "OK", value: () => box.value, ok: true }, { title: { code: "dialogs.cancel" }, class: "ghost", value: null, ok: true }],
      }).then((v) => (v === undefined || v === null ? null : String(v)));
    },
    info(title, message) {
      return open({ title, build: () => <div>{resolveMessage(message)}</div>, actions: [{ title: "OK", value: true, ok: true }] }).then(() => true as const);
    },
    pick(title, items, opts = {}) {
      const multiple = !!opts.multiple;
      const box = { selected: new Set<number>(opts.defaultSelected ?? []) };
      return open({
        title,
        build: () => <PickBody items={items} multiple={multiple} box={box} />,
        actions: [{ title: opts.okTitle ?? "OK", value: () => multiple ? [...box.selected] : (box.selected.size ? [...box.selected][0] : null), ok: true }, { title: { code: "dialogs.cancel" }, class: "ghost", value: null, ok: true }],
      }).then((v) => (v === undefined ? null : v) as number[] | number | null);
    },
    open,
  };
}

export function DialogProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [req, setReq] = useState<ModalRequest | null>(null);
  const [loadingIdx, setLoadingIdx] = useState<number | null>(null);
  const resolveRef = useRef<((v: unknown) => void) | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  /* Контейнер портала — как #modal-root в старом SPA: класс .open
     (styles.css: position:fixed; inset:0; z-index:80; flex-центрирование,
     на мобилке — bottom-sheet) навешивается, пока диалог открыт. */
  const portalContainerRef = useRef<HTMLDivElement>(null);

  const open = useCallback((opts: OpenDialogOptions) => {
    return new Promise<unknown>((resolve) => {
      // Один модал одновременно: предыдущий закрывается без значения.
      if (resolveRef.current) resolveRef.current(undefined);
      resolveRef.current = resolve;
      setLoadingIdx(null);
      setReq({ ...opts, title: opts.title ?? "" });
    });
  }, []);

  const settle = useCallback((value: unknown) => {
    const r = resolveRef.current;
    if (!r) return;
    resolveRef.current = null;
    setLoadingIdx(null);
    setReq(null);
    // value может быть функцией (ленивое вычисление).
    r(typeof value === "function" ? (value as () => unknown)() : value);
  }, []);

  const runAction = useCallback(
    async (idx: number, a: DialogAction) => {
      if (!a.onClick) {
        settle(a.value);
        return;
      }
      setLoadingIdx(idx);
      try {
        const r = await a.onClick();
        if (r !== false) settle(r);
      } finally {
        setLoadingIdx(null);
      }
    },
    [settle],
  );

  const apiRef = useRef<DialogsApi | null>(null);
  if (!apiRef.current) {
    apiRef.current = createDialogsApi(open);
  }
  const api = apiRef.current;

  // Счётчик открытых диалогов — сигнал для подавления хоткеев (не DOM-классы).
  useEffect(() => {
    if (!req) return;
    const { openDialog, closeDialog } = useOverlays.getState();
    openDialog();
    return () => closeDialog();
  }, [req]);

  // Регистрация синглтона (useDialogs остаётся основным путём в React-дереве).
  useEffect(() => {
    sharedApi = api;
    return () => {
      if (sharedApi === api) sharedApi = null;
    };
  }, [api]);

  return (
    <DialogsContext.Provider value={api}>
      {children}
      {/* Обёртка модалок легаси: пока диалог открыт — класс .open (fixed,
          затемнение, центрирование); без него .modal остаётся в потоке
          документа и «уезжает» с экраном. */}
      <div id="modal-root" ref={portalContainerRef} className={clsx(req && "open")} />
      <Dialog.Root open={req !== null} onOpenChange={(o) => { if (!o) settle(undefined); }}>
        <Dialog.Portal container={portalContainerRef}>
          <Dialog.Backdrop className="modal-backdrop" />
          <Dialog.Popup
            ref={popupRef}
            className={clsx("modal", req?.wide && "wide", req?.cls)}
            // Фокус: первое поле ввода → первая кнопка футера → «×».
            initialFocus={() =>
              popupRef.current?.querySelector<HTMLElement>("input, select") ||
              footerRef.current?.querySelector<HTMLElement>("button") ||
              closeRef.current ||
              true
            }
          >
            <Dialog.Title render={<h3 />}>{req?.title === undefined ? "" : resolveMessage(req.title)}</Dialog.Title>
            <button
              ref={closeRef}
              className="close ghost"
              type="button"
              aria-label={t("dialogs.close_aria")}
              onClick={() => settle(undefined)}
            >
              ×
            </button>
            <div className="modal-body">{req?.build?.({ close: settle })}</div>
            <div className="modal-actions" ref={footerRef}>
              {req?.actions?.map((a, i) => (
                <button
                  key={i}
                  type="button"
                  className={clsx(a.class || "", loadingIdx === i && "is-loading")}
                  disabled={loadingIdx === i}
                  onClick={() => void runAction(i, a)}
                >
                  {resolveMessage(a.title)}
                </button>
              ))}
            </div>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
    </DialogsContext.Provider>
  );
}

/* --- prompt: поле ввода пишет значение в box (ленивое value кнопки OK) --- */

function PromptBody({
  label,
  hint,
  box,
}: {
  label: RenderableMessage;
  hint?: RenderableMessage;
  box: { value: string };
}) {
  return (
    <>
      <label className="muted">{resolveMessage(label)}</label>
      <input
        type="text"
        defaultValue={box.value}
        style={{ width: "100%" }}
        autoFocus
        onChange={(e) => {
          box.value = e.target.value;
        }}
        onKeyDown={(e) => {
          // Enter в поле = OK (в старом коде Enter молчал; удобство без риска).
          if (e.key === "Enter") {
            e.preventDefault();
            (e.currentTarget.closest(".modal")?.querySelector<HTMLButtonElement>(".modal-actions button"))?.click();
          }
        }}
      />
      {hint ? (
        <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
          {resolveMessage(hint)}
        </div>
      ) : null}
    </>
  );
}

/* --- pick: список radio/checkbox, состояние в box --- */

function PickBody({
  items,
  multiple,
  box,
}: {
  items: PickItem[];
  multiple: boolean;
  box: { selected: Set<number> };
}) {
  const [, force] = useState(0);
  return (
    <>
      {items.map((item, i) => (
        <label key={i} className="pick-row">
          <input
            type={multiple ? "checkbox" : "radio"}
            name="pick"
            checked={box.selected.has(i)}
            onChange={() => {
              if (!multiple) box.selected = new Set([i]);
              else if (box.selected.has(i)) box.selected.delete(i);
              else box.selected.add(i);
              force((n) => n + 1);
            }}
          />
          <span className="pick-label">{item.label}</span>
          {item.sub ? <span className="pick-sub">{item.sub}</span> : null}
        </label>
      ))}
    </>
  );
}
