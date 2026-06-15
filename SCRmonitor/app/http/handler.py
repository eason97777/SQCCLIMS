import cgi
import json
import mimetypes
import shutil
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import urlparse

import app.config as config
from app.logging_setup import get_logger
from app.errors import ConflictError
from app.db import connect_db
from app.features.characterization import characterization_file_path, create_characterization_collection, create_characterization_files, delete_characterization_file, get_characterization_collection, get_characterization_file, get_characterization_files, get_characterization_samples, get_characterization_tree
from app.features.mes import advance_mes_sample_route, create_mes_route_layer, create_mes_route_step, create_mes_route_template, create_mes_sample_route, delete_mes_route_step, get_mes_route_template_by_project, get_mes_route_template_detail, get_mes_route_templates, get_mes_sample_route_by_sample, update_mes_route_step
from app.features.parsing import create_mock_parsed_data, get_parsed_data_detail, get_parsed_data_list, get_parsed_data_records, get_parsed_record_options, parse_raw_data
from app.features.performance import create_performance_dataset, delete_performance_dataset, get_performance_dataset_files, get_performance_datasets
from app.features.process_records import lookup_process_sample, save_process_record, search_process_field_suggestions, search_process_layers, search_process_samples
from app.features.processing import get_processing_results, run_processing
from app.features.raw_data import create_raw_data, delete_raw_data, delete_raw_data_file, get_raw_data_detail, get_raw_data_list, raw_data_file_row, upload_raw_data_files
from app.features.samples import create_sample, delete_sample, get_samples, update_sample
from app.features.summary import get_summary
from app.features.test_data import bulk_create_test_data, create_test_data, delete_test_data, get_test_data
from app.features.visualization import get_processing_jobs, get_resistance_summary, get_visualization_chart_archive, visualize_parsed_data
from app.storage import raw_data_upload_file_path, resolve_data_path


logger = get_logger("http")


