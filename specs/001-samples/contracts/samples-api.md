# API Contracts: Samples

> As-built request/response contracts for the 7 Samples endpoints, grounded in
> `app/http/handler.py` (routing) and `app/features/samples.py`,
> `app/deletion.py`, `app/features/mes.py`, `app/features/characterization.py`
> (logic). Status codes follow the project exception→status convention
> (constitution **Article VI**):
>
> | Raised | Status |
> |--------|--------|
> | `ValueError` | 400 Bad Request |
> | `AuthenticationError` | 401 Unauthorized (auth enabled) |
> | `AuthorizationError` | 403 Forbidden (auth enabled) |
> | `LookupError` | 404 Not Found |
> | anything else | 500 Internal Server Error |
>
> Error bodies are `{"error": "<message>"}` (500 also adds `"detail"`). Min-role
> applies only when auth is enabled (**Article XI**); when disabled, all roles
> pass. All requests/responses are JSON (`charset=utf-8`).

---

## 1. List samples

`GET /api/samples` · min role: **viewer**

### Query parameters

| Name | Type | Notes |
|------|------|-------|
| `query` | string (optional) | Free-text; matches `sample_display_code`, `sample_uid`, `sample_code`, `name`, `category`, `batch`, `owner` (SQL `LIKE %q%`). |
| `status` | string (optional) | Exact match on `status`. |

### Response `200`

JSON array of sample objects, ordered `created_at DESC, id DESC`. Each object:

```json
[
  {
    "id": 12,
    "sample_uid": "SMP-2026-000012",
    "sample_display_code": "PRJ-A-Wafer-1-Etch-S03",
    "sample_code": "PRJ-A",
    "name": "Wafer-1",
    "category": "Etch",
    "batch": "S03",
    "owner": "zhangsan",
    "status": "待测试",
    "received_at": "2026-06-10",
    "notes": "",
    "created_at": "2026-06-10T02:11:00+00:00",
    "updated_at": "2026-06-10T02:11:00+00:00",
    "data_count": 4,
    "last_measured_at": "2026-06-12T08:00:00+00:00"
  }
]
```

`data_count` and `last_measured_at` are computed (LEFT JOIN on `test_data`);
`last_measured_at` is `null` when the sample has no measurements.

### Errors

- `400` — never for this endpoint under normal use.

---

## 2. Create sample

`POST /api/samples` · min role: **operator**

### Request body

