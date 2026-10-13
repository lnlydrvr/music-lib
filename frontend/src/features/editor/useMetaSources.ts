/* Прогрессивная загрузка метаданных: источники (/api/fetch/meta) запрашиваются
   параллельно по одному и рендерятся по мере ответа, без ожидания самого
   медленного (Discogs). Плюс сессионный по-источниковый кэш — повторное
   открытие редактора того же трека не бьёт по сети (сервер кэширует так же). */
import { useEffect, useState } from "react";
import { get, post } from "../../lib/api";
import { toast } from "../../lib/toast";
import { asRenderableMessage } from "../../i18n/messages";
import type { ProviderRecord } from "../../lib/tags";

export interface MetaResponse {
  path?: string;
  records?: ProviderRecord[];
  [key: string]: unknown;
}

interface MetaSettings {
  metadata_sources?: string[];
  metadata_sources_available?: string[];
}

interface MetaSourcesState {
  /* null — поиск ещё не начался/идёт (в редакторе — спиннер). */
  records: ProviderRecord[] | null;
  /* Источники в полёте — группы «Ищу в X…». */
  pending: string[];
  /* Порядок групп из настроек (вне прогрессивного режима пуст). */
  order: string[];
}

interface UseMetaSourcesOpts {
  /* false — ничего не запрашивать (записи переданы снаружи). */
  enabled?: boolean;
  /* Batch-путь: все источники предзагружены одним запросом. */
  metaPromise?: Promise<MetaResponse> | null;
}

const EMPTY: MetaSourcesState = { records: null, pending: [], order: [] };

/* path → source → записи. */
const metaCache = new Map<string, Map<string, ProviderRecord[]>>();

export function clearMetaCache(): void {
  metaCache.clear();
}

function cachePut(path: string, source: string, recs: ProviderRecord[]): void {
  const by = metaCache.get(path) ?? new Map<string, ProviderRecord[]>();
  by.set(source, recs);
  metaCache.set(path, by);
}

/* Запрос одного источника (фильтр sources) — через кэш. */
export async function fetchMetaBySource(
  path: string,
  thumbnailUrl: string,
  source: string,
): Promise<ProviderRecord[]> {
  const cached = metaCache.get(path)?.get(source);
  if (cached) return cached;
  const meta = await post<MetaResponse>("/api/fetch/meta", {
    path,
    thumbnail_url: thumbnailUrl || "",
    sources: [source],
  });
  const recs = meta.records || [];
  cachePut(path, source, recs);
  return recs;
}

/* Общий запрос без фильтра (batch-prefetch); ответ раскладывается в кэш. */
export async function fetchMetaAll(path: string, thumbnailUrl = ""): Promise<MetaResponse> {
  const meta = await post<MetaResponse>("/api/fetch/meta", {
    path,
    thumbnail_url: thumbnailUrl || "",
  });
  const by = metaCache.get(path) ?? new Map<string, ProviderRecord[]>();
  for (const rec of meta.records || []) {
    by.set(rec.source, [...(by.get(rec.source) || []), rec]);
  }
  metaCache.set(path, by);
  return meta;
}

export function useMetaSources(
  path: string,
  thumbnailUrl: string,
  { enabled = true, metaPromise = null }: UseMetaSourcesOpts = {},
): MetaSourcesState {
  const [state, setState] = useState<MetaSourcesState>(EMPTY);

  useEffect(() => {
    let alive = true;

    if (metaPromise) {
      // Путь batch-редактора: все источники уже предзагружены одним запросом.
      setState(EMPTY);
      metaPromise
        .then((meta) => {
          if (alive) setState({ records: meta.records || [], pending: [], order: [] });
        })
        .catch((e: unknown) => {
          if (!alive) return;
          setState({ records: [], pending: [], order: [] });
          toast({ code: "editor.sources_unavailable_reason", params: { reason: asRenderableMessage(e) } }, "warn");
        });
      return () => {
        alive = false;
      };
    }

    if (!enabled) return;
    setState(EMPTY);

    // Прогрессивный режим: порядок из настроек, по одному параллельно.
    get<MetaSettings>("/api/settings")
      .then((s) => {
        if (!alive) return;
        const avail = s.metadata_sources_available || [];
        const order = (s.metadata_sources || []).filter((n) => avail.includes(n));
        if (!order.length) {
          setState({ records: [], pending: [], order: [] });
          return;
        }
        setState({ records: [], pending: [...order], order });
        const pending = new Set(order);
        let failed = 0;
        order.forEach((name) => {
          fetchMetaBySource(path, thumbnailUrl, name)
            .then((recs) => {
              if (alive) setState((st) => ({ ...st, records: [...(st.records || []), ...recs] }));
            })
            .catch(() => {
              failed += 1;
            })
            .finally(() => {
              pending.delete(name);
              if (!alive) return;
              setState((st) => ({ ...st, pending: [...pending] }));
              if (!pending.size && failed === order.length) toast({ code: "editor.sources_unavailable" }, "warn");
            });
        });
      })
      .catch(() => {
        // Настройки недоступны — одним общим запросом, как раньше.
        fetchMetaAll(path, thumbnailUrl)
          .then((meta) => {
            if (alive) setState({ records: meta.records || [], pending: [], order: [] });
          })
          .catch((e: unknown) => {
            if (!alive) return;
            setState({ records: [], pending: [], order: [] });
            toast({ code: "editor.sources_unavailable_reason", params: { reason: asRenderableMessage(e) } }, "warn");
          });
      });
    return () => {
      alive = false;
    };
  }, [enabled, metaPromise, path, thumbnailUrl]);

  return state;
}
