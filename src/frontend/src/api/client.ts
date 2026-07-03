export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const AUTH_PATHS = ['/login', '/register'];

function isAuthPage(): boolean {
  return AUTH_PATHS.some((p) => window.location.pathname.startsWith(p));
}

interface RequestOptions {
  method?: string;
  json?: unknown;
  body?: BodyInit;
  signal?: AbortSignal;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined = opts.body;
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.json);
  }

  const res = await fetch(`/api/v1${path}`, {
    method: opts.method ?? 'GET',
    credentials: 'same-origin',
    headers,
    body,
    signal: opts.signal,
  });

  if (res.status === 401 && !isAuthPage()) {
    window.location.assign('/login');
    throw new ApiError(401, 'Not authenticated');
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === 'string' && data.detail) detail = data.detail;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const http = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, json?: unknown) => request<T>(path, { method: 'POST', json }),
  patch: <T>(path: string, json: unknown) => request<T>(path, { method: 'PATCH', json }),
  delete: <T = void>(path: string) => request<T>(path, { method: 'DELETE' }),
};
