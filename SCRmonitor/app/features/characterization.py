import mimetypes
from pathlib import Path

import app.config as config
from app.db import connect_db
from app.features.samples import get_sample_row
from app.storage import remove_stored_path, resolve_data_path, save_uploaded_file, storage_path_for
from app.validation import now_iso, optional_text, row_dict, rows_dict, safe_path_part


def get_characterization_files(query_params):
    sample_id = query_params.get("sample_id", [""])[0].strip()
    category = query_params.get("category", [""])[0].strip()
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []
    if sample_id:
        where.append("cf.sample_id = ?")
        args.append(sample_id)
    if category:
        where.append("cf.category = ?")
        args.append(category)
    if query:
        like = f"%{query}%"
        where.append(
            "(s.sample_code LIKE ? OR s.name LIKE ? OR cf.category LIKE ? OR cf.technique LIKE ? OR cf.title LIKE ? OR cf.original_filename LIKE ?)"
        )
        args.extend([like, like, like, like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT cf.*, s.sample_code, s.name AS sample_name,
                       cc.name AS collection_name, cc.storage_dir AS collection_storage_dir
                FROM characterization_files cf
                JOIN samples s ON s.id = cf.sample_id
                LEFT JOIN characterization_collections cc ON cc.id = cf.collection_id
                {where_sql}
                ORDER BY cf.created_at DESC, cf.id DESC
                LIMIT 1000
                """,
                args,
            ).fetchall()
        )

def characterization_file_record(row):
    item = row_dict(row)
    if item:
        item["preview_type"] = preview_type_for_file(item)
        item["is_previewable"] = item["preview_type"] != "download"
    return item

def collection_storage_dir(sample, collection_id, collection_name):
    sample_part = f"sample-{sample['id']}_{safe_path_part(sample['sample_code'], 'sample')}"
    collection_part = f"collection-{collection_id}_{safe_path_part(collection_name, 'collection')}"
    return config.UPLOAD_DIR / "characterization" / sample_part / collection_part

def create_characterization_collection_record(conn, fields):
    try:
        sample_id = int(fields.get("sample_id", ""))
    except (TypeError, ValueError):
        raise ValueError("sample_id must be numeric")

    sample = get_sample_row(conn, sample_id)
    timestamp = now_iso()
    category = optional_text(fields, "category") or "未分类"
    name = optional_text(fields, "collection_name") or optional_text(fields, "name")
    if not name:
        technique = optional_text(fields, "technique")
        captured_at = optional_text(fields, "captured_at")
        name = " / ".join([part for part in (technique, category, captured_at) if part]) or "未命名表征数据包"

    cursor = conn.execute(
        """
        INSERT INTO characterization_collections (
            sample_id, category, name, technique, instrument, captured_at,
            operator, notes, storage_dir, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_id,
            category,
            name,
            optional_text(fields, "technique"),
            optional_text(fields, "instrument"),
            optional_text(fields, "captured_at"),
            optional_text(fields, "operator"),
            optional_text(fields, "notes"),
            "",
            timestamp,
            timestamp,
        ),
    )
    collection_id = cursor.lastrowid
    target_dir = collection_storage_dir(sample, collection_id, name)
    conn.execute(
        "UPDATE characterization_collections SET storage_dir = ? WHERE id = ?",
        (storage_path_for(target_dir), collection_id),
    )
    return collection_id

def get_or_create_characterization_collection(conn, fields):
    collection_id = fields.get("collection_id")
    if collection_id not in ("", None):
        try:
            collection_id = int(collection_id)
        except (TypeError, ValueError):
            raise ValueError("collection_id must be numeric")
        row = conn.execute(
            "SELECT * FROM characterization_collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if row is None:
            raise ValueError("collection_id not found")
        return row

    collection_id = create_characterization_collection_record(conn, fields)
    return conn.execute(
        "SELECT * FROM characterization_collections WHERE id = ?",
        (collection_id,),
    ).fetchone()

def create_characterization_collection(payload):
    with connect_db() as conn:
        collection_id = create_characterization_collection_record(conn, payload)
        return get_characterization_collection(collection_id, conn=conn)

def get_characterization_collection(collection_id, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = connect_db()
    try:
        row = conn.execute(
            """
            SELECT cc.*, s.sample_code, s.name AS sample_name,
                   COUNT(cf.id) AS file_count,
                   COALESCE(SUM(cf.file_size), 0) AS total_bytes,
                   MAX(cf.created_at) AS latest_file_at
            FROM characterization_collections cc
            JOIN samples s ON s.id = cc.sample_id
            LEFT JOIN characterization_files cf ON cf.collection_id = cc.id
            WHERE cc.id = ?
            GROUP BY cc.id
            """,
            (collection_id,),
        ).fetchone()
        if row is None:
            raise LookupError("characterization collection not found")
        return row_dict(row)
    finally:
        if own_conn:
            conn.close()

def get_characterization_samples(query_params):
    query = query_params.get("query", [""])[0].strip()
    where = []
    args = []
    if query:
        like = f"%{query}%"
        where.append("(s.sample_code LIKE ? OR s.name LIKE ? OR s.category LIKE ? OR s.batch LIKE ? OR s.owner LIKE ?)")
        args.extend([like, like, like, like, like])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connect_db() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT
                    s.*,
                    COUNT(DISTINCT cc.id) AS collection_count,
                    COUNT(cf.id) AS characterization_file_count,
                    COUNT(DISTINCT cc.category) AS characterization_category_count,
                    MAX(COALESCE(cf.created_at, cc.created_at)) AS latest_characterization_at
                FROM samples s
                LEFT JOIN characterization_collections cc ON cc.sample_id = s.id
                LEFT JOIN characterization_files cf ON cf.collection_id = cc.id
                {where_sql}
                GROUP BY s.id
                ORDER BY latest_characterization_at DESC, s.created_at DESC, s.id DESC
                """,
                args,
            ).fetchall()
        )

def get_characterization_tree(sample_id, query_params):
    query = query_params.get("query", [""])[0].strip()
    with connect_db() as conn:
        sample = row_dict(conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone())
        if sample is None:
            raise LookupError("sample not found")

        collection_where = ["cc.sample_id = ?"]
        collection_args = [sample_id]
        if query:
            like = f"%{query}%"
            collection_where.append(
                """
                (
                    cc.category LIKE ? OR cc.name LIKE ? OR cc.technique LIKE ? OR cc.instrument LIKE ?
                    OR cc.operator LIKE ? OR cc.notes LIKE ? OR cf.original_filename LIKE ? OR cf.title LIKE ?
                )
                """
            )
            collection_args.extend([like, like, like, like, like, like, like, like])

        where_sql = f"WHERE {' AND '.join(collection_where)}"
        collection_rows = rows_dict(
            conn.execute(
                f"""
                SELECT
                    cc.*,
                    COUNT(cf.id) AS file_count,
                    COALESCE(SUM(cf.file_size), 0) AS total_bytes,
                    MAX(cf.created_at) AS latest_file_at
                FROM characterization_collections cc
                LEFT JOIN characterization_files cf ON cf.collection_id = cc.id
                {where_sql}
                GROUP BY cc.id
                ORDER BY cc.category, cc.created_at DESC, cc.id DESC
                """,
                collection_args,
            ).fetchall()
        )

        collection_ids = [row["id"] for row in collection_rows]
        files_by_collection = {collection_id: [] for collection_id in collection_ids}
        if collection_ids:
            placeholders = ",".join("?" for _ in collection_ids)
            file_where = [f"cf.collection_id IN ({placeholders})"]
            file_args = list(collection_ids)
            if query:
                like = f"%{query}%"
                file_where.append(
                    "(cf.original_filename LIKE ? OR cf.title LIKE ? OR cf.category LIKE ? OR cf.technique LIKE ? OR cf.notes LIKE ?)"
                )
                file_args.extend([like, like, like, like, like])
            file_rows = conn.execute(
                f"""
                SELECT cf.*
                FROM characterization_files cf
                WHERE {' AND '.join(file_where)}
                ORDER BY cf.relative_path, cf.created_at DESC, cf.id DESC
                """,
                file_args,
            ).fetchall()
            for row in file_rows:
                item = characterization_file_record(row)
                files_by_collection.setdefault(item["collection_id"], []).append(item)

        categories = []
        category_map = {}
        for collection in collection_rows:
            category_name = collection["category"] or "未分类"
            if category_name not in category_map:
                category_map[category_name] = {"name": category_name, "collections": [], "file_count": 0}
                categories.append(category_map[category_name])
            collection["files"] = files_by_collection.get(collection["id"], [])
            category_map[category_name]["file_count"] += len(collection["files"])
            category_map[category_name]["collections"].append(collection)

    return {"sample": sample, "categories": categories}

def create_characterization_files(fields, files):
    if not files:
        raise ValueError("at least one file is required")

    timestamp = now_iso()
    created = []
    with connect_db() as conn:
        collection = get_or_create_characterization_collection(conn, fields)
        sample_id = collection["sample_id"]
        category = collection["category"] or optional_text(fields, "category") or "未分类"
        technique = collection["technique"] or optional_text(fields, "technique")
        target_dir = resolve_data_path(collection["storage_dir"]) if collection["storage_dir"] else config.UPLOAD_DIR / "characterization" / f"collection-{collection['id']}"

        for file_item in files:
            stored = save_uploaded_file(file_item, target_dir)
            payload = {
                "collection_id": collection["id"],
                "sample_id": sample_id,
                "category": category,
                "technique": technique,
                "title": optional_text(fields, "title") or stored["original_filename"],
                "original_filename": stored["original_filename"],
                "stored_filename": stored["stored_filename"],
                "storage_path": stored["storage_path"],
                "mime_type": stored["mime_type"],
                "file_size": stored["file_size"],
                "relative_path": stored["relative_path"],
                "thumbnail_path": "",
                "captured_at": optional_text(fields, "captured_at"),
                "operator": optional_text(fields, "operator"),
                "notes": optional_text(fields, "notes"),
                "created_at": timestamp,
            }
            cursor = conn.execute(
                """
                INSERT INTO characterization_files (
                    collection_id, sample_id, category, technique, title, original_filename,
                    stored_filename, storage_path, mime_type, file_size, relative_path,
                    thumbnail_path, captured_at, operator, notes, created_at
                )
                VALUES (
                    :collection_id, :sample_id, :category, :technique, :title, :original_filename,
                    :stored_filename, :storage_path, :mime_type, :file_size, :relative_path,
                    :thumbnail_path, :captured_at, :operator, :notes, :created_at
                )
                """,
                payload,
            )
            created.append(cursor.lastrowid)

        conn.execute(
            "UPDATE characterization_collections SET updated_at = ? WHERE id = ?",
            (timestamp, collection["id"]),
        )

    return {"inserted": len(created), "ids": created, "collection_id": collection["id"]}

def delete_characterization_file(file_id):
    with connect_db() as conn:
        row = conn.execute("SELECT storage_path FROM characterization_files WHERE id = ?", (file_id,)).fetchone()
        if row is None:
            raise LookupError("characterization file not found")
        conn.execute("DELETE FROM characterization_files WHERE id = ?", (file_id,))
    remove_stored_path(row["storage_path"])
    return {"deleted": file_id}

def get_characterization_file(file_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT cf.*, s.sample_code, s.name AS sample_name,
                   cc.name AS collection_name, cc.storage_dir AS collection_storage_dir,
                   cc.instrument AS collection_instrument
            FROM characterization_files cf
            JOIN samples s ON s.id = cf.sample_id
            LEFT JOIN characterization_collections cc ON cc.id = cf.collection_id
            WHERE cf.id = ?
            """,
            (file_id,),
        ).fetchone()
    if row is None:
        raise LookupError("characterization file not found")
    return characterization_file_record(row)

def characterization_file_path(file_record):
    target = resolve_data_path(file_record["storage_path"])
    upload_root = config.UPLOAD_DIR.resolve()
    if not str(target).startswith(str(upload_root)) or not target.is_file():
        raise LookupError("stored file not found")
    return target

def preview_type_for_file(file_record):
    mime_type = file_record.get("mime_type") or mimetypes.guess_type(file_record.get("original_filename", ""))[0] or ""
    suffix = Path(file_record.get("original_filename", "")).suffix.lower()
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if mime_type.startswith("text/") or suffix in {".csv", ".txt", ".json", ".md", ".log", ".dat"}:
        return "text"
    return "download"
