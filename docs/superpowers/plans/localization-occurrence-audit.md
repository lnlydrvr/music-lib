# Аудит совпадений локализации (15 октября 2026)

**Статус: НЕ ЗАКРЫТ.** Это сверка сохранённых результатов поиска, не сертификат полноты локализации. Исходный код и каталоги не менялись. Рабочее дерево уже содержит многочисленные чужие незакоммиченные изменения; координаты снимков не считаются координатами текущего дерева.

## Граница и способ воспроизведения

Запускать из корня репозитория (точные regex из canonical map, без изменения файлов):

```sh
rg -n 'aria-label=|title=|alt=|placeholder=|toast\(|\.confirm\(|\.prompt\(|\.info\(|\.pick\(|\.open\(|\.set\(|<[^>]+>[^<{]*[[:alpha:]]|label:|text:|sub:|heading=|message' frontend/src -g '*.ts' -g '*.tsx'
rg -n 'HTTPException|detail=|JSONResponse|\.push\(|message=|msg=|jobs\.submit|errors\[|RuntimeError|\["label"\]|\["error"\]|\.fail\(' src/web src/health.py src/lint.py src/quality.py src/normalize.py
```

Снимки в `/var/folders/0m/z7g8zg994kd53mq_8cw3nsn80000gp/T/opencode/`: `localization-frontend-hits.txt`, `localization-backend-hits.txt`, `current-frontend-wide.txt`, `current-backend-wide.txt`. Каждая строка имеет формат `path:line:source`, разбор **по первым двум** разделителям `:` после пути и номера (в исходном тексте двоеточия допустимы). Идентичность для мультимножества: `(path, strip(source))`; номер строки — координата, не identity. Нормализация ограничена снятием краевых пробелов, чтобы не объявлять одинаковыми разные условия/аргументы. При совпадении нескольких одинаковых строк учитывается `min(old_count,new_count)`; ни одна копия не теряется. «Изменено» ниже — не автоматическое соответствие конкретных строк: это расход двух мультимножеств в том же файле; без AST/исторического checkout нельзя доказать пару old→new.

| Срез | Исторических строк | В сохранённом current | Точное пересечение с учётом кратности | Только old | Только current | Повторяющихся identities old/current | Макс. кратность old/current |
|---|---:|---:|---:|---:|---:|---:|---:|
| frontend | 778 | 853 | 356 | 422 | 497 | 30/28 | 7/7 |
| backend | 164 | 167 | 49 | 115 | 118 | 23/23 | 11/9 |

`422/497` и `115/118` **не** означают столько исправлений/новых ошибок: текст одного вызова изменился, изменился набор файлов, а отдельные совпадения относятся к техническим выражениям. Пример реально изменённого выражения с кратностью: `views/SearchScreen.tsx`, `toast(String((e as Error)?.message || e), "error");` ×7 в old и `toast(asRenderableMessage(e), "error");` ×7 в current. Появление `asRenderableMessage` сохраняет descriptor, но не является доказательством происхождения каждой ошибки. Изменённые backend-вызовы `job.push("Готово", 100)` ×4 → `job.push(message("jobs.common.done", fallback="Done"), 100)` ×4 подтверждаются только на уровне семейства, не позиционного попарного матчинга.

Повторное исполнение **тех же** regex в этом рабочем дереве: frontend **854**, backend **155** (не 853/167). Проверка буквального совпадения снимка с нынешней строкой по снимковому номеру: historical frontend 36/778, saved current frontend 817/853; historical backend 2/164, saved current backend 19/167. Поэтому даже `current-*` — сохранённая промежуточная версия, а не сегодняшняя истина. Разницу по всем строкам live rerun не сохраняли по условию «только отчёт»; новопоявившийся или исчезнувший live-hit остаётся непроверенным. Историческую строку можно классифицировать по её собственному литералу, но нельзя удостоверить миграцию *каждой* old-ветки по одному текущему номеру. Область сканирования также не равна всему продукту: frontend regex не ищет каждый JS/JSX литерал, backend regex не ищет все конструкторы diagnostics/косвенные вызовы, HTML и 503 вне ряда попаданий.

## Критерии и реально подтверждённое