```json
{
  "sample_code": "PRJ-A",
  "name": "Wafer-1",
  "category": "Etch",
  "batch": "S03",
  "owner": "zhangsan",
  "status": "待测试",
  "received_at": "2026-06-10",
  "notes": "optional remark"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `sample_code` | yes | Project number; non-empty after trim. |
| `name` | yes | Sample name; non-empty. |
| `category` | yes* | Process type. Validation requires it non-empty. |
| `batch` | yes* | Sample sequence; non-empty, ≤ 32 chars, not punctuation-only. |
| `status` | yes* | Defaults to `"待测试"` if omitted/empty. |
| `owner` | no | Responsible person. |
| `received_at` | no | Received date (free text). |
| `notes` | no | Remarks. |

> *`category`, `batch`, `status` are accepted as optional at the JSON-parsing
> layer but are **required** by `validate_sample_payload` (status auto-defaults).
> `sample_uid` and `sample_display_code` are **server-generated** and MUST NOT be
> supplied.

### Response `201`

The full created sample row (same shape as a list item, **without** the computed
`data_count` / `last_measured_at`):

```json
{
  "id": 12,
  "sample_uid": "SMP-2026-000012",
  "sample_display_code": "PRJ-A-Wafer-1-Etch-S03",
  "sample_code": "PRJ-A",
  "name": "Wafer-1",
  "category": "Etch",
  "batch": "S03",
  "owner": "zhangsan",
  "status": "待测试",
  "received_at": "2026-06-10",
  "notes": "optional remark",
  "created_at": "2026-06-10T02:11:00+00:00",
  "updated_at": "2026-06-10T02:11:00+00:00"
}
```

### Errors

- `400` — missing required field (`"项目编号不能为空"`, `"样品名称不能为空"`,
  `"工艺类型不能为空"`, `"样品序号不能为空"`, `"样品状态不能为空"`); or
  `"{field} is required"` for `sample_code`/`name` at parse time.
- `400` — garbled text detected (`"检测到疑似乱码字符，请检查字段内容后再保存。"`).
- `400` — malformed sequence (`"样品序号格式可能不规范，请检查。"`).
- `400` — duplicate display code
  (`"当前样品显示编号已存在，请修改项目编号、样品名称、工艺类型或样品序号。"`).
- `400` — name-consistency violation
  (`"同一项目编号下的样品名称需保持一致。"` /
  `"同一项目编号和工艺类型下的样品名称需保持一致。"`).

---

## 3. Update sample

`PUT /api/samples/{id}` · min role: **operator**

### Request body

Same fields as **Create**. The server preserves the existing `sample_uid`;
`sample_display_code` is recomputed and re-validated. `id` in the path selects
the sample.

### Response `200`

The full updated sample row (same shape as the Create `201` body).

### Errors

- `404` — sample not found (`"sample not found"`).
- `400` — same validation errors as Create (required fields, garbled text,
  sequence, duplicate display code, name consistency).
- `400` — invalid id (`"invalid id"`) if `{id}` is non-numeric.

---

## 4. Delete sample (Strong tier)

`DELETE /api/samples/{id}` · min role: **admin**

Cascade-deletes the sample and all child data. Takes a DB backup first, snapshots
the row to `deletion_audit`, and removes associated live-store files after
commit. **Use the delete-preview endpoint first** to show blast radius.

### Response `200`

```json
{ "deleted": 12 }
```

### Errors

- `404` — sample not found (`"sample not found"`).
- `400` — invalid id (`"invalid id"`).

---

## 5. Delete preview (read-only cascade preview)

`GET /api/samples/{id}/delete-preview` · min role: **viewer**

Read-only. Reports how many rows of each child category and how many files would
be removed by a delete. **Modifies nothing.**

### Response `200`

```json
{
  "sample_display_code": "PRJ-A-Wafer-1-Etch-S03",
  "test_data": 4,
  "process_records": 2,
  "raw_data": 1,
  "raw_data_files": 3,
  "parsed_data": 1,
  "parsed_records": 120,
  "characterization_files": 5,
  "performance_datasets": 0,
  "files_total": 8
}
```

`files_total` is the count of resolved live-store file paths owned by the sample
and its descendants (raw-data files + characterization files + performance files
+ parsed-data outputs).

### Errors

- `404` — sample not found (`"sample not found"`).
- `400` — invalid id.

---

## 6. Sample MES route

`GET /api/samples/{id}/mes-route` · min role: **viewer**

Returns the **latest** MES sample route for the sample (most recent
`created_at`/`id`), after syncing it from any submitted process records.

### Response `200`

An MES sample-route payload (built by `mes_sample_route_payload`): the route
instance with its layers/steps and current progress. Shape is owned by the MES
feature; see [`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md).

### Errors

- `404` — no MES sample route for this sample (`"MES sample route not found"`).
- `400` — invalid id.

---

## 7. Sample characterization tree

`GET /api/samples/{id}/characterization-tree` · min role: **viewer**

Returns the sample's characterization collections grouped by category, with their
files nested, optionally filtered by free text.

### Query parameters

| Name | Type | Notes |
|------|------|-------|
| `query` | string (optional) | Filters collections/files by category, name, technique, instrument, operator, notes, filename, or title. |

### Response `200`

A tree object: the sample plus its characterization **categories → collections →
files**, where each collection carries `file_count`, `total_bytes`, and
`latest_file_at`. Shape is owned by the characterization feature; see
[`docs/BACKEND_MODULES.md`](../../docs/BACKEND_MODULES.md).

### Errors

- `404` — sample not found (`"sample not found"`).
- `400` — invalid id.

---

## Notes & known gaps

- There is **no** `GET /api/samples/{id}` single-sample detail endpoint. Detail
  reads currently rely on the list response (see the `samplesApi.ts` TODO and the
  spec **Out of Scope** section).
- Suffix routes (`/delete-preview`, `/mes-route`, `/characterization-tree`) are
  matched in `handle_api` **before** the generic `/api/samples/{id}` PUT/DELETE
  branch, so they are not shadowed.
