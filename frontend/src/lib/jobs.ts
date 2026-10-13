import { get, post } from "./api";
import { useDownloads } from "../stores/downloads";
import { resolveMessage, type RenderableMessage } from "../i18n/messages";

export interface JobProgress {
  type?: string;
  kind?: string;
  percent?: number | null;
  message?: RenderableMessage;
  msg?: RenderableMessage;
}

/** Terminal job failures retain their server descriptor for history rendering. */
export class JobError extends Error {
  constructor(readonly renderableMessage: RenderableMessage) {
    super(resolveMessage(renderableMessage));
    this.name = "JobError";
  }
}

/* Кандидат рекомендации из стриминга kind=recommendations. Точный DTO бэкенда
   (`_candidate_from_ytm` + seed из iter_generate): все поля обязательные string. */
export interface RecommendationItem {
  video_id: string;
  artist: string;
  title: string;
  album: string;
  cover_url: string;
  url: string;
  seed: string;
}

/* Progress-событие стриминга рекомендаций: дискриминатор kind + накопительный
   snapshot после каждого обработанного сида (items — полный список, не дельта). */
export interface RecommendationProgress extends JobProgress {
  type: "progress";
  kind: "recommendations";
  seed_index: number;
  seed_count: number;
  seed: string;
  items: RecommendationItem[];
  seeds: number;
  library_count: number;
  total: number;
}

/* SSE даёт быстрый terminal-результат, но polling сохраняется резервом: поток
   может оборваться после завершения задачи и EventSource начнёт реконнект. */
export function waitJob(
  jobId: string,
  onProgress?: (d: JobProgress) => void,
  onRecommendations?: (d: RecommendationProgress) => void,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let polling = false;
    let es: EventSource | null = null;
    let lastProgressSnapshot: string | null = null;
    const notifyProgress = (progress: JobProgress) => {
      const snapshot = JSON.stringify(progress);
      if (snapshot === lastProgressSnapshot) return;
      lastProgressSnapshot = snapshot;
      onProgress?.(progress);
      if ((progress as { kind?: string }).kind === "recommendations") {
        onRecommendations?.(progress as RecommendationProgress);
      }
    };
    const finish = (settler: (v: unknown) => void, value: unknown) => {
      if (settled) return;
      settled = true;
      settler(value);
    };
    const startPolling = () => {
      if (polling) return;
      polling = true;
      const tick = async () => {
        if (settled) return;
        let st: {
          status?: string;
          result?: unknown;
          error?: RenderableMessage | null;
          progress?: JobProgress[];
        };
        try {
          st = await get(`/api/jobs/${jobId}`);
        } catch {
          setTimeout(tick, 500);
          return;
        }
        const latestProgress = st.progress?.at(-1);
      if (latestProgress?.type === "progress") notifyProgress(normalizeProgress(latestProgress));
        if (st.status === "done") {
          es?.close();
          finish(resolve, st.result);
        } else if (st.status === "error") {
          es?.close();
          finish(reject, new JobError(st.error || { code: "jobs.common.failed", message: "Error" }));
        } else {
          setTimeout(tick, 300);
        }
      };
      tick();
    };
    es = new EventSource(`/api/jobs/${jobId}/events`);
    es.onmessage = (ev) => {
      let data: { type?: string; kind?: string } & JobProgress;
      try {
        data = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (data.type === "done") {
        es?.close();
        /* Бэкенд terminal done не содержит result: завершаем быстро, но итог
           читаем status-опросом. Если другой сервер прислал result — берём его. */
        if (Object.hasOwn(data, "result")) finish(resolve, (data as { result?: unknown }).result);
        else startPolling();
        return;
      }
      if (data.type === "error") {
        es?.close();
        const terminal = data as { error?: RenderableMessage | null; message?: RenderableMessage; msg?: RenderableMessage };
        finish(reject, new JobError(terminal.error ?? terminal.message ?? terminal.msg ?? { code: "jobs.common.failed", message: "Error" }));
        return;
      }
      if (data.type !== "progress") return;
      /* Общий коллбэк получает все progress-события, включая рекомендации. */
      notifyProgress(normalizeProgress(data));
    };
    es.onopen = startPolling;
    es.onerror = () => {
      // Поток оборвался — прогресс может пропасть, но результат ждём опросом.
      es?.close();
      startPolling();
    };
  });
}

function normalizeProgress(progress: JobProgress): JobProgress {
  if (progress.message !== undefined) return progress;
  if (progress.msg !== undefined) return { ...progress, message: progress.msg };
  return progress;
}

/* Единая точка запуска фоновой задачи: POST → job_id → SSE/опрос результата.
   Прогресс и завершение автоматически трекаются доком загрузок. */
export async function startJob<T = unknown>(
  endpoint: string,
  body?: unknown,
  {
    onProgress,
    onRecommendations,
    title,
  }: {
    onProgress?: (d: JobProgress) => void;
    onRecommendations?: (d: RecommendationProgress) => void;
    title?: RenderableMessage;
  } = {},
): Promise<T> {
  const { job_id } = await post<{ job_id: string }>(endpoint, body);
  const dl = useDownloads.getState();
  dl.track(job_id, dl.titleFor(endpoint, title));
  try {
    const result = await waitJob(
      job_id,
      (d) => {
        useDownloads.getState().progress(job_id, d);
        if (onProgress) onProgress(d);
      },
      onRecommendations,
    );
    useDownloads.getState().finish(job_id, true, { code: "jobs.common.done", message: "Done" });
    return result as T;
  } catch (e) {
    const message = e instanceof JobError
      ? e.renderableMessage
      : (e as Error)?.message || String(e || "Error");
    useDownloads.getState().finish(job_id, false, message);
    throw e;
  }
}