`K` = **доказана только конкретная прямая ссылка** в строке снимка: `t("key")` / `i18n.t("key")` или `{code:"key"}` в frontend; `message("code", ...)` / `_message("code", ...)` в backend, причём ключ существует и непуст в *обоих* нынешних JSON-каталогах. Доказательство этой ссылки НЕ распространяется на остальные выражения той же строки. Ключ/код читается непосредственно из исходной строки снимка; правило извлечения: `(?:t|i18n.t|message|_message)\(\s*['"]([\w.]+)['"]` или `code:\s*['"]([\w.]+)['"]`, проверить путь в `frontend/src/locales/{en,ru}.json`. Типизированный `t()` и проверка каталогов не устанавливают происхождение каждой строковой переменной.

`U` = **неразрешённый candidate**, включая технические ложные срабатывания, для которых по одному hit не доказана конкретная граница владения. Это НЕ категория «плохой копии»; в дальнейшем конкретный U должен получить одно из: `K` (с **точным** code), `D` (ограниченные data/provider/technical, с источником), `N` (не-UI: тип/импорт/лог/комментарий/служебный ID), `L` (исключение целой legacy-строки, с веткой/причиной). В приложении ниже классы заданы на уровне **ординального номера строки в конкретном файле снимка**, не номера строки source. Запись `K` означает только подтверждение ссылки; если есть другая UI-строка в том же hit, классификация всего hit должна быть пересмотрена. Отсутствие missing keys среди найденных прямых ссылок не является доказательством полноты.

| Снимок | K: прямой ключ/код в EN+RU | U: не аттестовано целиком | Подтверждённые D/N/L внутри U (примеры, не вычитаются из U) |
|---|---:|---:|---|
| historical frontend | 0 | 778 | старые UI-литералы, URL/типы/технические поля вперемешку |
| saved current frontend | 267 | 586 | `settings/YtmCard.tsx` credentials, `QualityScreen.tsx` Inbox, импортные типы |
| historical backend | 0 | 164 | старые owned ошибки/job/diagnostics и raw provider ветки |
| saved current backend | 103 | 64 | исключения L ниже, объявления/импорты, транспортные строки |

Эти числа отражают **порог доказанности**, а не итоговую оценку локализации. Выражения с вычисляемыми ключами (например `message(progress_code,...)`) требуют отдельного разбора. В снимке frontend совпадения `t()` внутри import *не* входят в K: импорт `RenderableMessage`/`resolveMessage` — тип/функция, не UI-перевод. Проверены контексты `frontend/src/i18n/messages.ts:99–125` (перевод descriptor только при выводе), `views/QualityScreen.tsx:57–62,94–129` (представление нормализации и `Inbox`), `views/settings/YtmCard.tsx:89–112,217–229` (API-состояние и рендер). Это выборочные трассы, **не** контекстная верификация всех 853 строк.

Проверенные узкие границы: `views/settings/YtmCard.tsx` сохранённые current ordinals 763 (образец HTTP заголовков), 765–766 (`client_id`, `client_secret`) — D, текстовые технические значения/идентификаторы, не произвольное исключение для остальных placeholders; current 781 (`row.title`/`row.error`) — D только при условии показанного provider/API происхождения, требуются проверки всех `rows`. `views/SettingsScreen.tsx` current 30: `English` — D (самоназвание языка), 38 `Shazam` и 40 `Primuse` — D (названия сервисов); `views/QualityScreen.tsx` current 49 `Inbox` — D (имя реальной папки, проверка `isInboxPath`), 47 — fallback-only `message` внутри `renderNormalizationChange` с ключом `diagnostics.quality.change` в соседних строках; не следует записывать 47 в K по соседству. `views/MiscScreen.tsx` current 815 `Shazam` — D (бренд). Для остального множества U данных оснований недостаточно.

## Backend: проверенные ветки, исключения, риски

