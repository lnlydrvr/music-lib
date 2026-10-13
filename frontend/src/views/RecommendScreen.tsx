/* Рекомендации — персональное радио YouTube Music по сидам из библиотеки:
   карточки со свайпами/кнопками, принятые треки и дизлайки уходят в аккаунт.
   Генерация стримится: каждый обработанный сид отдаёт накопительный snapshot,
   карточки показываются сразу и добираются в хвост (append-only merge). */
import { useCallback, useEffect, useRef, useState } from "react";
import { get, post } from "../lib/api";
import { toast } from "../lib/toast";
import { JobError, startJob } from "../lib/jobs";
import type { RecommendationItem } from "../lib/jobs";
import type { RecommendationKey, RenderableMessage } from "../i18n/messages";
import { asRenderableMessage, resolveMessage, resolveRecommendationKey } from "../i18n/messages";
import { useTranslation } from "react-i18next";
import { usePlayer } from "../stores/player";
import { anyOverlayOpen } from "../stores/overlays";
import { ProgressBar } from "../components/ui/ProgressBar";
import { EmptyState } from "../components/ui/EmptyState";

const SVG_PLAY =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>';

/* Фазы экрана: loading — задача запущена, карточек ещё нет; streaming — первый
   snapshot выдан, сиды продолжают обрабатываться; ready — финальный DTO;
   error — задача упала (частичная очередь сохраняется). */
type Phase = "loading" | "streaming" | "ready" | "error";
type RecommendationActionKey = Extract<RecommendationKey, `recommend.apply.${string}`>;

interface GenResult {
  items?: RecommendationItem[];
  seeds?: number;
  library_count?: number;
  total?: number;
}

/* Транслит кириллицы → латиница — зеркало _CYR_TO_LAT бэкенда, чтобы
   fallback-ключ совпадал с нормой сервера (ytmusic.norm). */
const CYR_TO_LAT: Record<string, string> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z",
  и: "i", й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r",
  с: "s", т: "t", у: "u", ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh",
  щ: "shch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
};

/* Нормализация как ytmusic.norm: lowercase → транслит → только буквы/цифры
   (пробелы/пунктуация убираются, склеиваются без разделителей). */
function normKey(s: string): string {
  return s
    .normalize("NFC")
    .toLowerCase()
    .replace(/[а-яё]/g, (ch) => CYR_TO_LAT[ch] ?? "")
    .replace(/[^\p{L}\p{N}]/gu, "");
}

/* Фичи не меняют песню — зеркало norm_title бэкенда: «Song» и «Song (feat.
   Guest)» — один трек. В скобках допустим ещё и with; инлайн-with не режем
   («I Wanna Dance with Somebody» — часть названия). */
const FEATURE_PAREN_RE = /\([^)]*(?:feat\.?|ft\.?|featuring|with)\b[^)]*\)/gi;
const FEATURE_INLINE_RE = /(?:feat\.?|ft\.?|featuring)\b/i;

