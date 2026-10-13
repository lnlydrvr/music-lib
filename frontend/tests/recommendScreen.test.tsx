import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import RecommendScreen from "../src/views/RecommendScreen";
import { startJob } from "../src/lib/jobs";
import { JobError } from "../src/lib/jobs";
import { ApiError } from "../src/lib/api";
import type { JobProgress, RecommendationItem, RecommendationProgress } from "../src/lib/jobs";
import { toast } from "../src/lib/toast";
import { changeLanguage } from "../src/i18n";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));
vi.mock("../src/lib/jobs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lib/jobs")>();
  return { ...actual, startJob: vi.fn() };
});

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

/* Точный DTO бэкенда (`_candidate_from_ytm` + seed): все поля обязательные string. */
function rec(over: Partial<RecommendationItem> = {}): RecommendationItem {
  return {
    video_id: "",
    artist: "Artist",
    title: "Song",
    album: "",
    cover_url: "",
    url: "",
    seed: "",
    ...over,
  };
}

const ITEMS: RecommendationItem[] = [
  rec({ video_id: "v1", artist: "Artist A", title: "Song A", album: "Album A", seed: "Seed X", url: "http://w/1", cover_url: "http://c/1.jpg" }),
  rec({ video_id: "v2", artist: "Artist B", title: "Song B" }),
];

/* Snapshot kind=recommendations — накопительный список после обработанного сида. */
function snap(items: RecommendationItem[], over: Partial<RecommendationProgress> = {}): RecommendationProgress {
  return {
    type: "progress",
    kind: "recommendations",
    msg: "",
    seed_index: 1,
    seed_count: 3,
    seed: "Seed X",
    items,
    seeds: 3,
    library_count: 10,
    total: items.length,
    ...over,
  };
}

type JobOpts = {
  onProgress?: (d: JobProgress) => void;
  onRecommendations?: (d: RecommendationProgress) => void;
};

/* Отложенный startJob: коллбэки и resolve/reject — в руках теста,
   карточки появляются ДО settle промиса. */