Проверено на нынешнем дереве: `src/web/jobs.py:33–85,89–106,138–145` хранит descriptor в `name`, `error`, `events[].message`, отдаёт его через `to_dict()` и SSE, legacy `msg` получает строковый fallback. `JobFailure` сохраняет известную структурированную ошибку, generic `except Exception` оставляет `str(e)`. `src/web/routes.py:1306–1365` поддерживает `jobs.download.unknown_error` только при отсутствии `result.error`, при его наличии остаётся raw string; `:1392–1428` и `:2540–2578` показывают косвенный `_BatchProgress.update/complete` с `jobs.download.batch_progress`, `batch_finished`, `batch_item`, `batch_complete`. Код, параметры и существование этих ключей в EN/RU проверены, но `current-backend-wide.txt:156` (`self.job.push(msg)`) сам по себе не доказывает содержимое `msg`. `src/web/routes.py:2420–2444,2470–2475` использует `JobFailure(message("jobs.shazam.file_missing" / "jobs.shazam.empty_file" / "jobs.shazam.file_unset"))`; исторические `RuntimeError` здесь более не обосновывают незакрытую owned ветку. `src/quality.py` saved current ordinals 3–9: прямые `diagnostics.quality.*` коды и непустые английские fallback; ordinals 1–2 — перенос `item.message` (проверить оба источника), 10–11 — исключения ОС (raw `str(exc)`). `src/web/routes.py:1177,1194,1422` — `items[].error`: known absent-error fallback `jobs.download.failed`, присутствующее внешнее `res.error` остаётся строкой, postprocessing остаётся полной legacy строкой. `frontend/src/i18n/messages.ts:99–125` разрешает коды из каталога и оставляет legacy строку дословно.

**Канонические L-исключения** (координаты **historical source** → saved current source из снимков; номера live могут отличаться; reason для всей строки: ветка включает raw OS/provider/third-party причину, английский самостоятельный fallback для неё не задан):

| Historical `routes.py` | Saved current `routes.py` | Основание |
|---|---|---|
| 467 | 491 | неверный cookies.txt + raw reason |
| 609, 757, 761 | 633, 781, 785 | полная `str(e)` / `error` внешнего вызова |
| 927, 937, 947, 966, 987, 1024, 1066, 1088 | 951, 961, 971, 990, 1011, 1048, 1090, 1112 | YouTube Music failure + exception |
| 1145, 1158, 1283, 1304 | 1169, 1182, 1308, 1329 | поиск/радио/плейлист + exception |
| 1307 (ТОЛЬКО с `engine.last_error`) | 1332–1334 | provider suffix; ветка без suffix — `api.errors.empty_playlist` на saved current 1336–1338 |
| 1329, 1704, 2033, 2199 | 1361, 1738, 2072, 2238 | provider/OS exception; не назначать prefix-only code |
| 1252 | 1277 | postprocessing + raw exception в `items[].error` |
| `quality.py:376,398` | `quality.py:392,414` | raw `str(exc)` в результатах apply |
| `jobs.py:131` | `jobs.py:145` | generic *unknown* exception; известные ошибки идут через `JobFailure` (снимок `:143`) |

**Подтверждённый пропуск исправлен:** historical `routes.py:514` — owned-only `unknown_browser`; сохранённый current snapshot `routes.py:538` и live до этого исправления (`src/web/routes.py:455`) всё ещё возвращали русскую строку, несмотря на контракт `api.errors.unknown_browser`. Ветка теперь возвращает descriptor с `browser` и `available`, английским fallback; `tests/test_web_api.py::test_cookies_check_selected_browser` утверждает полный DTO. После исправления live line — около 453–460. Результат targeted test: **1 passed** (`pytest -q tests/test_web_api.py::test_cookies_check_selected_browser`). В сохранённых old/current snapshot файлах строка намеренно осталась прежней — это evidence до фикса.

Исторические `routes.py:1410,1965,1169,1364` и сохранённые current `:1444,2004,1193,1396` — многострочные вызовы: сам hit не содержит ключа; только соседний body может доказать producer. `routes.py:1855` (`JSONResponse`) также требует проверить `detail` и `errors` в body; непосредственный ключ из строки не извлекается. Result `label` отдельно проверен в нынешнем `src/web/routes.py` (по `mode` выбирается `jobs.compress.audio_result` или `jobs.compress.cover_result` descriptor); широкий regex не является проверкой этой ветки. `normalize.py` не имеет найденных строк в обоих снимках: это не доказательство отсутствия copy или корректности DTO. Данные `path`, `field`, `kind`, `cause`, provider names и прочие discriminators не должны попадать в перевод, даже если стоят рядом с message.

## Машинно-разбираемое приложение: полный ordinal-ledger

