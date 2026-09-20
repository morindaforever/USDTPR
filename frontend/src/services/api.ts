import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';

/**
 * Base URL resolution:
 * - `VITE_API_BASE_URL` when provided (production / explicit override).
 * - `/api` otherwise, which the Vite dev server proxies to Django
 *   (see vite.config.ts). This avoids CORS during development.
 */
const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

const REQUEST_TIMEOUT_MS = 15_000;

/**
 * In-memory access token (never persisted to localStorage — see section
 * 3 security notes). Survives page reloads via the HttpOnly refresh cookie
 * and the silent refresh in AuthContext boot.
 */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Read Django's CSRF cookie so cookie-authenticated POSTs pass CSRF. */
function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Centralized Axios instance. All service modules must use this client. */
export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  withCredentials: true, // send the refresh cookie
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  const method = (config.method || 'get').toLowerCase();
  if (method !== 'get' && method !== 'head') {
    const csrf = readCookie('csrftoken');
    if (csrf) {
      config.headers['X-CSRFToken'] = csrf;
    }
  }
  return config;
});

/** True for auth endpoints that should never trigger the refresh loop. */
function isAuthUrl(url = ''): boolean {
  return url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh');
}

let refreshInFlight: Promise<boolean> | null = null;

/** Try to rotate the access token via the HttpOnly refresh cookie. */
export async function tryRefreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = axios
      .post(`${API_BASE_URL}/auth/refresh/`, {}, { withCredentials: true })
      .then((response) => {
        const data = response.data as { access?: string; data?: { access?: string } };
        const token = data?.access ?? data?.data?.access ?? null;
        accessToken = token;
        return Boolean(token);
      })
      .catch(() => {
        accessToken = null;
        return false;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

/**
 * Normalized API failure. Extends Error so `catch (err)` blocks using the
 * idiomatic `err instanceof Error ? err.message : fallback` pattern surface
 * the REAL backend message (envelope `message`, DRF `detail`, or the first
 * field error) instead of their generic fallback text.
 */
export class ApiRequestError extends Error {
  status: number | null;
  detail: unknown;

  constructor(status: number | null, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Response interceptor — normalize every failure into an `ApiRequestError`
 * and transparently retry once after a successful token refresh.
 */
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;

    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !isAuthUrl(original.url)
    ) {
      original._retried = true;
      const refreshed = await tryRefreshAccessToken();
      if (refreshed) {
        return api.request(original);
      }
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }

    return Promise.reject(
      new ApiRequestError(
        error.response?.status ?? null,
        extractErrorMessage(error),
        error.response?.data,
      ),
    );
  },
);

/** Map a failed request to a user-friendly message. */
function extractErrorMessage(error: AxiosError): string {
  if (error.response) {
    const data = error.response.data;
    const detail = extractDetailMessage(data);
    if (detail) return detail;
    switch (error.response.status) {
      case 400:
        return 'The request was invalid. Please review your input.';
      case 401:
        return 'You need to sign in to continue.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 429:
        return 'Too many requests. Please try again shortly.';
      case 500:
        return 'Something went wrong on our side. Please try again.';
      default:
        return `Request failed with status ${error.response.status}.`;
    }
  }
  if (error.code === 'ECONNABORTED') {
    return 'The request timed out. Please check your connection.';
  }
  return 'Unable to reach the server. Please check your connection.';
}

/** Envelope payloads can be {message}, {errors:{field:[...]}}, or plain DRF. */
function extractDetailMessage(data: unknown): string | null {
  if (typeof data === 'string') return data;
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    if (typeof record.message === 'string') return record.message;
    if (typeof record.detail === 'string') return record.detail;
    const errors = record.errors;
    if (errors && typeof errors === 'object') {
      const first = Object.entries(errors as Record<string, unknown>).find(([, v]) => v != null);
      if (first) {
        const value = Array.isArray(first[1]) ? first[1][0] : first[1];
        if (typeof value === 'string') return value;
      }
    }
  }
  return null;
}

/** Typed helper for GET requests with generic response typing. */
export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.get<T>(url, config);
  return response.data;
}

/** Typed helper for POST requests with generic response typing. */
export async function apiPost<T>(
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await api.post<T>(url, body, config);
  return response.data;
}

export async function apiPatch<T>(
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await api.patch<T>(url, body, config);
  return response.data;
}

/**
 * POST with a FormData body (file uploads). Lets the browser set the
 * multipart Content-Type boundary — the default header is dropped.
 */
export async function apiPostForm<T>(
  url: string,
  formData: FormData,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await api.post<T>(url, formData, {
    ...config,
    headers: { 'Content-Type': undefined, ...config?.headers },
  });
  return response.data;
}

/** GET a binary response (e.g. private-media images served through auth). */
export async function apiGetBlob(url: string, config?: AxiosRequestConfig): Promise<Blob> {
  const response = await api.get<Blob>(url, {
    ...config,
    responseType: 'blob',
  });
  return response.data;
}