function delayedJob() {
  let onProgress!: (d: JobProgress) => void;
  let onRecommendations!: (d: RecommendationProgress) => void;
  let resolve!: (v: unknown) => void;
  let reject!: (e: Error) => void;
  vi.mocked(startJob).mockImplementationOnce((((_endpoint: string, _body?: unknown, opts?: JobOpts) => {
    onProgress = opts!.onProgress!;
    onRecommendations = opts!.onRecommendations!;
    return new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
  }) as unknown) as typeof startJob);
  return {
    progress: (d: JobProgress) => act(() => onProgress(d)),
    rec: (d: RecommendationProgress) => act(() => onRecommendations(d)),
    /* Обёртки читают переменные в момент вызова — коллбэки назначаются
       только после монтирования экрана. */
    resolve: (v: unknown) => resolve(v),
    reject: (e: Error) => reject(e),
    /* Сырые коллбэки без act — проверка «после unmount ничего не обновляется». */
    rawRec: (d: RecommendationProgress) => onRecommendations(d),
    rawProgress: (d: JobProgress) => onProgress(d),
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  location.hash = "";
  vi.mocked(toast).mockClear();
  vi.mocked(startJob).mockReset();
  fetchMock = vi.fn(async (url: string) => {
    if (url === "/api/settings") return jsonResponse({ ytm_feedback_action: "like" });
    if (url === "/api/recommend/apply" || url === "/api/recommend/dislike") return jsonResponse({});
    throw new Error(`unexpected ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = "";
});

function renderScreen() {
  return render(
    <DialogProvider>
      <RecommendScreen />
    </DialogProvider>,
  );
}

describe("RecommendScreen", () => {
  it("генерация: карточка, счётчик, инфо о библиотеке", async () => {
    vi.mocked(startJob).mockResolvedValue({ items: ITEMS, library_count: 10, total: 2 } as never);
    renderScreen();
    expect(await screen.findByText("Song A")).toBeInTheDocument();
    expect(screen.getByText("Artist A")).toBeInTheDocument();
    expect(screen.getByText("Album A")).toBeInTheDocument();
    expect(screen.getByText("похоже на: Seed X")).toBeInTheDocument();
    expect(screen.getByText("1 из 2")).toBeInTheDocument();
    expect(screen.getByText("Библиотека: 10 треков · рекомендаций: 2")).toBeInTheDocument();
    // Действие из настроек — «Лайк».
    expect(screen.getByRole("button", { name: "Лайк" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Дизлайк" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Пропустить" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Прослушать: Song A" })).toBeEnabled();
    // У второго трека нет url — после перехода кнопка «Слушать» отключится.
  });

  it("«Лайк»: POST /api/recommend/apply → следующая карточка", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockResolvedValue({ items: ITEMS, library_count: 10, total: 2 } as never);
    renderScreen();
    await screen.findByText("Song A");

    await user.click(screen.getByRole("button", { name: "Лайк" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Лайк отправлен в YouTube Music"));
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/recommend/apply")).toBe(true);
    const body = JSON.parse(String(fetchMock.mock.calls.find(([u]) => u === "/api/recommend/apply")?.[1]?.body));
    expect(body).toEqual({ artist: "Artist A", title: "Song A" });
    // Очередь продвинулась.
    await waitFor(() => expect(screen.getByText("2 из 2")).toBeInTheDocument());
    expect(screen.getByText("Song B")).toBeInTheDocument();
    // Без url кнопка «Слушать» недоступна.
    expect(screen.getByRole("button", { name: "Прослушать: Song B" })).toBeDisabled();
  });

  it("«Дизлайк»: POST /api/recommend/dislike; «Пропустить» — без запроса", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockResolvedValue({ items: ITEMS, library_count: 10, total: 2 } as never);
    renderScreen();
    await screen.findByText("Song A");

    // Пропуск без обращения к аккаунту.
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    await waitFor(() => expect(screen.getByText("Song B")).toBeInTheDocument());
    expect(fetchMock.mock.calls.filter(([u]) => u.startsWith("/api/recommend/"))).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Дизлайк" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Дизлайк отправлен — радио это учтёт"));
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/recommend/dislike")).toBe(true);
    // Очередь пуста.
    await waitFor(() => expect(screen.getByText("Рекомендаций больше нет")).toBeInTheDocument());
  });

  it("действие принятия из настройки — «В библиотеку»", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      jsonResponse(url === "/api/settings" ? { ytm_feedback_action: "library" } : {}),
    );
    vi.mocked(startJob).mockResolvedValue({ items: ITEMS, library_count: 10, total: 2 } as never);
    renderScreen();
    expect(await screen.findByRole("button", { name: "В библиотеку" })).toBeInTheDocument();
  });

  it("descriptor JobError без YT-коннекта: состояние с кнопкой в настройки и сменой локали", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockRejectedValue(
      new JobError({
        code: "api.errors.ytm_connection_required",
        params: { source: "account" },
        message: "Connect YouTube Music (Settings → YouTube Music)",
      }) as never,
    );
    renderScreen();
    expect(await screen.findByText("YouTube Music не подключён")).toBeInTheDocument();
    expect(screen.getByText("Подключите YouTube Music (настройки → YouTube Music)")).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });
    expect(await screen.findByText("Connect YouTube Music (Settings → YouTube Music)")).toBeInTheDocument();
    expect(screen.getByText("YouTube Music is not connected")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open settings" }));
    expect(location.hash).toBe("#/settings");
  });

  it("переключение локали обновляет активный результат, не изменяя данные трека", async () => {
    vi.mocked(startJob).mockResolvedValue({ items: ITEMS, library_count: 10, total: 2 } as never);
    await changeLanguage("ru");
    renderScreen();
    await screen.findByText("Библиотека: 10 треков · рекомендаций: 2");

    await act(async () => { await changeLanguage("en"); });
    expect(screen.getByText("Library: 10 tracks · recommendations: 2")).toBeInTheDocument();
    expect(screen.getByText("Song A")).toBeInTheDocument();
    expect(screen.getByText("Artist A")).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("ApiError до создания job показывает состояние подключения и ведёт в настройки", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockRejectedValue(
      new ApiError(401, {
        code: "api.errors.ytm_connection_required",
        message: "Connect YouTube Music (Settings → YouTube Music)",
      }) as never,
    );
    renderScreen();

    expect(await screen.findByText("YouTube Music не подключён")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Открыть настройки" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Открыть настройки" }));
    expect(location.hash).toBe("#/settings");
  });
});

describe("RecommendScreen: потоковые рекомендации", () => {
  it("loading → streaming → ready: карточка до resolve, append-only, дедуп, финал", async () => {
    const user = userEvent.setup();
    const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A", album: "Album A", seed: "Seed X" });
    const B = rec({ video_id: "v2", artist: "Artist B", title: "Song B" });
    const C = rec({ video_id: "v3", artist: "Artist C", title: "Song C" });
    const D = rec({ artist: "Artist D", title: "Song D" });
    // Без video_id — дедуп по нормализованной паре artist/title.
    const Ddup = rec({ artist: "artist  d", title: " SONG d " });
    const E = rec({ video_id: "v5", artist: "Artist E", title: "Song E" });

    const job = delayedJob();
    renderScreen();

    // loading: прогресс идёт, карточек нет, «больше нет» не показываем.
    expect(await screen.findByText("Сбор сидов...")).toBeInTheDocument();
    expect(screen.queryByText("Рекомендаций больше нет")).not.toBeInTheDocument();

    // Первый snapshot: карточка появляется ДО resolve (streaming).
    job.rec(snap([A, B]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();
    expect(screen.getByText("1 из 2")).toBeInTheDocument();
    // Стриминг продолжается: прогресс «Обработан сид N из M» рядом с карточкой.
    expect(screen.getByText("Обработан сид 1 из 3")).toBeInTheDocument();
    expect(screen.getByText("Библиотека: 10 треков · рекомендаций: 2")).toBeInTheDocument();

    // Пропуск A: обработанная карточка не должна вернуться из будущих snapshot/финала.
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    await waitFor(() => expect(screen.getByText("Song B")).toBeInTheDocument());
    expect(screen.getByText("2 из 2")).toBeInTheDocument();

    // Второй snapshot: только новые элементы в хвост; дубли (A, B, пара-вариант D) отброшены.
    job.rec(snap([A, B, C, D, Ddup], { seed_index: 2, library_count: 11, total: 4 }));
    await waitFor(() => expect(screen.getByText("2 из 4")).toBeInTheDocument());
    // Очередь не заменена snapshot-ом — B всё ещё первая карточка.
    expect(screen.getByText("Song B")).toBeInTheDocument();
    expect(screen.getByText("Библиотека: 11 треков · рекомендаций: 4")).toBeInTheDocument();

    // Лайк B: и эта обработанная не вернётся из финала.
    await user.click(screen.getByRole("button", { name: "Лайк" }));
    await waitFor(() => expect(screen.getByText("Song C")).toBeInTheDocument());
    expect(screen.getByText("3 из 4")).toBeInTheDocument();

    // Финал: новый элемент (E) в хвост, счётчики обновлены, стриминг завершён (ready).
    await act(async () => {
      job.resolve({ items: [A, B, C, D, E], seeds: 3, library_count: 12, total: 5 });
    });
    await waitFor(() => expect(screen.getByText("3 из 5")).toBeInTheDocument());
    expect(screen.getByText("Библиотека: 12 треков · рекомендаций: 5")).toBeInTheDocument();
    expect(screen.getByText("Song C")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("ошибка стриминга сохраняет уже выданные карточки", async () => {
    const user = userEvent.setup();
    const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });
    const B = rec({ video_id: "v2", artist: "Artist B", title: "Song B" });

    const job = delayedJob();
    renderScreen();
    job.rec(snap([A, B]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();

    await act(async () => {
      job.reject(new Error("Радио недоступно"));
    });
    expect(await screen.findByText("Радио недоступно")).toBeInTheDocument();
    // Частичная очередь жива: карточка на месте, действия работают.
    expect(screen.getByText("Song A")).toBeInTheDocument();
    expect(screen.queryByText("Рекомендаций больше нет")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Лайк" }));
    await waitFor(() => expect(screen.getByText("Song B")).toBeInTheDocument());
    expect(screen.getByText("2 из 2")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("snapshot descriptor перерисовывается при смене локали и сохраняет его params", async () => {
    const job = delayedJob();
    await changeLanguage("ru");
    renderScreen();
    const descriptor = {
      code: "jobs.recommend.seed",
      params: { index: 2, total: 7 },
      message: "Processed seed 2 of 7",
    };

    job.rec(snap([rec({ video_id: "v1" })], {
      seed_index: 2,
      seed_count: 7,
      message: descriptor,
      msg: "legacy progress must not replace descriptor",
    }));
    expect(await screen.findByText("Обработан сид 2 из 7")).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });
    expect(await screen.findByText("Processed seed 2 of 7")).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("новая сессия игнорирует snapshot/финал прежнего запуска", async () => {
    const user = userEvent.setup();
    const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });
    const Z = rec({ video_id: "vz", artist: "Artist Z", title: "Song Z" });
    const Q = rec({ video_id: "vq", artist: "Artist Q", title: "Song Q" });

    const first = delayedJob();
    renderScreen();
    first.rec(snap([A]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();

    // Очередь исчерпана → «Обновить рекомендации» запускает вторую сессию.
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    const refresh = await screen.findByRole("button", { name: "Обновить рекомендации" });
    const second = delayedJob();
    await user.click(refresh);
    expect(await screen.findByText("Сбор сидов...")).toBeInTheDocument();

    // Поздние callbacks первой сессии — мимо: ни Z, ни возврата пропущенной A.
    first.rec(snap([A, Z]));
    await act(async () => {
      first.resolve({ items: [A, Z], seeds: 3, library_count: 10, total: 2 });
    });
    expect(screen.queryByText("Song Z")).not.toBeInTheDocument();
    expect(screen.queryByText("Song A")).not.toBeInTheDocument();
    // Вторая сессия всё ещё в loading — её прогресс не тронут старым финалом.
    expect(screen.getByText("Сбор сидов...")).toBeInTheDocument();

    // И обычный progress-событие старой сессии тоже игнорируется.
    first.progress({ percent: 77, msg: "Прежний сид" });
    expect(screen.queryByText("Прежний сид")).not.toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");

    // Snapshot новой сессии применяется.
    second.rec(snap([Q], { seed_index: 2, seed_count: 4 }));
    expect(await screen.findByText("Song Q")).toBeInTheDocument();
    expect(screen.getByText("1 из 1")).toBeInTheDocument();
    expect(screen.getByText("Обработан сид 2 из 4")).toBeInTheDocument();

    await act(async () => {
      second.resolve({ items: [Q], seeds: 4, library_count: 10, total: 1 });
    });
    await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
    expect(screen.getByText("Библиотека: 10 треков · рекомендаций: 1")).toBeInTheDocument();
  });

  it("разные video_id при одинаковых artist/title — остаются обе карточки", async () => {
    const user = userEvent.setup();
    const A1 = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });
    const A2 = rec({ video_id: "v2", artist: "Artist A", title: "Song A" });

    const job = delayedJob();
    renderScreen();

    // Контракт дедупа: непустой video_id → ключ только v:<id>. Норм-пара не
    // участвует — разные id это разные треки, обе карточки в очереди.
    job.rec(snap([A1, A2]));
    expect(await screen.findByText("1 из 2")).toBeInTheDocument();

    // Пропустили первую версию — вторая на её месте, счётчик дошёл до 2.
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    await waitFor(() => expect(screen.getByText("2 из 2")).toBeInTheDocument());
    expect(screen.getByText("Song A")).toBeInTheDocument();

    // Финал с теми же элементами ничего не добавляет и не возвращает первую.
    await act(async () => {
      job.resolve({ items: [A1, A2], seeds: 3, library_count: 10, total: 2 });
    });
    await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
    expect(screen.getByText("2 из 2")).toBeInTheDocument();
    expect(screen.getByText("Song A")).toBeInTheDocument();
  });

  it("fallback без video_id: feat-вариант названия дедупится по норме бэкенда", async () => {
    const user = userEvent.setup();
    // Пара 1: фичи не меняют песню (norm_title): «Song D» и «Song D (feat.
    // Guest)» — один трек. Пара 2: транслит-норма (norm): «Valentin
    // Strykalo» и «Валентин Стрыкало» с пунктуацией — тоже.
    const D = rec({ artist: "Artist D", title: "Song D" });
    const Dfeat = rec({ artist: "artist  d", title: "Song D (feat. Guest)" });
    const T = rec({ artist: "Valentin Strykalo", title: "Кукушка" });
    const Tcyr = rec({ artist: "Валентин Стрыкало", title: "кукушка!" });

    const job = delayedJob();
    renderScreen();

    // Четыре элемента → две карточки: ключ n:norm(artist)|norm_title(title).
    job.rec(snap([D, Dfeat, T, Tcyr]));
    expect(await screen.findByText("Song D")).toBeInTheDocument();
    expect(screen.getByText("1 из 2")).toBeInTheDocument();
    // Выжила первая карточка пары — feat-вариант не в очереди.
    expect(screen.queryByText("Song D (feat. Guest)")).not.toBeInTheDocument();

    // Пропуск D → «Кукушка»; финал с дублями ничего не возвращает.
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    await waitFor(() => expect(screen.getByText("Кукушка")).toBeInTheDocument());
    expect(screen.getByText("2 из 2")).toBeInTheDocument();

    await act(async () => {
      job.resolve({ items: [D, Dfeat, T, Tcyr], seeds: 3, library_count: 10, total: 4 });
    });
    await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
    expect(screen.getByText("Кукушка")).toBeInTheDocument();
    expect(screen.getByText("2 из 2")).toBeInTheDocument();
    expect(screen.queryByText("Song D")).not.toBeInTheDocument();
  });

  it.each([
    ["skip", "Пропустить"],
    ["apply", "Лайк"],
    ["dislike", "Дизлайк"],
  ] as const)(
    "обработанная карточка (%s) не возвращается из поздних snapshot и финала",
    async (_kind, btnName) => {
      const user = userEvent.setup();
      const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });
      const B = rec({ video_id: "v2", artist: "Artist B", title: "Song B" });

      const job = delayedJob();
      renderScreen();
      job.rec(snap([A, B]));
      expect(await screen.findByText("Song A")).toBeInTheDocument();

      // Обрабатываем A любым из трёх способов — B становится текущей.
      await user.click(screen.getByRole("button", { name: btnName }));
      await waitFor(() => expect(screen.getByText("Song B")).toBeInTheDocument());
      expect(screen.getByText("2 из 2")).toBeInTheDocument();

      // Поздний накопительный snapshot всё ещё содержит A — не возвращаем.
      job.rec(snap([A, B], { seed_index: 2 }));
      await waitFor(() => expect(screen.getByText("Обработан сид 2 из 3")).toBeInTheDocument());
      expect(screen.queryByText("Song A")).not.toBeInTheDocument();
      expect(screen.getByText("2 из 2")).toBeInTheDocument();

      // Финальный DTO тоже содержит A — карточка не resurrect-ится.
      await act(async () => {
        job.resolve({ items: [A, B], seeds: 3, library_count: 10, total: 2 });
      });
      await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
      expect(screen.queryByText("Song A")).not.toBeInTheDocument();
      expect(screen.getByText("Song B")).toBeInTheDocument();
      expect(screen.getByText("2 из 2")).toBeInTheDocument();
    },
  );

  it("поздний apply/dislike старой сессии не трогает очередь и handled новой", async () => {
    const user = userEvent.setup();
    const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });

    // Дизлайк висит в полёте: момент ответа контролируем вручную.
    let releaseDislike!: () => void;
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ ytm_feedback_action: "like" });
      if (url === "/api/recommend/dislike")
        return new Promise((res) => {
          releaseDislike = () => res(jsonResponse({}));
        });
      throw new Error(`unexpected ${url}`);
    });

    const first = delayedJob();
    renderScreen();
    first.rec(snap([A]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();

    // Дизлайк (POST в полёте) и тут же «Пропустить»: карточка ушла, очередь пуста.
    await user.click(screen.getByRole("button", { name: "Дизлайк" }));
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    const refresh = await screen.findByRole("button", { name: "Обновить рекомендации" });

    // Новая сессия: seen/handled обнулены, радио снова рекомендует A.
    const second = delayedJob();
    await user.click(refresh);
    expect(await screen.findByText("Сбор сидов...")).toBeInTheDocument();
    second.rec(snap([A]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();

    // Ответ старого дизлайка приходит уже внутри новой сессии: карточка A
    // новой сессии не должна исчезнуть, handled новой сессии — не замусориться.
    await act(async () => {
      releaseDislike();
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Дизлайк отправлен — радио это учтёт"));
    expect(await screen.findByText("Song A")).toBeInTheDocument();
  });

  it("pending привязан к сессии: старый POST не блокирует новую карточку и не сбрасывает её pending", async () => {
    const user = userEvent.setup();
    const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });
    const B = rec({ video_id: "v2", artist: "Artist B", title: "Song B" });

    // Оба action-POST — под ручным управлением: момент ответа контролирует тест.
    let releaseOldDislike!: () => void;
    let releaseNewApply!: () => void;
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ ytm_feedback_action: "like" });
      if (url === "/api/recommend/dislike")
        return new Promise((res) => {
          releaseOldDislike = () => res(jsonResponse({}));
        });
      if (url === "/api/recommend/apply")
        return new Promise((res) => {
          releaseNewApply = () => res(jsonResponse({}));
        });
      throw new Error(`unexpected ${url}`);
    });

    const first = delayedJob();
    renderScreen();
    first.rec(snap([A]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();

    // Дизлайк сессии 1 висит в полёте; карточку убираем пропуском → «Обновить».
    await user.click(screen.getByRole("button", { name: "Дизлайк" }));
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    const refresh = await screen.findByRole("button", { name: "Обновить рекомендации" });

    // Новая сессия: seen/handled обнулены, A рекомендована снова (+ B в хвосте).
    const second = delayedJob();
    await user.click(refresh);
    expect(await screen.findByText("Сбор сидов...")).toBeInTheDocument();
    second.rec(snap([A, B]));
    expect(await screen.findByText("Song A")).toBeInTheDocument();
    expect(screen.getByText("1 из 2")).toBeInTheDocument();

    // Лайк новой сессии уходит отдельным POST, НЕ дожидаясь старого дизлайка.
    await user.click(screen.getByRole("button", { name: "Лайк" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u === "/api/recommend/apply")).toBe(true));
    // Карточка ждёт ответа — из очереди не ушла.
    expect(screen.getByText("Song A")).toBeInTheDocument();

    // Поздний ответ старого дизлайка: toast есть, но (а) очередь/handled новой
    // сессии не тронуты, (б) pending новой сессии жив — повторное действие на
    // той же карточке не отправляет второй POST в аккаунт.
    await act(async () => {
      releaseOldDislike();
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Дизлайк отправлен — радио это учтёт"));
    await user.click(screen.getByRole("button", { name: "Дизлайк" }));
    expect(fetchMock.mock.calls.filter(([u]) => u === "/api/recommend/dislike")).toHaveLength(1);
    expect(screen.getByText("Song A")).toBeInTheDocument();
    expect(screen.getByText("1 из 2")).toBeInTheDocument();

    // Ответ нового лайка продвигает очередь новой сессии.
    await act(async () => {
      releaseNewApply();
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Лайк отправлен в YouTube Music"));
    await waitFor(() => expect(screen.getByText("Song B")).toBeInTheDocument());
    expect(screen.getByText("2 из 2")).toBeInTheDocument();
  });

  it("unmount инвалидирует сессию: поздние коллбэки старого экрана не трогают новую сессию", async () => {
    const A = rec({ video_id: "v1", artist: "Artist A", title: "Song A" });
    const Z = rec({ video_id: "vz", artist: "Artist Z", title: "Song Z" });
    const Q = rec({ video_id: "vq", artist: "Artist Q", title: "Song Q" });

    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      // Экземпляр 1: живая сессия, коллбэки — в руках теста.
      const first = delayedJob();
      const view = renderScreen();
      first.rec(snap([A]));
      expect(await screen.findByText("Song A")).toBeInTheDocument();
      view.unmount();

      // Экземпляр 2 (возврат на экран): новая сессия в loading — 0%, «Сбор сидов...».
      const second = delayedJob();
      renderScreen();
      expect(await screen.findByText("Сбор сидов...")).toBeInTheDocument();
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");

      // Поздние события сессии 1 — сырые (без act): snapshot, progress и финал.
      first.rawRec(snap([A, Z]));
      first.rawProgress({ percent: 55, msg: "Поздний сид" });
      first.resolve({ items: [A, Z], seeds: 3, library_count: 10, total: 2 });
      await new Promise((r) => setTimeout(r, 10));

      // Очередь/прогресс НОВОЙ сессии не изменились: ни карточки старой (A/Z),
      // ни её прогресс, счётчики и инфо-строка не появились.
      expect(screen.queryByText("Song A")).not.toBeInTheDocument();
      expect(screen.queryByText("Song Z")).not.toBeInTheDocument();
      expect(screen.queryByText("Поздний сид")).not.toBeInTheDocument();
      expect(screen.queryByText("Обработан сид 1 из 3")).not.toBeInTheDocument();
      expect(screen.queryByText("1 из 2")).not.toBeInTheDocument();
      expect(screen.queryByText(/Библиотека: /)).not.toBeInTheDocument();
      expect(screen.getByText("Сбор сидов...")).toBeInTheDocument();
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
      expect(errSpy).not.toHaveBeenCalled();

      // Новая сессия живёт своей жизнью: стриминг (карточка Q, прогресс 1/2 = 50%).
      second.rec(snap([Q], { seed_index: 1, seed_count: 2 }));
      expect(await screen.findByText("Song Q")).toBeInTheDocument();
      expect(screen.getByText("1 из 1")).toBeInTheDocument();
      expect(screen.getByText("Обработан сид 1 из 2")).toBeInTheDocument();
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");

      // И доводит до конца: финал → ready, прогресс скрыт, инфо — только её.
      await act(async () => {
        second.resolve({ items: [Q], seeds: 2, library_count: 10, total: 1 });
      });
      await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
      expect(screen.getByText("Song Q")).toBeInTheDocument();
      expect(screen.getByText("1 из 1")).toBeInTheDocument();
      expect(screen.getByText("Библиотека: 10 треков · рекомендаций: 1")).toBeInTheDocument();
      expect(errSpy).not.toHaveBeenCalled();
    } finally {
      errSpy.mockRestore();
    }
  });
});
