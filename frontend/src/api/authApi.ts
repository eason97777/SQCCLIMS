import { apiClient } from "./apiClient";
import type { AuthMeResponse } from "../types/auth";

const AUTH_ME_PATH = "/api/auth/me";

/**
 * Fetch the current auth status.
 *
 * This intentionally does NOT go through apiClient.get: `/api/auth/me` is
 * callable without a token, and we need to optionally probe with a *candidate*
 * token (during login) without storing it or triggering the global 401 logout
 * handler. A non-OK response here means "could not determine auth status".
 */
export async function getAuthMe(candidateToken?: string): Promise<AuthMeResponse> {
  const headers = new Headers();
  if (candidateToken) {
    headers.set("Authorization", `Bearer ${candidateToken}`);
  }

  const response = await fetch(apiClient.buildUrl(AUTH_ME_PATH), {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    throw new Error(`Auth status request failed (${response.status})`);
  }

  return (await response.json()) as AuthMeResponse;
}