function normTitleKey(s: string): string {
  let t = s.normalize("NFC").replace(FEATURE_PAREN_RE, "");
  const i = FEATURE_INLINE_RE.exec(t);
  if (i) t = t.slice(0, i.index).replace(/[ ,.;:\-–—(|/&]+$/u, "");
  return normKey(t);
}

/* Ключ дедупа: непустой video_id → ТОЛЬКО v:<id>; нормализованная пара
   artist/title (norm + norm_title бэкенда) — исключительно fallback при
   отсутствии video_id. Разные video_id при одинаковых artist/title —
   разные треки, обе карточки остаются. */
function recKey(item: Pick<RecommendationItem, "video_id" | "artist" | "title">): string {
  const vid = (item.video_id || "").trim();
  if (vid) return `v:${vid}`;
  return `n:${normKey(item.artist)}|${normTitleKey(item.title)}`;
}

/* Тексты действия принятия — по настройке ytm_feedback_action. */
function applyTexts(mode: string): {
  label: RecommendationActionKey;
  overlay: RecommendationActionKey;
  toastText: RecommendationActionKey;
  hint: "recommend.apply.library_hint" | "recommend.apply.like_hint";
} {
  if (mode === "library") {
    return {
      label: "recommend.apply.library",
      overlay: "recommend.apply.library_overlay",
      toastText: "recommend.apply.library_done",
      hint: "recommend.apply.library_hint",
    };
  }
  return { label: "recommend.apply.like", overlay: "recommend.apply.like_overlay", toastText: "recommend.apply.like_done", hint: "recommend.apply.like_hint" };
}

export default function RecommendScreen() {
  const { t } = useTranslation();
  const [queue, setQueue] = useState<RecommendationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [info, setInfo] = useState<{ library: number; total: number } | null>(null);
  const [progress, setProgress] = useState<{ pct: number; msg: RenderableMessage } | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<RenderableMessage | null>(null);
  const [needsConnection, setNeedsConnection] = useState(false);
  const [apply, setApply] = useState(applyTexts("like"));
  /* Pending привязан к сессии: хранит ID сессии, чей action-POST в полёте
     (null — свободно). Висящий POST старой сессии не блокирует карточки
     новой; поздний finally старой сессии не сбрасывает pending новой. */
  const pendingRef = useRef<number | null>(null);
  /* Session guard: поздние callbacks/финал прежнего запуска (StrictMode
     double-mount, повторный «Обновить рекомендации») не трогают новую сессию. */
  const sessionRef = useRef(0);
  const seenRef = useRef<Set<string>>(new Set());
  const handledRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    get<Record<string, unknown>>("/api/settings")
      .then((st) => setApply(applyTexts(String(st.ytm_feedback_action || "like"))))
      .catch(() => {
        /* нет настроек — дефолт (лайк) */
      });
  }, []);

  /* Append-only merge: в хвост очереди попадают только элементы, чьего ключа
     ещё нет в seen/handled; ключ пишем и считаем вне setState (updater
     остаётся чистым — StrictMode может вызвать его дважды). Возвращает число
     добавленных карточек. */
  const mergeItems = useCallback((incoming: RecommendationItem[]): number => {
    const fresh: RecommendationItem[] = [];
    for (const it of incoming) {
      const key = recKey(it);
      if (seenRef.current.has(key) || handledRef.current.has(key)) continue;
      seenRef.current.add(key);
      fresh.push(it);
    }
    if (fresh.length) setQueue((q) => [...q, ...fresh]);
    return fresh.length;
  }, []);

  const generate = useCallback(async () => {
    const session = ++sessionRef.current;
    const alive = () => session === sessionRef.current;
    seenRef.current = new Set();
    handledRef.current = new Set();
    /* Новый запуск сбрасывает pending: action-POST прежней сессии, ещё в
       полёте, больше ничего не блокирует (его finally чистит только свой). */
    pendingRef.current = null;
    setError(null);
    setNeedsConnection(false);
    setQueue([]);
    setTotal(0);
    setInfo(null);
    setPhase("loading");
    setProgress({ pct: 0, msg: { code: "recommend.seeds.collecting" } });
    try {
      const res = await startJob<GenResult>(
        "/api/recommend/generate",
        {},
        {
          onProgress: (d) => {
            /* recommendations-события полностью разбирает onRecommendations. */
            if (!alive() || (d as { kind?: string }).kind === "recommendations") return;
            setProgress({ pct: d.percent ?? 0, msg: d.message ?? d.msg ?? "" });
          },
          onRecommendations: (d) => {
            if (!alive()) return;
            const added = mergeItems(d.items);
            setTotal((t) => t + added);
            setInfo({ library: d.library_count, total: d.total });
            setPhase("streaming");
            const pct = d.seed_count > 0 ? Math.round((d.seed_index / d.seed_count) * 100) : 0;
            setProgress({ pct, msg: (d.message ?? d.msg) || { code: "jobs.recommend.seed", params: { index: d.seed_index, total: d.seed_count } } });
          },
        },
      );
      if (!alive()) return;
      /* Финальный DTO проходит через тот же merge — идемпотентно к последнему
         snapshot, обработанные/виденные карточки не возвращаются. */
      const added = mergeItems(res.items || []);
      setTotal((t) => t + added);
      setInfo({ library: res.library_count || 0, total: res.total || 0 });
      setPhase("ready");
    } catch (e) {
      if (!alive()) return;
      /* Ошибка сохраняет частичную очередь — выданные карточки остаются. */
      const renderableMessage = asRenderableMessage(e);
      setError(renderableMessage);
      setNeedsConnection(
        (e instanceof JobError
          && typeof e.renderableMessage !== "string"
          && e.renderableMessage.code === "api.errors.ytm_connection_required")
        || (typeof renderableMessage !== "string"
          && renderableMessage.code === "api.errors.ytm_connection_required"),
      );
      setPhase("error");
    } finally {
      if (alive()) setProgress(null);
    }
  }, [mergeItems]);

  useEffect(() => {
    void generate();
    /* Unmount (в т.ч. StrictMode remount) инвалидирует сессию: коллбэки
       незавершённого запуска не обновляют state/refs после размонтирования. */
    return () => {
      sessionRef.current++;
    };
  }, [generate]);

  /* Обработанное (лайк/дизлайк/пропуск) отмечаем ДО будущих merge — поздние
     snapshot/финал не вернут карточку в очередь. Сессия фиксируется на момент
     действия: поздний apply/dislike старой сессии (POST резолвнулся уже после
     перезапуска) не трогает handled/queue новой. */
  const advance = useCallback((item: RecommendationItem, session = sessionRef.current) => {
    if (session !== sessionRef.current) return;
    handledRef.current.add(recKey(item));
    setQueue((q) => q.filter((x) => x !== item));
  }, []);

  const action = useCallback(
    async (item: RecommendationItem, which: "apply" | "dislike") => {
      /* Блокируем только действие ТОЙ ЖЕ сессии: pending старой сессии
         (POST пережил перезапуск генерации) новую карточку не блокирует. */
      if (pendingRef.current === sessionRef.current) return;
      const session = sessionRef.current;
      pendingRef.current = session;
      try {
        const body = { artist: item.artist, title: item.title };
        if (which === "apply") {
          await post("/api/recommend/apply", body);
          toast(resolveRecommendationKey(apply.toastText));
        } else {
          await post("/api/recommend/dislike", body);
          toast(t("recommend.dislike_done"));
        }
        advance(item, session);
      } catch (e) {
        toast(asRenderableMessage(e), "error");
      } finally {
        /* Чистим только СВОЙ pending: за время полёта POST могла начаться
           новая сессия и выставить свой pending — не сбиваем его. */
        if (pendingRef.current === session) pendingRef.current = null;
      }
    },
    [advance, apply, t],
  );

  /* Стрелки ←/→ вне инпутов и диалогов. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName || "";
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag) || anyOverlayOpen()) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (queue[0]) void action(queue[0], "dislike");
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        if (queue[0]) void action(queue[0], "apply");
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [queue, action]);

  const item = queue[0];
  const busy = phase === "loading" || phase === "streaming";
  const needConnect = needsConnection;

  return (
    <>
      <h1>{t("recommend.title")}</h1>
      <div className="comment">{t("recommend.subtitle")}</div>
      <div className="muted" style={{ marginTop: 8 }}>{info ? t("recommend.info", info) : ""}</div>

      {progress && busy ? (
        <div className="panel" style={{ marginBottom: 12 }}>
          <ProgressBar pct={progress.pct} msg={progress.msg} />
        </div>
      ) : null}

      {error ? (
        needConnect && !item ? (
          <EmptyState
            art="♫"
            title={t("recommend.disconnected")}
            sub={resolveMessage(error)}
            action={
              <button className="btn-big" type="button" onClick={() => { location.hash = "#/settings"; }}>
                {t("recommend.open_settings")}
              </button>
            }
          />
        ) : (
          /* Ошибка при частичной очереди: текст сверху, карточки остаются. */
          <div className="empty">{resolveMessage(error)}</div>
        )
      ) : null}

      {/* Пустая очередь вне loading: стриминг ещё идёт (карточки подтянутся)
          или рекомендации исчерпаны — в обоих случаях можно перезапустить. */}
      {!item && !error && phase !== "loading" ? (
        <div className="rec-empty">
          <h3>{phase === "streaming" ? t("recommend.streaming.title") : t("recommend.empty.title")}</h3>
          <div className="muted">
            {phase === "streaming" ? t("recommend.streaming.hint") : t("recommend.empty.hint")}
          </div>
          <button className="btn-big" type="button" style={{ marginTop: 12 }} onClick={() => { void generate(); }}>
            {t("recommend.refresh")}
          </button>
        </div>
      ) : null}

      {item ? (
        <>
          <RecStack item={item} apply={apply} onAction={action} onSkip={() => advance(item)} pending={pendingRef} session={sessionRef} />
          <div className="rec-counter">{t("recommend.counter", { current: total - queue.length + 1, total })}</div>
          <div className="rec-hint">
            {t("recommend.hint", {
               dislike: resolveRecommendationKey(typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches ? "recommend.dislike_swipe" : "recommend.dislike_key"),
               apply: resolveRecommendationKey(
                 typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches
                   ? apply.hint
                   : apply.hint === "recommend.apply.library_hint"
                     ? "recommend.apply.library_hint_key"
                     : "recommend.apply.like_hint_key",
               ),
            })}
          </div>
        </>
      ) : null}
    </>
  );
}

