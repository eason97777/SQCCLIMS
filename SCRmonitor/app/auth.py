"""Optional token-based authentication and role-based access control.

Auth is DISABLED BY DEFAULT. With no environment variables set every request
behaves exactly as it did before this module existed; ``authorize`` is a no-op.
It only enforces when explicitly enabled.

Environment variables (read at call time, never bound at import):
    JIQT_AUTH_ENABLED   truthy (1/true/yes) to turn enforcement ON
    JIQT_AUTH_DISABLED  truthy hard-override that keeps auth OFF even if enabled
    JIQT_API_TOKENS     "token1:role1,token2:role2" -> {token: role}

Roles: admin, operator, viewer.

RBAC policy by HTTP method (only paths under /api/ are guarded):
    GET, HEAD          -> viewer, operator, admin
    POST, PUT, PATCH   -> operator, admin
    DELETE             -> admin
"""
import os

from app.errors import AuthenticationError, AuthorizationError


VALID_ROLES = ("admin", "operator", "viewer")

# Role sets permitted per HTTP method.
_METHOD_POLICY = {
    "GET": {"viewer", "operator", "admin"},
    "HEAD": {"viewer", "operator", "admin"},
    "POST": {"operator", "admin"},
    "PUT": {"operator", "admin"},
    "PATCH": {"operator", "admin"},
    "DELETE": {"admin"},
}

_TRUTHY = {"1", "true", "yes"}


def _is_truthy(value):
    return (value or "").strip().lower() in _TRUTHY


def auth_enabled():
    """True only if auth is explicitly enabled and not hard-disabled.

    Reads the environment at call time so tests and the running server can
    toggle behaviour without a restart. Default -> False (disabled).
    """
    if _is_truthy(os.environ.get("JIQT_AUTH_DISABLED")):
        return False
    return _is_truthy(os.environ.get("JIQT_AUTH_ENABLED"))


def token_store():
    """Parse JIQT_API_TOKENS ("tok:role,tok:role") into {token: role}.

    Malformed entries (no colon, blank token, unknown role) are skipped.
    """
    store = {}
    raw = os.environ.get("JIQT_API_TOKENS", "")
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        token, _, role = entry.partition(":")
        token = token.strip()
        role = role.strip().lower()
        if token and role in VALID_ROLES:
            store[token] = role
    return store


def _extract_token(headers):
    """Pull a bearer token from Authorization or X-API-Key headers."""
    auth_header = headers.get("Authorization", "") or ""
    if auth_header:
        parts = auth_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    api_key = headers.get("X-API-Key", "") or ""
    if api_key:
        return api_key.strip()
    return None


def authenticate(headers):
    """Return the role for the request's token, or None if absent/invalid."""
    token = _extract_token(headers)
    if not token:
        return None
    return token_store().get(token)


def authorize(method, path, headers):
    """Middleware: enforce auth + RBAC for /api/ paths when auth is enabled.

    No-op when auth is disabled (the default) or for non-API paths so the
    static SPA always loads. Raises AuthenticationError (401) for a missing or
    invalid token and AuthorizationError (403) when the role is insufficient.
    """
    if not auth_enabled():
        return
    if not path.startswith("/api/"):
        return

    role = authenticate(headers)
    if role is None:
        raise AuthenticationError("missing or invalid API token")

    allowed = _METHOD_POLICY.get(method.upper())
    if allowed is None or role not in allowed:
        raise AuthorizationError(f"role '{role}' is not permitted to {method} this resource")
