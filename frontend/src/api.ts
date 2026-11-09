const KEY_STORAGE = "atlas.apiKey";

export function getApiKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function setApiKey(key: string): void {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage unavailable: key lives for this session only */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Params = Record<string, string | number | boolean | undefined | null>;

export async function api<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const url = `/api${path}${qs.size ? `?${qs}` : ""}`;
  const headers = new Headers(init?.headers);
  const key = getApiKey();
  if (key) headers.set("X-API-Key", key);
  if (init?.body) headers.set("Content-Type", "application/json");
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, `${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const post = <T>(path: string, body: unknown) =>
  api<T>(path, undefined, { method: "POST", body: JSON.stringify(body) });