/* Карточка рекомендации: свайп/драг с оверлеями, «Слушать», действия. */
function RecStack({
  item,
  apply,
  onAction,
  onSkip,
  pending,
  session,
}: {
  item: RecommendationItem;
  apply: ReturnType<typeof applyTexts>;
  onAction: (item: RecommendationItem, which: "apply" | "dislike") => void;
  onSkip: () => void;
  /* Ref-ы читаются в момент события: pending.current — ID сессии, чей POST
     в полёте; драг блокируется, только если он принадлежит текущей сессии. */
  pending: { current: number | null };
  session: { current: number };
}) {
  const { t } = useTranslation();
  const cardRef = useRef<HTMLDivElement>(null);
  const ovYesRef = useRef<HTMLDivElement>(null);
  const ovNoRef = useRef<HTMLDivElement>(null);
  const drag = useRef({ on: false, sx: 0, dx: 0 });
  const [coverErr, setCoverErr] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);

  const isInteractive = (t: EventTarget | null): boolean => {
    for (let n = t as HTMLElement | null; n && n !== cardRef.current; n = n.parentElement) {
      if (n.tagName === "BUTTON" || n.tagName === "A" || n.tagName === "INPUT") return true;
    }
    return false;
  };

  const clearDrag = () => {
    const card = cardRef.current;
    if (!card) return;
    card.classList.remove("drag-right", "drag-left");
    card.style.transform = "";
    if (ovYesRef.current) ovYesRef.current.style.opacity = "0";
    if (ovNoRef.current) ovNoRef.current.style.opacity = "0";
  };

  const move = (x: number) => {
    const card = cardRef.current;
    if (!card || !drag.current.on) return;
    const dx = x - drag.current.sx;
    drag.current.dx = dx;
    card.style.transform = `translateX(${dx}px) rotate(${dx * 0.08}deg)`;
    card.classList.toggle("drag-right", dx > 24);
    card.classList.toggle("drag-left", dx < -24);
    const t = Math.min(Math.abs(dx) / 100, 1);
    if (ovYesRef.current) ovYesRef.current.style.opacity = dx > 0 ? String(t) : "0";
    if (ovNoRef.current) ovNoRef.current.style.opacity = dx < 0 ? String(t) : "0";
  };

  const end = () => {
    const card = cardRef.current;
    if (!card || !drag.current.on) return;
    drag.current.on = false;
    card.classList.remove("dragging", "pressed");
    if (Math.abs(drag.current.dx) >= 100) {
      const right = drag.current.dx > 0;
      card.classList.add("flying");
      card.classList.remove("drag-right", "drag-left");
      const d = right ? 600 : -600;
      card.style.transform = `translateX(${d}px) rotate(${d * 0.08}deg)`;
      card.style.opacity = "0";
      onAction(item, right ? "apply" : "dislike");
    } else {
      clearDrag();
    }
  };

  return (
    <div className="rec-stack">
      <div
        ref={cardRef}
        className="rec-card"
        draggable={false}
        onDragStart={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          if (e.button !== 0 || (pending.current !== null && pending.current === session.current) || isInteractive(e.target)) return;
          e.preventDefault();
          drag.current = { on: true, sx: e.clientX, dx: 0 };
          cardRef.current?.classList.add("dragging", "pressed");
          try {
            cardRef.current?.setPointerCapture(e.pointerId);
          } catch {
            /* ignore */
          }
        }}
        onPointerMove={(e) => move(e.clientX)}
        onPointerUp={end}
        onPointerCancel={() => {
          drag.current.on = false;
          cardRef.current?.classList.remove("dragging", "pressed");
          clearDrag();
        }}
      >
        <div ref={ovYesRef} className="rec-overlay yes" aria-hidden="true" style={{ opacity: 0 }}>
            {`✓ ${resolveRecommendationKey(apply.overlay)}`}
        </div>
        <div ref={ovNoRef} className="rec-overlay no" aria-hidden="true" style={{ opacity: 0 }}>
          {`✗ ${t("recommend.dislike_overlay")}`}
        </div>

        {item.cover_url && !coverErr ? (
          <img
            className="rec-cover"
            src={item.cover_url}
            loading="lazy"
            draggable={false}
            alt={t("common.cover_alt", { title: `${item.artist} — ${item.title}` })}
            onError={() => setCoverErr(true)}
          />
        ) : (
          <div className="rec-cover-placeholder" aria-hidden="true">♫</div>
        )}

        <div className="rec-info">
          <div className="rec-title">{item.title}</div>
          <div className="rec-artist">{item.artist}</div>
          {item.album ? <div className="rec-album">{item.album}</div> : null}
          {item.seed ? <div className="rec-seed">{t("recommend.similar", { seed: item.seed })}</div> : null}
        </div>

        <div className="rec-bottom">
          <div className="rec-preview">
            <button
              className="small-btn ghost"
              type="button"
              title={t("player.listen")}
              aria-label={t("player.listen_track", { title: item.title })}
              disabled={!item.url || previewBusy}
              onClick={async (e) => {
                e.stopPropagation();
                if (!item.url) return;
                setPreviewBusy(true);
                try {
                  const res = await get<{ url: string }>("/api/preview", { url: item.url });
                  usePlayer.getState().play({
                    src: res.url,
                    title: item.title,
                    artist: item.artist,
                    coverUrl: item.cover_url || "",
                  });
                } catch (err) {
                  toast(asRenderableMessage(err), "error");
                }
                setPreviewBusy(false);
              }}
            >
              <span dangerouslySetInnerHTML={{ __html: SVG_PLAY }} /> {t("player.listen")}
            </button>
          </div>
          <div className="rec-actions">
            <button className="rec-skip" type="button" onClick={(e) => { e.stopPropagation(); onAction(item, "dislike"); }}>
              {t("recommend.dislike")}
            </button>
            <button className="rec-apply" type="button" onClick={(e) => { e.stopPropagation(); onAction(item, "apply"); }}>
                {resolveRecommendationKey(apply.label)}
            </button>
          </div>
          <button className="small-btn ghost rec-skip-all" type="button" onClick={(e) => { e.stopPropagation(); onSkip(); }}>
            {t("recommend.skip")}
          </button>
        </div>
      </div>
    </div>
  );
}
