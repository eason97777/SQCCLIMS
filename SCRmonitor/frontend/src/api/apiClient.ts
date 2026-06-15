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

async function parseErrorPayload(response: Response) {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
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
  const response = await fetch(buildUrl(path, query), init);

  if (!response.ok) {
    const payload = await parseErrorPayload(response);
    const message =
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : response.statusText || "Request failed";

    throw new ApiError(message, response.status, payload);
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

  getBlob(path: string, query?: QueryParams) {
    return fetch(buildUrl(path, query)).then(async (response) => {
      if (!response.ok) {
        const payload = await parseErrorPayload(response);
        const message =
          typeof payload === "object" &&
          payload !== null &&
          "error" in payload &&
          typeof payload.error === "string"
            ? payload.error
            : response.statusText || "Request failed";

        throw new ApiError(message, response.status, payload);
      }

      return response.blob();
    });
  },

  buildUrl,
};
