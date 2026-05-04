import { decodeEscapedTextDeep } from "@/lib/decodeEscapedText";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  });

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    if (res.status === 401) {
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }

  const data = (await res.json()) as T;
  return decodeEscapedTextDeep(data);
}

async function requestForm<T>(path: string, body: FormData, method = 'POST'): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    body,
    // Do NOT set Content-Type — browser will set multipart/form-data with boundary
  });

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    if (res.status === 401) {
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }

  const data = (await res.json()) as T;
  return decodeEscapedTextDeep(data);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  postForm: <T>(path: string, body: FormData) => requestForm<T>(path, body),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (path: string) => request<void>(path, { method: 'DELETE' }),
};
