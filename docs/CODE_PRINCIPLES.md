# Code Principles

> Principles and governance live in the [constitution](../.specify/memory/constitution.md); this file is the concrete coding-conventions reference (examples + conventions).

A coding-conventions reference for everyone working in this codebase — humans and coding agents alike. Read `ARCHITECTURE.md` first for the layer map.

## 1. Respect the layering and dependency direction

The dependency direction is **low-level ← features ← http** (see `ARCHITECTURE.md`):

- `app/http/handler.py` may import from `app/features/*` and infra.
- `app/features/*` may import from `db`, `validation`, `storage`, `errors`, `config`.
- Infra/domain modules must not import features or the HTTP layer.

No import cycles. If a low-level module genuinely needs something from a higher one (e.g. `db.record_deletion` needs `validation.now_iso`), break the cycle with a **function-local import** inside the function that needs it — exactly as `db.py` already does.

## 2. Access runtime config as attributes, at call time

`config.configure_paths()` reassigns `DATA_DIR`, `DB_PATH`, `UPLOAD_DIR`, `OUTPUT_DIR`, `LOG_DIR` at startup, so binding them at import time captures stale values. Always `import app.config as config` and read `config.<NAME>` when you use it.

```python
import app.config as config
db = config.DB_PATH          # ✅ resolved at call time

from app.config import DB_PATH   # ❌ frozen at import, ignores configure_paths()
```

## 3. One feature = one module

Each domain area is a single module under `app/features/`. Put validation and SQL there. The HTTP handler stays thin: parse the request, call a feature function, serialize the result. Do not add business logic to `handler.py`, and do not spread one feature across several modules.

## 4. Error handling via the exception convention

Don't build status codes in feature code. Raise the right exception and let `AppHandler.route()` map it: invalid input → `ValueError`; missing entity → `LookupError`; uniqueness/state conflict → `ConflictError`. The full mapping is the canonical table below.

### Exception → HTTP status mapping

| Raise | Becomes |
|-------|---------|
| `ValueError` | 400 Bad Request |
| `AuthenticationError` | 401 Unauthorized |
| `AuthorizationError` | 403 Forbidden |
| `LookupError` | 404 Not Found |
| `ConflictError` | 409 Conflict |
| `sqlite3.IntegrityError` | 409 Conflict (uniqueness/integrity collision that could not be auto-resolved) |
| `sqlite3.OperationalError` *(message contains "database is locked")* | 503 Service Unavailable (busy beyond `busy_timeout`; retry shortly) |
| anything else | 500 (logged with full traceback) |

## 5. Parameterized SQL only

Never string-format user input into SQL. Use `?` placeholders or named parameters and pass values as the parameter tuple/dict — as every feature module already does. The only acceptable interpolation is for trusted identifiers built entirely in code (e.g. fixed column lists), never request data.

## 6. No new third-party dependencies without approval

The backend core is intentionally **stdlib-only** (`http.server`, `sqlite3`, etc.). Get explicit approval before adding anything to `requirements.txt`; third-party scientific dependencies are confined to `parsers/`. The frontend uses npm normally, but keep its footprint lean too.

## 7. Keep the smoke test green

Run `tests/smoke_test.py` before a change to capture a baseline and after every change to prove nothing regressed:

```bash
python3 tests/smoke_test.py
```

When you add or change an endpoint, extend the smoke test to cover it.

## 8. Schema changes go through migrations

New tables, columns, indexes, and data backfills go in a new `migrations/NNN_*.sql` file — never by editing an applied migration (checksums are enforced) and not by appending to `init_db()`. See `CONTRIBUTING.md` and `migrations/README.md`.

## 9. Comments and naming

Follow the existing style. Comment non-obvious logic and invariants, not what the code plainly says. Match existing naming conventions and file structure. Simplest solution that works — no speculative abstraction.

## Deliberately deferred (known future directions)

These are intentionally **not** built yet. Don't treat their absence as a bug; if you need them, raise it rather than bolting on a partial version (see the constitution on deferred features):

- **Full cascading soft-delete.** Today deletes are hard deletes with a `deletion_audit` JSON snapshot for recoverability. A first-class soft-delete (status flags + cascade) is deferred.
- **A repository layer.** SQL currently lives inline in feature modules. Extracting a repository/data-access layer to remove inline SQL is a future refactor.
- **Pagination.** List endpoints currently return full result sets. Cursor/offset pagination is deferred until data volume requires it.
