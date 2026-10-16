/* API-клиент: fetch + разбор строковых и descriptor detail/errors FastAPI. */
import type { RenderableMessage } from "../i18n/messages";

export class ApiError extends Error {
  readonly status: number;
  readonly fields: Record<string, RenderableMessage> | null;
  readonly renderableMessage: RenderableMessage;

  constructor(renderableMessage: RenderableMessage, fields?: Record<string, RenderableMessage> | null);
  constructor(status: number, renderableMessage: RenderableMessage, fields?: Record<string, RenderableMessage> | null);
  constructor(
    statusOrMessage: number | RenderableMessage,
    messageOrFields: RenderableMessage | Record<string, RenderableMessage> | null = null,
    fields: Record<string, RenderableMessage> | null = null,
  ) {
    const hasStatus = typeof statusOrMessage === "number";
    const status = hasStatus ? statusOrMessage : 0;
    const renderableMessage = (hasStatus ? messageOrFields : statusOrMessage) as RenderableMessage;
    const normalizedFields = (hasStatus ? fields : messageOrFields) as Record<string, RenderableMessage> | null;
    super(readableMessage(renderableMessage));
    this.name = "ApiError";
    this.status = status;
    this.fields = normalizedFields;
    this.renderableMessage = renderableMessage;
  }
}

function isStructuredMessage(value: unknown): value is Exclude<RenderableMessage, string> {
  return Boolean(value) && typeof value === "object" && typeof (value as { code?: unknown }).code === "string";
}

function normalizeMessage(value: unknown, fallback: string): RenderableMessage {
  if (typeof value === "string") return value;
  if (isStructuredMessage(value)) return value;
  if (value && typeof value === "object" && typeof (value as { message?: unknown }).message === "string") {
    return (value as { message: string }).message;
  }
  return fallback;
}

function normalizeFields(value: unknown): Record<string, RenderableMessage> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const fields: Record<string, RenderableMessage> = {};
  for (const [field, error] of Object.entries(value)) {
    if (typeof error === "string" || isStructuredMessage(error)) fields[field] = error;
  }
  return Object.keys(fields).length ? fields : null;
}

function readableMessage(value: RenderableMessage): string {
  if (typeof value === "string") return value;
  return typeof value.message === "string" && value.message.trim() ? value.message : "Something went wrong";
}

export type QueryParams = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, params?: QueryParams): string {
  if (!params) return path;
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) q.set(k, String(v));
  }
  const s = q.toString();
  if (!s) return path;
  return path + (path.includes("?") ? "&" : "?") + s;
}

export async function request<T = unknown>(method: string, path: string, body?: unknown, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const opts: RequestInit = { ...init, method, headers };
  if (body !== undefined) {
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail: RenderableMessage = `${res.status} ${res.statusText}`;
    let fields: Record<string, RenderableMessage> | null = null;
    try {
      const j = await res.json();
      if (j && typeof j === "object") {
        detail = normalizeMessage((j as { detail?: unknown }).detail, detail);
        fields = normalizeFields((j as { errors?: unknown }).errors);
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail, fields);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? res.json() : res) as Promise<T>;
}

export function get<T = unknown>(path: string, params?: QueryParams, method = "GET", init?: RequestInit): Promise<T> {
  return request<T>(method, buildUrl(path, params), undefined, init);
}

export function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, body ?? {});
}

export function put<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request<T>("PUT", path, body ?? {});
}

export function del<T = unknown>(path: string, params?: QueryParams): Promise<T> {
  return request<T>("DELETE", buildUrl(path, params));
}

export function coverUrl(path: string): string {
  return `/api/cover?path=${encodeURIComponent(path)}`;
}

export const api = { request, get, post, put, del, coverUrl };