Схема каждой строки: `snapshot|path|K ordinal ranges` (1-based **номер записи в snapshot**, интервал включительно); **все остальные ordinals в указанном path являются U**. Диапазоны файлов задают каждый ordinal ровно один раз; сверять исходный source text непосредственно по соответствующему snapshot. Пустой K = все U. Это lossless partition входных строк, но **не** заполненная occurrence-level semantic классификация: U перечислены явно именно как непроверенные. `Hf`=`localization-frontend-hits.txt`, `Cf`=`current-frontend-wide.txt`, `Hb`=`localization-backend-hits.txt`, `Cb`=`current-backend-wide.txt`; `F/`=`frontend/src/`, `W/`=`src/web/`, `S/`=`src/`. Колонки `start-end` задают все входные записи данного файла; `K` подтверждён ключами в конкретной строке. Один входной hit — одна запись даже если в ней несколько литералов.

```text
snapshot|path|start-end|K
Hf|F/views/DiscoverScreen.tsx|1-5|-
Hf|F/views/settings/YtmCard.tsx|6-59|-
Hf|F/views/settings/parts.tsx|60-72|-
Hf|F/App.tsx|73|-
Hf|F/views/SearchScreen.tsx|74-139|-
Hf|F/views/SettingsScreen.tsx|140-173|-
Hf|F/lib/ops.tsx|174|-
Hf|F/views/MiscScreen.tsx|175-207|-
Hf|F/views/MenuScreen.tsx|208-222|-
Hf|F/nav.ts|223-232|-
Hf|F/hooks/useTheme.ts|233|-
Hf|F/views/library/TracksTab.tsx|234-243|-
Hf|F/views/QualityScreen.tsx|244-289|-
Hf|F/views/LibraryScreen.tsx|290-362|-
Hf|F/lib/tags.ts|363-365|-
Hf|F/features/editor/useMetaSources.ts|366-377|-
Hf|F/hooks/useHashRoute.ts|378|-
Hf|F/views/library/ArtistsTab.tsx|379-382|-
Hf|F/features/ytm/detail.tsx|383-414|-
Hf|F/components/PreviewButton.tsx|415-418|-
Hf|F/features/editor/TrackEditorDialog.tsx|419-422|-
Hf|F/features/editor/BatchEditorDialog.tsx|423-445|-
Hf|F/stores/downloads.ts|446-449|-
Hf|F/lib/jobs.ts|450-452|-
Hf|F/lib/hotkeys.ts|453|-
Hf|F/views/library/trackDetail.tsx|454-473|-
Hf|F/lib/toast.tsx|474-477|-
Hf|F/features/ytm/badges.tsx|478-484|-
Hf|F/components/Tabbar.tsx|485-486|-
Hf|F/views/library/useYtData.ts|487-493|-
Hf|F/views/RecommendScreen.tsx|494-519|-
Hf|F/components/CommandPalette.tsx|520-524|-
Hf|F/views/library/AlbumsTab.tsx|525-529|-
Hf|F/views/library/albumDetail.tsx|530-580|-
Hf|F/lib/api.ts|581-597|-
Hf|F/views/library/PlaylistsTab.tsx|598-600|-
Hf|F/views/library/Cards.tsx|601-624|-
Hf|F/views/library/Inbox.tsx|625-641|-
Hf|F/components/dialogs/KeymapDialog.tsx|642-647|-
Hf|F/stores/overlays.ts|648|-
Hf|F/views/library/libUtils.ts|649-651|-
Hf|F/features/ytm/settings.ts|652-654|-
Hf|F/features/editor/TrackEditor.tsx|655-674|-
Hf|F/components/PlayerBar.tsx|675-677|-
Hf|F/features/ytm/download.ts|678-681|-
Hf|F/features/ytm/cards.tsx|682-693|-
Hf|F/lib/format.ts|694|-
Hf|F/stores/player.ts|695-696|-
Hf|F/features/ytm/rows.tsx|697-708|-
Hf|F/components/MoreMenu.tsx|709|-
Hf|F/components/ui/SegControl.tsx|710-713|-
Hf|F/components/DownloadsDock.tsx|714-720|-
Hf|F/components/ui/TrackRow.tsx|721-723|-
Hf|F/components/dialogs/DialogProvider.tsx|724-749|-
Hf|F/components/Topbar.tsx|750-758|-
Hf|F/components/ui/CollapsibleGroup.tsx|759-760|-
Hf|F/components/ui/ProgressBar.tsx|761-762|-
Hf|F/components/AudioPlayer.tsx|763-767|-
Hf|F/components/ui/QueueItem.tsx|768-771|-
Hf|F/components/ui/Cover.tsx|772|-
Hf|F/components/ui/EmptyState.tsx|773-774|-
Hf|F/components/ui/Pipeline.tsx|775-778|-
Hb|S/quality.py|1-11|-
Hb|W/routes.py|12-163|-
Hb|W/jobs.py|164|-
Cf|F/views/DiscoverScreen.tsx|1-3|3
Cf|F/views/SettingsScreen.tsx|4-43|6,14-15,17,19,24,27-29,31,33,36-37,39-40
Cf|F/views/QualityScreen.tsx|44-93|50-52,59,61,63,66,69-72,74-82,85-87,89-93
Cf|F/views/SearchScreen.tsx|94-155|95-97,106-107,109,115,117-118,122,125,128,137,139-140,142-144,147,149,155
Cf|F/views/library/TracksTab.tsx|156-165|164
Cf|F/views/library/ArtistsTab.tsx|166-169|169
Cf|F/views/library/trackDetail.tsx|170-190|178-179,183-184,188
Cf|F/views/library/useYtData.ts|191-197|-
Cf|F/views/library/Cards.tsx|198-221|216-217,220-221
Cf|F/nav.ts|222|-
Cf|F/views/library/Inbox.tsx|223-240|-
Cf|F/views/MenuScreen.tsx|241-255|250
Cf|F/views/library/albumDetail.tsx|256-307|261-265,267-269,271,278,280,283-286,297-299,301-307
Cf|F/App.tsx|308|-
Cf|F/stores/downloads.ts|309-322|311,313-314,317,319-321
Cf|F/views/library/AlbumsTab.tsx|323-327|326
Cf|F/stores/overlays.ts|328|-
Cf|F/i18n/messages.ts|329-343|-
Cf|F/stores/player.ts|344-345|-
Cf|F/features/editor/useMetaSources.ts|346-358|355,357-358
Cf|F/components/PreviewButton.tsx|359-363|360-361
Cf|F/features/editor/BatchEditorDialog.tsx|364-386|375,377,380-383,385
Cf|F/features/editor/runMetaflow.ts|387|-
Cf|F/components/Topbar.tsx|388-396|392-395
Cf|F/components/MoreMenu.tsx|397|397
Cf|F/components/AudioPlayer.tsx|398-402|402
Cf|F/features/ytm/detail.tsx|403-435|414,417,421,424-425,430,434
Cf|F/features/editor/TrackEditor.tsx|436-456|442,444,447-450,452-453,455
Cf|F/i18n/index.ts|457|-
Cf|F/views/library/PlaylistsTab.tsx|458-460|-
Cf|F/features/editor/TrackEditorDialog.tsx|461-465|-
Cf|F/lib/ops.tsx|466-467|-
Cf|F/i18n/production.typecheck.ts|468|-
Cf|F/components/DownloadsDock.tsx|469-476|472-476
Cf|F/components/dialogs/KeymapDialog.tsx|477-483|482
Cf|F/components/Tabbar.tsx|484-485|484-485
Cf|F/views/RecommendScreen.tsx|486-516|501,503,505,510,512-514
Cf|F/features/ytm/badges.tsx|517-523|517-523
Cf|F/lib/tags.ts|524-526|-
Cf|F/components/CommandPalette.tsx|527-531|527-529
Cf|F/views/LibraryScreen.tsx|532-603|542-543,546,549-550,554,557,561-562,564,566,568,570,573-574,576,579-587,593-594,596-599
Cf|F/lib/jobs.ts|604-616|606,609,613
Cf|F/views/library/libUtils.ts|617-619|-
Cf|F/lib/toast.tsx|620-624|-
Cf|F/views/settings/parts.tsx|625-637|-
Cf|F/features/ytm/download.ts|638-645|-
Cf|F/lib/hotkeys.ts|646|-
Cf|F/hooks/useTheme.ts|647|-
Cf|F/components/ui/EmptyState.tsx|648-649|-
Cf|F/lib/format.ts|650|-
Cf|F/components/ui/ProgressBar.tsx|651-653|653
Cf|F/lib/api.ts|654-677|-
Cf|F/features/ytm/cards.tsx|678-689|679-680,682-686,688
Cf|F/components/dialogs/DialogProvider.tsx|690-716|698,700,713
Cf|F/hooks/useHashRoute.ts|717|-
Cf|F/components/ui/CollapsibleGroup.tsx|718-719|-
Cf|F/components/ui/Cover.tsx|720|-
Cf|F/views/settings/YtmCard.tsx|721-781|730,733,736,738-739,741,743,745-753,756,759,762,768-769
Cf|F/components/ui/TrackRow.tsx|782-784|782
Cf|F/components/ui/SegControl.tsx|785-788|-
Cf|F/views/MiscScreen.tsx|789-822|796-799,801-803,805-808,811,813,817-820
Cf|F/components/ui/Pipeline.tsx|823-827|825-826
Cf|F/features/ytm/rows.tsx|828-839|829-832,835-837
Cf|F/components/PlayerBar.tsx|840-842|841-842
Cf|F/features/ytm/settings.ts|843-845|-
Cf|F/features/ytm/types.ts|846|-
Cf|F/components/ui/QueueItem.tsx|847-853|852-853
Cb|S/quality.py|1-11|3-9
Cb|W/routes.py|12-165|15,21-22,24-25,27,29,31,33,35,37-39,41-42,46-48,50-59,63,65-69,75,77,80,84,86-87,89-91,97,99,102-103,105-110,114,116-117,119-127,129,131-132,134-137,139-155,159-165
Cb|W/jobs.py|166-167|-
```

