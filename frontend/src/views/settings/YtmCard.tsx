/* Карточка «YouTube Music»: статус, куки из браузера (профили, поиск
 * аккаунтов со страничными каналами, извлечение), свитчеры/сегменты формы —
 * пропсами из SettingsScreen, проверки YouTube и ручные способы — в details. */
import { useCallback, useEffect, useState } from "react";
import { del, get, post } from "../../lib/api";
import { toast } from "../../lib/toast";
import { startJob } from "../../lib/jobs";
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { SegControl } from "../../components/ui/SegControl";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../../i18n/messages";
import { Card, Details, Field, SwitchRow } from "./parts";
import { useTranslation } from "react-i18next";

interface YtmBrowserEntry {
  name: string;
  profiles?: string[];
}

interface AccountCandidate {
  authuser: number;
  likes: number;
  page_id?: string;
  account?: { name?: string; handle?: string };
}

export function YtmCard({
  noClips,
  onNoClips,
  searchSource,
  onSearchSource,
  feedback,
  onFeedback,
  cookies,
}: {
  noClips: boolean;
  onNoClips: (v: boolean) => void;
  searchSource: string;
  onSearchSource: (v: string) => void;
  feedback: string;
  onFeedback: (v: string) => void;
  /* YouTube-часть (18+/вход/cookies.txt) — состояние SettingsScreen. */
  cookies: {
    ytBrowser: string;
    onYtBrowser: (v: string) => void;
    browsers: string[];
    set: boolean;
    file: string;
    onCookiesSaved: (file: string) => void;
    onCookiesDeleted: () => void;
  };
}) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<{ connected?: boolean; mode?: string; account?: { name?: string }; account_error?: string } | null>(null);
  const [browsers, setBrowsers] = useState<YtmBrowserEntry[]>([]);
  const [browser, setBrowser] = useState("");
  const [profile, setProfile] = useState("");
  const [accounts, setAccounts] = useState<AccountCandidate[] | null>(null);
  const [account, setAccount] = useState("");
  const [pageId, setPageId] = useState("");
  const [accountsOut, setAccountsOut] = useState<{ pct: number; msg: RenderableMessage } | null>(null);
  const [extractOut, setExtractOut] = useState<{ pct: number; msg: RenderableMessage } | null>(null);
  const [headers, setHeaders] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [authOut, setAuthOut] = useState<{ pct: number; msg: RenderableMessage; url?: string } | null>(null);
  const [busy, setBusy] = useState<string>("");

  const statusRefresh = useCallback(async () => {
    let st = null;
    try {
      st = await get<{ connected?: boolean; mode?: string; account?: { name?: string }; account_error?: string }>("/api/ytmusic/status");
    } catch {
      /* статус остаётся «не подключено» */
    }
    setStatus(st);
  }, []);

  useEffect(() => {
    void statusRefresh();
    get<{ browsers?: YtmBrowserEntry[] }>("/api/ytmusic/auth/browsers")
      .then((data) => setBrowsers(data.browsers || []))
      .catch(() => setBrowsers([]));
  }, [statusRefresh]);

  const profiles = browsers.find((b) => b.name === browser)?.profiles || [];
  const hasProfile = profiles.length > 0;

  /* «Найти аккаунты»: личные профили + страничные brand-каналы. */
  const findAccounts = async () => {
    if (!browser) return;
    setBusy("accounts");
    setAccountsOut({ pct: 0, msg: "" });
    try {
      const res = await startJob<{ candidates?: AccountCandidate[] }>(
        "/api/ytmusic/auth/browser/accounts",
        { browser, profile: hasProfile ? profile : null },
        { onProgress: (d) => setAccountsOut({ pct: d.percent || 0, msg: d.message ?? d.msg ?? "" }) },
      );
      const cands = res.candidates || [];
      setAccounts(cands);
      setAccount("");
      setAccountsOut({
        pct: 100,
        msg: cands.length
          ? { code: "settings.ytm.browser_accounts.found", params: { count: cands.length } }
          : { code: "settings.ytm.browser_accounts.not_recognized" },
      });
      if (!cands.length) toast({ code: "settings.ytm.browser_accounts.not_found" }, "error");
    } catch (e) {
      setAccountsOut({ pct: 0, msg: "" });
      toast(asRenderableMessage(e), "error");
    } finally {
      setBusy("");
    }
  };

  /* «Извлечь из браузера»: с выбранным аккаунтом (authuser/page_id) или фолбэк. */
  const extract = async () => {
    if (!browser) return;
    setBusy("extract");
    setExtractOut({ pct: 0, msg: "" });
    let selAuth: number | null = null;
    let selPage: string | null = null;
    if (accounts && account) {
      const sep = account.indexOf(":");
      if (sep === -1) selAuth = Number(account);
      else {
        selAuth = Number(account.slice(0, sep));
        selPage = account.slice(sep + 1);
      }
    }
    try {
      const res = await startJob<{ authuser?: number; account?: { name?: string } }>(
        "/api/ytmusic/auth/browser/extract",
        {
          browser,
          profile: hasProfile ? profile : null,
          authuser: selAuth,
          page_id: selPage || pageId.trim() || null,
        },
        { onProgress: (d) => setExtractOut({ pct: d.percent || 0, msg: d.message ?? d.msg ?? "" }) },
      );
      const acc: RenderableMessage = res.account?.name || { code: "settings.ytm.browser_accounts.unknown" };
      setExtractOut({ pct: 100, msg: { code: "settings.ytm.browser_extract.done", params: { account: acc, authuser: res.authuser ?? "" } } });
      toast({ code: "settings.ytm.browser_extract.saved", params: { account: acc } });
      await statusRefresh();
    } catch (e) {
      setExtractOut({ pct: 0, msg: "" });
      toast(asRenderableMessage(e), "error");
    } finally {
      setBusy("");
    }
  };

  const removeAuth = async () => {
    const ok = await getDialogs().confirm(
      t("settings.ytm.remove_auth.confirm"),
      { defaultOk: false, okTitle: t("settings.delete") },
    );
    if (!ok) return;
    try {
      await del("/api/ytmusic/auth");
      toast(t("settings.ytm.remove_auth.done"));
      await statusRefresh();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  };

  const saveHeaders = async () => {
    if (!headers.trim()) {
      toast(t("settings.ytm.headers_required"), "error");
      return;
    }
    setBusy("headers");
    try {
      await post("/api/ytmusic/auth/browser", { headers_raw: headers });
      toast(t("settings.ytm.auth_saved"));
      setHeaders("");
      await statusRefresh();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    } finally {
      setBusy("");
    }
  };

  const oauth = async () => {
    if (!clientId.trim() || !clientSecret.trim()) {
      toast(t("settings.ytm.oauth_required"), "error");
      return;
    }
    setBusy("oauth");
    setAuthOut({ pct: 0, msg: "" });
    try {
      await startJob(
        "/api/ytmusic/auth/oauth",
        { client_id: clientId.trim(), client_secret: clientSecret.trim() },
        {
          onProgress: (d) => {
            setAuthOut({ pct: d.percent || 0, msg: d.message ?? d.msg ?? "", url: (d as { auth_url?: string }).auth_url });
          },
        },
      );
      setAuthOut({ pct: 100, msg: { code: "settings.ytm.oauth_done" } });
      toast(t("settings.ytm.oauth_connected"));
      await statusRefresh();
    } catch (e) {
      setAuthOut({ pct: 0, msg: "" });
      toast(asRenderableMessage(e), "error");
    } finally {
      setBusy("");
    }
  };

  return (
    <Card title="YouTube Music" sub={t("settings.ytm.subtitle")}>
      <Field
        label={t("settings.ytm.status.label")}
        hint={t("settings.ytm.status.hint")}
      >
        <div className="row">
          <span className="set-hint">
            {!status || !status.connected
              ? t("settings.ytm.status.disconnected")
              : t("settings.ytm.status.connected", { mode: status.mode === "oauth" ? "OAuth" : t("settings.ytm.status.browser_headers") })}
            {status?.connected && status.account?.name ? ` — ${status.account.name}` : null}
            {status?.connected && status.account_error ? <span className="tag bad">{t("settings.ytm.status.login_failed")}</span> : null}
          </span>
          <button className="ghost small-btn" type="button" onClick={() => void removeAuth()}>{t("settings.delete")}</button>
        </div>
      </Field>

      <Field
        label={t("settings.ytm.browser_cookies.label")}
        hint={t("settings.ytm.browser_cookies.hint")}
      >
        <div className="set-filecol">
          <div className="row">
            <select
              aria-label={t("settings.ytm.browser_cookies.browser")}
              value={browser}
              disabled={!browsers.length}
              onChange={(e) => {
                setBrowser(e.target.value);
                setProfile("");
                setAccounts(null);
                setAccount("");
              }}
            >
              {!browsers.length ? <option value="">{t("settings.ytm.browser_cookies.not_found")}</option> : null}
              {browsers.map((b) => (
                <option key={b.name} value={b.name}>{b.name}</option>
              ))}
            </select>
            <select
              aria-label={t("settings.ytm.browser_cookies.profile")}
              value={profile}
              disabled={!hasProfile}
              onChange={(e) => {
                setProfile(e.target.value);
                setAccounts(null);
                setAccount("");
              }}
            >
              {!hasProfile ? <option value="">{t("settings.ytm.browser_cookies.profile_not_found")}</option> : null}
              {profiles.map((p) => (
                <option key={p} value={p}>{p === "Default" ? t("settings.ytm.browser_cookies.default_profile") : p}</option>
              ))}
            </select>
            <button
              className="ghost small-btn"
              type="button"
              disabled={!hasProfile || busy === "accounts"}
              onClick={() => void findAccounts()}
            >
              {t("settings.ytm.browser_accounts.action")}
            </button>
            <button
              className="ghost small-btn"
              type="button"
              disabled={!browser || busy === "extract"}
              onClick={() => void extract()}
            >
              {t("settings.ytm.browser_extract.action")}
            </button>
          </div>
          <div className="row" style={{ marginTop: 6 }}>
            <select
              aria-label={t("settings.ytm.browser_accounts.label")}
              value={account}
              disabled={!accounts}
              onChange={(e) => setAccount(e.target.value)}
            >
              <option value="">{t("settings.ytm.browser_accounts.auto")}</option>
              {(accounts || []).map((candidate) => {
                const value = candidate.page_id ? `${candidate.authuser}:${candidate.page_id}` : `${candidate.authuser}`;
                const label =
                  `${candidate.account?.name || t("settings.ytm.browser_accounts.unnamed")}` +
                  (candidate.account?.handle ? ` (${candidate.account.handle})` : "") +
                  (candidate.page_id ? ` (${t("settings.ytm.browser_accounts.brand")})` : "") +
                  ` — ${t("settings.ytm.browser_accounts.likes", { count: candidate.likes, authuser: candidate.authuser })}`;
                return <option key={value} value={value}>{label}</option>;
              })}
            </select>
          </div>
          <input
            type="text"
            placeholder={t("settings.ytm.browser_accounts.page_id_placeholder")}
            value={pageId}
            onChange={(e) => setPageId(e.target.value)}
          />
          {extractOut != null ? <ProgressBar pct={extractOut.pct} msg={extractOut.msg} /> : null}
          {accountsOut != null ? <ProgressBar pct={accountsOut.pct} msg={accountsOut.msg} /> : null}
        </div>
      </Field>

      <SwitchRow text={t("settings.ytm.no_clips")} checked={noClips} onChange={onNoClips} />

      <Field label={t("search.source")}>
        <SegControl
          options={[
            ["youtube_music", "YouTube Music"],
            ["youtube", "YouTube"],
          ]}
          current={searchSource as "youtube_music" | "youtube"}
          onChange={(v) => onSearchSource(v)}
        />
      </Field>
      <div className="set-hint">
        {t("settings.ytm.search_source_hint")}
      </div>

      <Field label={t("settings.ytm.feedback.label")}>
        <SegControl
          options={[
            ["like", t("recommend.apply.like")],
            ["library", t("recommend.apply.library")],
          ]}
          current={feedback as "like" | "library"}
          onChange={(v) => onFeedback(v)}
        />
      </Field>
      <div className="set-hint">
        {t("settings.ytm.feedback.hint")}
      </div>

      <Details title={t("settings.ytm.checks.title")}>
        <Field label={t("settings.ytm.checks.browser")} hint={t("settings.ytm.checks.browser_hint")}>
          <select value={cookies.ytBrowser} onChange={(e) => cookies.onYtBrowser(e.target.value)}>
            {(cookies.browsers || []).map((b: string) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </Field>
        <Field label={t("settings.ytm.checks.status")}>
          <span className="set-hint">
            {cookies.set
              ? t("settings.ytm.checks.cookies_set", { file: String(cookies.file || "").split("/").pop() || "cookies.txt" })
              : t("settings.ytm.checks.cookies_unset")}
          </span>
        </Field>
        <Field label="cookies.txt" hint={t("settings.ytm.checks.cookies_hint")}>
          <div className="set-filecol">
            <input
              type="file"
              accept=".txt,text/plain"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                try {
                  const content = await f.text();
                  const res = await post<{ path?: string; lines?: number }>("/api/settings/cookies", { content });
                  cookies.onCookiesSaved(res.path || "");
                  e.target.value = "";
                  toast(t("settings.ytm.checks.cookies_saved", { count: res.lines || 0 }));
                } catch (err) {
                  toast(asRenderableMessage(err), "error");
                }
              }}
            />
            <div className="row">
              <button className="ghost small-btn" type="button" onClick={() => void saveCookiesDelete(cookies)}>
                {t("settings.delete")}
              </button>
            </div>
          </div>
        </Field>
        <YtChecks browser={cookies.ytBrowser} />
      </Details>

      <Details title={t("settings.ytm.alternatives.title")}>
        <div className="set-hint" style={{ marginBottom: 6 }}>
          {t("settings.ytm.alternatives.hint")}
        </div>
        <Field
          label={t("settings.ytm.alternatives.headers_label")}
          hint={t("settings.ytm.alternatives.headers_hint")}
        >
          <div className="set-filecol">
            <textarea
              rows={4}
              placeholder={"Cookie: …\nX-Goog-AuthUser: 0\nAuthorization: …"}
              style={{ fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
              value={headers}
              onChange={(e) => setHeaders(e.target.value)}
            />
            <div className="row">
              <button className="ghost small-btn" type="button" disabled={busy === "headers"} onClick={() => void saveHeaders()}>
                {t("settings.ytm.alternatives.headers_action")}
              </button>
            </div>
          </div>
        </Field>
        <Field label={t("settings.ytm.alternatives.oauth_label")}>
          <div className="set-filecol">
            <input type="text" placeholder="client_id (YouTube Data API)" value={clientId} onChange={(e) => setClientId(e.target.value)} />
            <input
              type="password"
              autoComplete="off"
              placeholder="client_secret"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
            />
            <div className="row">
              <button className="ghost small-btn" type="button" disabled={busy === "oauth"} onClick={() => void oauth()}>
                {t("settings.ytm.alternatives.oauth_action")}
              </button>
            </div>
            {authOut != null ? (
              <>
                <ProgressBar pct={authOut.pct} msg={authOut.msg} />
                {authOut.url ? (
                  <div className="set-hint" style={{ marginTop: 8 }}>
                    {t("settings.ytm.alternatives.oauth_link")}{" "}
                    <a href={authOut.url} target="_blank" rel="noopener">{authOut.url}</a>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>
        </Field>
      </Details>
    </Card>
  );
}

async function saveCookiesDelete(cookies: { onCookiesDeleted: () => void }): Promise<void> {
  const { default: i18n } = await import("../../i18n");
  const ok = await getDialogs().confirm(i18n.t("settings.ytm.checks.cookies_delete_confirm"), {
    defaultOk: false,
    okTitle: i18n.t("settings.delete"),
  });
  if (!ok) return;
  try {
    await del("/api/settings/cookies");
    cookies.onCookiesDeleted();
    toast(i18n.t("settings.ytm.checks.cookies_deleted"));
  } catch (e) {
    toast(asRenderableMessage(e), "error");
  }
}

/* «Проверить вход» и «Проверить 18+» — результаты под кнопками. */
function YtChecks({ browser }: { browser: string }) {
  const { t } = useTranslation();
  type LoginRow = { browser: string; status?: string; auth?: boolean; cookies?: number; error?: string };
  type AgeRow = { source: string; ok?: boolean; reason?: string; title?: string; error?: string };
  const [login, setLogin] = useState<
    | { state: "loading" }
    | { state: "result"; browser?: string; rows: LoginRow[] }
    | { state: "error"; message: RenderableMessage }
    | null
  >(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [age, setAge] = useState<
    | { state: "loading" }
    | { state: "result"; verified: boolean; rows: AgeRow[] }
    | { state: "error"; message: RenderableMessage }
    | null
  >(null);
  const [ageBusy, setAgeBusy] = useState(false);

  const checkLogin = async () => {
    setLoginBusy(true);
    setLogin({ state: "loading" });
    try {
      const res = await post<{ browser?: string; browsers?: { browser: string; status?: string; auth?: boolean; cookies?: number; error?: string }[] }>(
        "/api/settings/cookies/check",
        { browser },
      );
      setLogin({ state: "result", browser: res.browser, rows: res.browsers || [] });
    } catch (e) {
      setLogin({ state: "error", message: asRenderableMessage(e) });
    } finally {
      setLoginBusy(false);
    }
  };

  const checkAge = async () => {
    setAgeBusy(true);
    setAge({ state: "loading" });
    try {
      const res = await post<{ verified_18?: boolean; checks?: { source: string; ok?: boolean; reason?: string; title?: string; error?: string }[] }>(
        "/api/settings/cookies/verify-age",
        {},
      );
      setAge({ state: "result", verified: !!res.verified_18, rows: res.checks || [] });
    } catch (e) {
      setAge({ state: "error", message: asRenderableMessage(e) });
    } finally {
      setAgeBusy(false);
    }
  };

  return (
    <>
      <button className="ghost small-btn" type="button" disabled={loginBusy} onClick={() => void checkLogin()}>
        {t("settings.ytm.checks.login_action")}
      </button>
      <div className="set-hint" style={{ margin: "6px 0 0" }}>
        {login?.state === "loading" ? t("settings.ytm.checks.login_reading") : null}
        {login?.state === "error" ? resolveMessage(login.message) : null}
        {login?.state === "result" ? <LoginResult rows={login.rows} browser={login.browser ?? browser} /> : null}
        {!login ? t("settings.ytm.checks.login_hint") : null}
      </div>
      <div style={{ height: 8 }} />
      <button className="ghost small-btn" type="button" disabled={ageBusy} onClick={() => void checkAge()}>
        {t("settings.ytm.checks.age_action")}
      </button>
      <div className="set-hint" style={{ margin: "6px 0 0" }}>
        {age?.state === "loading" ? t("settings.ytm.checks.age_reading") : null}
        {age?.state === "error" ? resolveMessage(age.message) : null}
        {age?.state === "result" ? <AgeResult verified={age.verified} rows={age.rows} /> : null}
        {!age ? t("settings.ytm.checks.age_hint") : null}
      </div>
    </>
  );
}

function LoginResult({ rows, browser }: { rows: { browser: string; status?: string; auth?: boolean; cookies?: number; error?: string }[]; browser: string }) {
  const { t } = useTranslation();
  const good = rows.filter((row) => row.auth).map((row) => row.browser);
  return <>
    {rows.map((row) => (
      <div className="row" style={{ gap: 8, marginBottom: 4 }} key={row.browser}>
        <b>{row.browser}</b>
        {row.status === "error" ? <span className="tag bad">{t("settings.ytm.checks.error")}</span>
          : row.status === "empty" ? <span className="tag warn">{t("settings.ytm.checks.empty")}</span>
            : row.auth ? <span className="tag ok">{t("settings.ytm.checks.signed_in")}</span> : <span className="tag warn">{t("settings.ytm.checks.signed_out")}</span>}
        <span className="muted">{row.status === "error" ? row.error : row.status === "empty" ? t("settings.ytm.checks.no_cookies") : t("settings.ytm.checks.cookie_count", { count: row.cookies ?? 0 })}</span>
      </div>
    ))}
    <div className="set-hint">{good.length ? t("settings.ytm.checks.login_available", { browsers: good.join(", ") }) : t("settings.ytm.checks.login_unavailable", { browser })}</div>
  </>;
}

function AgeResult({ verified, rows }: { verified: boolean; rows: { source: string; ok?: boolean; reason?: string; title?: string; error?: string }[] }) {
  const { t } = useTranslation();
  return <>
    <div className="row" style={{ gap: 8, marginBottom: 6 }}>
      <b>{t("settings.ytm.checks.age_label")}</b>
      {verified ? <span className="tag ok">{t("settings.ytm.checks.age_verified")}</span> : <span className="tag bad">{t("settings.ytm.checks.age_unverified")}</span>}
    </div>
    {rows.map((row) => (
      <div className="row" style={{ gap: 8, marginBottom: 4 }} key={row.source}>
        <b>{row.source}</b>
        {row.ok ? <span className="tag ok">{t("settings.ytm.checks.ok")}</span>
          : row.reason === "gate" ? <span className="tag warn">{t("settings.ytm.checks.signed_out")}</span>
            : row.reason === "blocked" ? <span className="tag bad">{t("settings.ytm.checks.age_unverified")}</span>
              : <span className="tag bad">{t("settings.ytm.checks.error")}</span>}
        {row.ok ? <span className="muted">{row.title}</span> : row.reason === "other" ? <span className="muted">{row.error}</span> : null}
      </div>
    ))}
  </>;
}
