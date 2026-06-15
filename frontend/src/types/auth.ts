export type AuthRole = "viewer" | "operator" | "admin";

export type AuthMeResponse = {
  auth_enabled: boolean;
  authenticated: boolean;
  role: AuthRole | null;
};