Пример машинной проверки приложения: развернуть `start-end` для каждого snapshot/path, убедиться, что `K ⊆ start-end`, каждому ordinal соответствует ровно одна строка снимка, `U = all - K`; отсутствие строки в K не значит «задача закрыта». Для точной корреляции использовать `Counter((path, source.strip()))` и хранить отдельные `old_count/current_count` для каждого identity. У этого отчёта **нет** индивидуальной таблицы `old→new` для 942 исторических occurrences: доказательная база для неё отсутствует. `K` извлекается из сохранённой строки, *не* из соседнего импорта. Расхождение live скана не покрыто приложением.

## Свидетельства проверок и решение

Из сегодняшнего рабочего дерева, без полного прогона suites: `python scripts/check_locales.py` → `Locale catalogs validated`; `python scripts/check_copy.py` → `Hardcoded-copy guardrail passed: no scoped candidates found`; `cd frontend && npm run check:i18n-keys` → exit 0; `python -m pytest tests/test_messages.py tests/test_job_catalogs.py tests/test_locale_catalogs.py tests/test_copy_guardrails.py -q` → **40 passed in 1.32s**. Более ранний `localization-task-5a-report.md:46–50` записывает 35 frontend файлов / 236 тестов и сборку, но это историческое свидетельство, **не** сегодняшний прогон. Проверка copy намеренно ограничена JSX-атрибутами/текстом и связанными вызовами уведомлений, backend проверяет импортированные `message()` и синтаксис ключа; успешный guardrail не классифицирует wide-scan строки. Полные suites не запускались: обнаруженное расхождение owned-only `unknown_browser` — конкретный повод для адресного теста разработчиком, но этому аудиту запрещено менять продукт.

Вывод и ТЗ для следующего исполнителя: (1) сохранить live rerun и вернуть оба saved-current снимка к одному неизменному commit/tree; (2) для **каждого** U в ordinal-ledger построить отдельную запись `(snapshot,path,line,source,identity,occurrence-index,class,key-or-reason,current-source-location)` с точным английским/русским кодом или замкнутым data/legacy основанием; отдельно отметить все old-only/current-only и однозначно/неоднозначно изменённые строки; (3) исправить либо аргументированно исключить `unknown_browser` в ветке `src/web/routes.py` с повторным тестом; (4) вручную проверить соседние выражения многострочных вызовов, импортные ложные срабатывания, result labels, raw provider источники, HTTP/job/diagnostic сериализацию. Пока 778+164 исторических строк и 586+64 строк saved current остаются не аттестованы семантически, **приёмка exhaustive audit невозможна**.

```text
producer (routes/health/lint/quality) → HTTP detail / job name+progress+error / diagnostic message
  → API/SSE/polling serialization → i18n.resolveMessage → UI
provider/path/tag/ID ───────────────────────────────────────→ UI verbatim (not catalog)
```
