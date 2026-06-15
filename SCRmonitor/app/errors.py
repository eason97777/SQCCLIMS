"""Domain exceptions and the exception->HTTP status convention.

The HTTP handler maps raised exceptions to status codes as follows:
    ValueError    -> 400 Bad Request
    LookupError   -> 404 Not Found
    ConflictError -> 409 Conflict
Anything else    -> 500 Internal Server Error
"""


class ConflictError(Exception):
    pass
