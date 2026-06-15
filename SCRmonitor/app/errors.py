"""Domain exceptions and the exception->HTTP status convention.

The HTTP handler maps raised exceptions to status codes as follows:
    ValueError          -> 400 Bad Request
    AuthenticationError -> 401 Unauthorized
    AuthorizationError  -> 403 Forbidden
    LookupError         -> 404 Not Found
    ConflictError       -> 409 Conflict
Anything else          -> 500 Internal Server Error
"""


class ConflictError(Exception):
    pass


class AuthenticationError(Exception):
    """Missing or invalid credentials. Intended HTTP status: 401 Unauthorized."""

    pass


class AuthorizationError(Exception):
    """Authenticated but insufficient role. Intended HTTP status: 403 Forbidden."""

    pass
