# API Contract: Error Handling Under Concurrency

> This is a **cross-cutting, behavioral** contract change — **not** a new
> endpoint. It documents how the project's exception→status convention
> (constitution **Article VI**) is extended so that database-contention and
> integrity failures are reported **honestly** instead of as a misleading
> `500 Internal Server Error`. It is grounded in `app/http/handler.py` (the single
> central mapping in `route()`), `app/db.py` (`connect_db()`), and
> `app/features/samples.py` (the sample create path).

## What changes

The current mapping in `AppHandler.route()` (`app/http/handler.py:60-84`) is:

| Raised | Status (today) |
|--------|----------------|
| `ValueError` | 400 Bad Request |
| `AuthenticationError` | 401 Unauthorized |
| `AuthorizationError` | 403 Forbidden |
| `LookupError` | 404 Not Found |
| `ConflictError` | 409 Conflict |
| **anything else** (incl. `sqlite3.IntegrityError`, `sqlite3.OperationalError`) | **500 Internal Server Error** |

Today, a contended writer that hits SQLite's single write lock raises
`sqlite3.OperationalError: database is locked` (because `connect_db()` sets no
`busy_timeout` — `app/db.py:7-14`), and a uniqueness/integrity collision raises
`sqlite3.IntegrityError`; **both fall through to the generic 500** — dishonest:
the request was not malformed and the server is not broken.

**This feature adds two mappings** to the same central point:

| Raised | Status (after) | Meaning |
|--------|----------------|---------|
| `sqlite3.IntegrityError` | **409 Conflict** | A uniqueness/integrity rule was violated and could not be auto-resolved. |
| `sqlite3.OperationalError` *(message indicates "database is locked")* | **503 Service Unavailable** | The database stayed locked beyond the bounded wait window (`busy_timeout`). Retry shortly. |

Ordering: the new arms are placed so they do **not** shadow the existing
`ValueError`/`LookupError`/`ConflictError`/auth arms. Only a locked
`OperationalError` maps to 503; other `OperationalError`s (e.g. genuine schema/SQL
errors) continue to surface as 500, because those *are* unexpected.

> Note: `create_sample` already catches `IntegrityError` for the **display-code**
> duplicate case and re-raises it as a `ValueError` → **400** with a field-naming
> message (`app/features/samples.py:179-180`). That behavior is **preserved**.
> The new 409 mapping is the **fallback** for integrity errors that genuinely
> reach the handler (a real conflict, not a user-input problem). The `sample_uid`
> collision case is handled by an in-feature **retry loop** (regenerate UID and
> re-insert), so under normal concurrency it never reaches the handler at all.

## Affected endpoints

**All write endpoints** — every `POST` / `PUT` / `PATCH` / `DELETE` under `/api/`
— because the underlying contention (`database is locked`) and integrity
conditions can arise on any write. This includes, but is not limited to:

- `POST /api/samples`, `PUT /api/samples/{id}`, `DELETE /api/samples/{id}`
- `POST /api/test-data`, `POST /api/test-data/bulk`, `DELETE /api/test-data/{id}`
- `POST`/`PUT /api/process-records`
- `POST /api/raw-data`, `POST /api/raw-data/{id}/files`, `DELETE` raw-data paths
- `POST /api/parsed-data/{id}/visualize`, `POST /api/process`
- the MES, characterization, and performance write endpoints

Read endpoints (`GET`) are unaffected in practice (they do not contend for the
write lock), but they inherit the same central mapping for free.

No endpoint's **path, method, request body, or success response** changes. Only
the **status code returned on contention/integrity failure** changes
(500 → 409/503).

## Error response bodies

Bodies keep the existing shape `{"error": "<message>"}` produced by
`AppHandler.send_json` (`app/http/handler.py:495-501`). Unlike the old 500 path
(which also added `"detail": str(exc)`), the mapped 409/503 responses carry the
clean `error` field only.

### 409 Conflict (integrity collision)

```http
HTTP/1.1 409 Conflict
Content-Type: application/json; charset=utf-8
```

```json
{ "error": "resource conflict" }
```

### 503 Service Unavailable (database busy beyond wait window)

```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json; charset=utf-8
```

```json
{ "error": "database is busy, please retry" }
```

> Exact messages are an implementation detail; the **contract** is: integrity
> collision → 409, lock-wait timeout → 503, both with a JSON `{"error": ...}`
> body, and **neither** as a 500.

## Client guidance

- **409** → a real conflict; do not blind-retry the identical request. (Under
  normal sample creation this is not expected — UID collisions are auto-resolved
  in-feature.)
- **503** → transient; the database was busy. A short backoff-and-retry is
  appropriate. This is the honest signal that replaces the former misleading 500.
- **400 / 404 / 401 / 403 / existing 409 (`ConflictError`)** → unchanged; existing
  semantics are preserved (FR-006).

## Constitution alignment

- **Article VI** — the mapping stays in the **single** central point
  (`route()`); feature code raises/propagates typed exceptions and never builds
  status codes by hand.
- **Article I** — no new dependency; `sqlite3` exceptions are standard library.
- **Article X** — the smallest honest change: two `except` arms, not a new
  error-handling framework.
