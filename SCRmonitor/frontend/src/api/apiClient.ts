type Primitive = string | number | boolean | null | undefined;

type QueryValue = Primitive | Primitive[];

export type QueryParams = Record<string, QueryValue>;

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

/**
 * Thrown when the backend rejects a request because the current role lacks the
 * required permission (HTTP 403). Surfaced to the UI as "permission denied";
 * it does NOT log the user out.
 */
export class ForbiddenError extends ApiError {
  constructor(message: string, payload: unknown) {
    super(message, 403, payload);
    this.name = "ForbiddenError";
  }
}

/**
 * Thrown when the backend rejects a request because the token is missing or
 * invalid (HTTP 401). The stored token is cleared and the registered
 * unauthorized handler (the auth context) is notified so it can show login.
 */
export class UnauthorizedError extends ApiError {
  constructor(message: string, payload: unknown) {
    super(message, 401, payload);
    this.name = "UnauthorizedError";
  }
}

// --- Token storage -------------------------------------------------------

// NOTE: localStorage is acceptable for this local lab tool. The token is a
// pre-shared access token, not a credential that maps to an account.
const TOKEN_STORAGE_KEY = "scrmonitor_auth_token";

let cachedToken: string | null = null;
let tokenLoaded = false;

function readStoredToken(): string | null {
  if (tokenLoaded) {
    return cachedToken;
  }
  tokenLoaded = true;
  try {
    cachedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    cachedToken = null;
  }
  return cachedToken;
}

export function getAuthToken(): string | null {
  return readStoredToken();
}

export function setAuthToken(token: string | null) {
  cachedToken = token && token.length > 0 ? token : null;
  tokenLoaded = true;
  try {
    if (cachedToken) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, cachedToken);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignore storage failures (e.g. private mode); token still lives in memory.
  }
}

// --- Unauthorized notification ------------------------------------------

let onUnauthorized: (() => void) | null = null;

/**
 * Register a callback invoked when any request returns 401. The auth context
 * registers here so it can clear its state and show the login gate. The stored
 * token is already cleared before this fires.
 */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

function handleUnauthorized() {
  setAuthToken(null);
  if (onUnauthorized) {
    onUnauthorized();
  }
}

// --- Request plumbing ----------------------------------------------------

function buildUrl(path: string, query?: QueryParams) {
  const url = new URL(path, window.location.origin);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }

      if (Array.isArray(value)) {
        for (const item of value) {
          if (item !== undefined && item !== null && item !== "") {
            url.searchParams.append(key, String(item));
          }
        }
      } else {
        url.searchParams.set(key, String(value));
      }
    }
  }

  return `${url.pathname}${url.search}`;
}

/**
 * Merge the Authorization header into the request init only when a token is
 * actually stored. When auth is OFF (no token), requests are byte-for-byte
 * identical to before, so auth-OFF behavior is unchanged.
 */
function withAuth(init: RequestInit): RequestInit {
  const token = readStoredToken();
  if (!token) {
    return init;
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return { ...init, headers };
}

async function parseErrorPayload(response: Response) {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

function errorMessage(payload: unknown, response: Response) {
  return typeof payload === "object" &&
    payload !== null &&
    "error" in payload &&
    typeof (payload as { error: unknown }).error === "string"
    ? (payload as { error: string }).error
    : response.statusText || "Request failed";
}

async function raiseForStatus(response: Response): Promise<never> {
  const payload = await parseErrorPayload(response);
  const message = errorMessage(payload, response);

  if (response.status === 401) {
    handleUnauthorized();
    throw new UnauthorizedError(message, payload);
  }

  if (response.status === 403) {
    throw new ForbiddenError(message, payload);
  }

  throw new ApiError(message, response.status, payload);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    return response.json() as Promise<T>;
  }

  return response.text() as T;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  query?: QueryParams,
): Promise<T> {
  const response = await fetch(buildUrl(path, query), withAuth(init));

  if (!response.ok) {
    return raiseForStatus(response);
  }

  return parseResponse<T>(response);
}

export const apiClient = {
  get<T>(path: string, query?: QueryParams) {
    return request<T>(path, { method: "GET" }, query);
  },

  postJson<TResponse, TBody extends object>(path: string, body: TBody) {
    return request<TResponse>(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  },

  putJson<TResponse, TBody extends object>(path: string, body: TBody) {
    return request<TResponse>(path, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  },

  patchJson<TResponse, TBody extends object>(path: string, body: TBody) {
    return request<TResponse>(path, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  },

  delete<T>(path: string) {
    return request<T>(path, {
      method: "DELETE",
    });
  },

  postFormData<TResponse>(path: string, formData: FormData) {
    return request<TResponse>(path, {
      method: "POST",
      body: formData,
    });
  },

  getText(path: string, query?: QueryParams) {
    return request<string>(path, { method: "GET" }, query);
  },

  async getBlob(path: string, query?: QueryParams) {
    const response = await fetch(buildUrl(path, query), withAuth({}));

    if (!response.ok) {
      return raiseForStatus(response);
    }

    return response.blob();
  },

  /**
   * Auth-aware file download. Fetches the resource with the Authorization
   * header (when a token is stored), then triggers a browser download via a
   * temporary object URL. Use this instead of a raw `<a href="/api/...">`,
   * which cannot carry the token and would 401 when auth is on.
   */
  async downloadFile(path: string, filename?: string, query?: QueryParams) {
    const blob = await apiClient.getBlob(path, query);
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    if (filename) {
      anchor.download = filename;
    }
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    // Revoke after a tick so the navigation/download has started.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  },

  buildUrl,
};