class AppHandler(BaseHTTPRequestHandler):
    server_version = "SampleTestingCenter/1.0"

    def send_response(self, code, message=None):
        # Capture the response status for access logging without altering
        # the response itself.
        self._response_status = code
        super().send_response(code, message)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_PATCH(self):
        self.route("PATCH")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        self._response_status = None
        start = time.monotonic()
        try:
            if path.startswith("/api/"):
                self.handle_api(method, path, query)
            else:
                self.serve_static(path)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except LookupError as exc:
            self.send_json({"error": str(exc)}, status=404)
        except ConflictError as exc:
            self.send_json({"error": str(exc)}, status=409)
        except Exception as exc:
            logger.exception("unhandled error handling %s %s", method, path)
            self.send_json({"error": "internal server error", "detail": str(exc)}, status=500)
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            status = self._response_status if self._response_status is not None else "-"
            logger.info(
                "%s %s status=%s duration_ms=%.1f", method, path, status, duration_ms
            )

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def read_multipart(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("request body must be multipart/form-data")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": self.command,
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
            keep_blank_values=True,
        )
        fields = {}
        files = []
        for item in form.list or []:
            if item.filename:
                files.append(
                    {
                        "name": item.name,
                        "filename": item.filename,
                        "mime_type": item.type or "",
                        "content": item.file.read(),
                    }
                )
            else:
                fields[item.name] = item.value
        return fields, files

    def handle_api(self, method, path, query):
        if method == "GET" and path == "/api/summary":
            return self.send_json(get_summary())
        if method == "GET" and path == "/api/samples":
            return self.send_json(get_samples(query))
        if method == "POST" and path == "/api/samples":
            return self.send_json(create_sample(self.read_json()), status=201)
        if method == "GET" and path == "/api/mes-route-templates":
            return self.send_json(get_mes_route_templates(query))
        if method == "POST" and path == "/api/mes-route-templates":
            return self.send_json(create_mes_route_template(self.read_json()), status=201)
        if method == "GET" and path == "/api/mes-route-templates/by-project":
            return self.send_json(get_mes_route_template_by_project(query))
        if path.startswith("/api/mes-route-templates/") and path.endswith("/layers") and method == "POST":
            template_id = int(path.replace("/api/mes-route-templates/", "", 1).replace("/layers", "").strip("/"))
            return self.send_json(create_mes_route_layer(template_id, self.read_json()), status=201)
        if path.startswith("/api/mes-route-templates/") and method == "GET":
            template_id = self.path_id(path, "/api/mes-route-templates/")
            return self.send_json(get_mes_route_template_detail(template_id))
        if path.startswith("/api/mes-route-layers/") and path.endswith("/steps") and method == "POST":
            layer_id = int(path.replace("/api/mes-route-layers/", "", 1).replace("/steps", "").strip("/"))
            return self.send_json(create_mes_route_step(layer_id, self.read_json()), status=201)
        if path.startswith("/api/mes-route-steps/") and method == "PATCH":
            step_id = self.path_id(path, "/api/mes-route-steps/")
            return self.send_json(update_mes_route_step(step_id, self.read_json()))
        if path.startswith("/api/mes-route-steps/") and method == "DELETE":
            step_id = self.path_id(path, "/api/mes-route-steps/")
            return self.send_json(delete_mes_route_step(step_id))
        if method == "POST" and path == "/api/mes-sample-routes":
            return self.send_json(create_mes_sample_route(self.read_json()), status=201)
        if path.startswith("/api/mes-sample-routes/") and path.endswith("/advance") and method == "POST":
            sample_route_id = int(path.replace("/api/mes-sample-routes/", "", 1).replace("/advance", "").strip("/"))
            return self.send_json(advance_mes_sample_route(sample_route_id, self.read_json()))
        if path.startswith("/api/samples/") and path.endswith("/mes-route") and method == "GET":
            sample_id = int(path.replace("/api/samples/", "", 1).replace("/mes-route", "").strip("/"))
            return self.send_json(get_mes_sample_route_by_sample(sample_id))
        if path.startswith("/api/samples/") and path.endswith("/characterization-tree") and method == "GET":
            sample_id = int(path.replace("/api/samples/", "", 1).replace("/characterization-tree", "").strip("/"))
            return self.send_json(get_characterization_tree(sample_id, query))
        if path.startswith("/api/samples/"):
            sample_id = self.path_id(path, "/api/samples/")
            if method == "PUT":
                return self.send_json(update_sample(sample_id, self.read_json()))
            if method == "DELETE":
                return self.send_json(delete_sample(sample_id))

        if method == "GET" and path == "/api/process-records/sample-lookup":
            if query.get("mode", [""])[0] == "suggestions":
                if query.get("field", [""])[0]:
                    return self.send_json(search_process_field_suggestions(query))
                return self.send_json(search_process_samples(query))
            if query.get("mode", [""])[0] == "field-suggestions":
                return self.send_json(search_process_field_suggestions(query))
            return self.send_json(lookup_process_sample(query))
        if method == "GET" and path == "/api/process-records/field-suggestions":
            return self.send_json(search_process_field_suggestions(query))
        if method == "GET" and path == "/api/process-records/layers":
            return self.send_json(search_process_layers(query))
        if method == "GET" and path == "/api/process-records/sample-suggestions":
            return self.send_json(search_process_samples(query))
        if method in {"POST", "PUT"} and path == "/api/process-records":
            status = 201 if method == "POST" else 200
            return self.send_json(save_process_record(self.read_json()), status=status)

        if method == "GET" and path == "/api/test-data":
            return self.send_json(get_test_data(query))
        if method == "POST" and path == "/api/test-data":
            return self.send_json(create_test_data(self.read_json()), status=201)
        if method == "POST" and path == "/api/test-data/bulk":
            return self.send_json(bulk_create_test_data(self.read_json()), status=201)
        if path.startswith("/api/test-data/") and method == "DELETE":
            record_id = self.path_id(path, "/api/test-data/")
            return self.send_json(delete_test_data(record_id))

        raw_data_path = path.rstrip("/") if path != "/" else path
        if method == "GET" and raw_data_path == "/api/raw-data":
            return self.send_json(get_raw_data_list(query))
        if method == "POST" and raw_data_path == "/api/raw-data":
            return self.send_json(create_raw_data(self.read_json()), status=201)
        if raw_data_path.startswith("/api/raw-data/"):
            suffix = raw_data_path.replace("/api/raw-data/", "", 1).strip("/")
            parts = [part for part in suffix.split("/") if part]
            if not parts:
                raise ValueError("raw_data_id must be numeric")
            try:
                raw_data_id = int(parts[0])
            except ValueError as exc:
                raise ValueError("raw_data_id must be numeric") from exc

            if method == "POST" and len(parts) == 2 and parts[1] == "files":
                _fields, files = self.read_multipart()
                return self.send_json(upload_raw_data_files(raw_data_id, files), status=201)
            if method == "POST" and len(parts) == 2 and parts[1] == "parse":
                return self.send_json(parse_raw_data(raw_data_id, self.read_json()))
            if method == "GET" and len(parts) == 1:
                return self.send_json(get_raw_data_detail(raw_data_id))
            if method == "DELETE" and len(parts) == 1:
                return self.send_json(delete_raw_data(raw_data_id))

        if path.startswith("/api/raw-data-files/"):
            suffix = path.replace("/api/raw-data-files/", "", 1).strip("/")
            if method == "GET" and suffix.endswith("/download"):
                file_id = int(suffix.replace("/download", "").strip("/"))
                return self.send_raw_data_file(file_id)
            if method == "DELETE":
                file_id = self.path_id(path, "/api/raw-data-files/")
                return self.send_json(delete_raw_data_file(file_id))

        if path.startswith("/api/outputs/") and method == "GET":
            return self.serve_output(path)
        if path.startswith("/api/templates/") and method == "GET":
            return self.serve_template(path)
        if method == "GET" and path == "/api/parsed-data":
            return self.send_json(get_parsed_data_list(query))
        if method == "POST" and path == "/api/parsed-data/mock":
            return self.send_json(create_mock_parsed_data(self.read_json()), status=201)
        if path.startswith("/api/parsed-data/") and method == "POST" and path.endswith("/visualize"):
            parsed_data_id = self.path_id(path[:-len("/visualize")], "/api/parsed-data/")
            return self.send_json(visualize_parsed_data(parsed_data_id, self.read_json()), status=201)
        if path.startswith("/api/parsed-data/") and method == "POST" and path.endswith("/resistance-summary"):
            parsed_data_id = self.path_id(path[:-len("/resistance-summary")], "/api/parsed-data/")
            return self.send_json(get_resistance_summary(parsed_data_id, self.read_json()))
        if path.startswith("/api/processing-jobs/") and method == "GET" and path.endswith("/charts/download"):
            job_id = self.path_id(path[:-len("/charts/download")], "/api/processing-jobs/")
            return self.send_visualization_chart_archive(job_id, query)
        if path.startswith("/api/parsed-data/") and method == "GET" and path.endswith("/records"):
            parsed_data_id = self.path_id(path[:-len("/records")], "/api/parsed-data/")
            return self.send_json(get_parsed_data_records(parsed_data_id, query))
        if path.startswith("/api/parsed-data/") and method == "GET" and path.endswith("/record-options"):
            parsed_data_id = self.path_id(path[:-len("/record-options")], "/api/parsed-data/")
            return self.send_json(get_parsed_record_options(parsed_data_id))
        if path.startswith("/api/parsed-data/") and method == "GET":
            parsed_data_id = self.path_id(path, "/api/parsed-data/")
            return self.send_json(get_parsed_data_detail(parsed_data_id))
        if method == "GET" and path == "/api/processing-jobs":
            return self.send_json(get_processing_jobs(query))

        if method == "GET" and path == "/api/characterization-files":
            return self.send_json(get_characterization_files(query))
        if method == "POST" and path == "/api/characterization-files":
            fields, files = self.read_multipart()
            return self.send_json(create_characterization_files(fields, files), status=201)
        if method == "GET" and path == "/api/characterization/samples":
            return self.send_json(get_characterization_samples(query))
        if method == "POST" and path == "/api/characterization-collections":
            return self.send_json(create_characterization_collection(self.read_json()), status=201)
        if path.startswith("/api/characterization-collections/") and method == "GET":
            collection_id = self.path_id(path, "/api/characterization-collections/")
            return self.send_json(get_characterization_collection(collection_id))
        if path.startswith("/api/characterization-files/"):
            suffix = path.replace("/api/characterization-files/", "", 1).strip("/")
            if method == "GET" and suffix.endswith("/preview"):
                file_id = int(suffix.replace("/preview", "").strip("/"))
                return self.send_characterization_file(file_id, inline=True)
            if method == "GET" and suffix.endswith("/download"):
                file_id = int(suffix.replace("/download", "").strip("/"))
                return self.send_characterization_file(file_id, inline=False)
            if method == "GET":
                file_id = self.path_id(path, "/api/characterization-files/")
                return self.send_json(get_characterization_file(file_id))
            if method == "DELETE":
                file_id = self.path_id(path, "/api/characterization-files/")
                return self.send_json(delete_characterization_file(file_id))

        if method == "GET" and path == "/api/performance-datasets":
            return self.send_json(get_performance_datasets(query))
        if method == "POST" and path == "/api/performance-datasets":
            fields, files = self.read_multipart()
            return self.send_json(create_performance_dataset(fields, files), status=201)
        if path.startswith("/api/performance-datasets/"):
            suffix = path.replace("/api/performance-datasets/", "", 1).strip("/")
            if method == "GET" and suffix.endswith("/files"):
                dataset_id = int(suffix.replace("/files", "").strip("/"))
                return self.send_json(get_performance_dataset_files(dataset_id))
            if method == "DELETE":
                dataset_id = self.path_id(path, "/api/performance-datasets/")
                return self.send_json(delete_performance_dataset(dataset_id))

        if method == "GET" and path == "/api/process-results":
            return self.send_json(get_processing_results())
        if method == "POST" and path == "/api/process":
            return self.send_json(run_processing(self.read_json()), status=201)

        self.send_json({"error": "not found"}, status=404)

    def path_id(self, path, prefix):
        raw = path.replace(prefix, "", 1).strip("/")
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError("invalid id") from exc

    def send_characterization_file(self, file_id, inline):
        record = get_characterization_file(file_id)
        target = characterization_file_path(record)
        preview_type = record["preview_type"]
        if inline and preview_type == "download":
            return self.send_json({"error": "file type is not previewable"}, status=415)

        content_type = record.get("mime_type") or mimetypes.guess_type(record["original_filename"])[0] or "application/octet-stream"
        if preview_type == "text":
            content_type = content_type if content_type.startswith("text/") else "text/plain"
        disposition_type = "inline" if inline else "attachment"
        filename = record["original_filename"]
        quoted_filename = quote(filename)
        safe_filename = filename.replace("\\", "_").replace('"', "'")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"{disposition_type}; filename=\"{safe_filename}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        static_root = config.STATIC_DIR.resolve()
        requested_target = (config.STATIC_DIR / path.lstrip("/")).resolve()

        if str(requested_target).startswith(str(static_root)) and requested_target.is_file():
            target = requested_target
        else:
            suffix = Path(path).suffix.lower()
            if suffix:
                self.send_error(404)
                return
            target = (config.STATIC_DIR / "index.html").resolve()
            if not target.is_file():
                self.send_error(404)
                return

        content_type = self.guess_content_type(target)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as handle:
            self.wfile.write(handle.read())

    def serve_output(self, path):
        relative = path.replace("/api/outputs/", "", 1).strip("/")
        target = resolve_data_path(relative)
        output_root = config.OUTPUT_DIR.resolve()
        if not str(target).startswith(str(output_root)) or not target.is_file():
            self.send_json({"error": "output file not found"}, status=404)
            return

        content_type = self.guess_content_type(target)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_visualization_chart_archive(self, job_id, query):
        archive_path, archive_name = get_visualization_chart_archive(job_id, query.get("chart_key", []))
        quoted_filename = quote(archive_name)
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(archive_path.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{archive_name}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with archive_path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_raw_data_file(self, file_id):
        with connect_db() as conn:
            record = raw_data_file_row(conn, file_id)
        target = raw_data_upload_file_path(record)
        if not target.is_file():
            raise LookupError("raw data file not found on disk")

        content_type = record.get("mime_type") or self.guess_content_type(target)
        filename = record["original_filename"]
        quoted_filename = quote(filename)
        safe_filename = filename.replace("\\", "_").replace('"', "'")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def serve_template(self, path):
        template_name = path.replace("/api/templates/", "", 1).strip("/")
        if "/" in template_name or "\\" in template_name or template_name not in config.ALLOWED_TEMPLATE_FILES:
            self.send_json({"error": "template not found"}, status=404)
            return

        template_root = config.TEMPLATE_DIR.resolve()
        target = (config.TEMPLATE_DIR / template_name).resolve()
        if not str(target).startswith(str(template_root)) or not target.is_file():
            self.send_json({"error": "template not found"}, status=404)
            return

        quoted_filename = quote(template_name)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{template_name}\"; filename*=UTF-8''{quoted_filename}",
        )
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def guess_content_type(self, target):
        overrides = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".ico": "image/x-icon",
        }
        suffix = target.suffix.lower()
        if suffix in overrides:
            return overrides[suffix]
        return mimetypes.guess_type(str(target))[0] or "application/octet-stream"

    def send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        # Route BaseHTTPRequestHandler's default stderr logging through our
        # logger at DEBUG so it does not duplicate the access log line emitted
        # by route(). Demoted to DEBUG to avoid double noise at INFO level.
        logger.debug(format % args)
