import json
import logging
import re
import threading
from datetime import datetime, timezone
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# R2 JSON store for admin-assigned document access. The document itself remains
# in the recipient's date-based download folder.
# ---------------------------------------------------------------------------

_admin_docs_lock = threading.Lock()
USERS_OBJECT_KEY = "login/users.json"
ADMIN_DOCS_OBJECT_KEY = "admin_docs.json"


def _load_admin_docs() -> list[dict]:
    docs = get_json_object(ADMIN_DOCS_OBJECT_KEY)
    if docs is None:
        return []
    if not isinstance(docs, list) or not all(isinstance(doc, dict) for doc in docs):
        raise RuntimeError("Admin document data in R2 has an invalid structure.")
    return docs


def _save_admin_docs(docs: list[dict]) -> None:
    put_json_object(ADMIN_DOCS_OBJECT_KEY, docs)


# Per-doc-key lock to prevent concurrent download-count races
_doc_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()

MAX_DOWNLOADS = 3

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _doc_lock(doc_key: str) -> threading.Lock:
    with _locks_mutex:
        if doc_key not in _doc_locks:
            _doc_locks[doc_key] = threading.Lock()
        return _doc_locks[doc_key]


def _current_ym() -> tuple[int, int]:
    """Use one server-side clock for every date-based R2 key."""
    now = datetime.now(timezone.utc)
    return now.year, now.month


def current_year_month() -> tuple[int, int]:
    """Expose the server date so one submission uses one date-based folder."""
    return _current_ym()


def _safe_path_component(value: str) -> str:
    return value.strip().replace("/", "-").replace("\\", "-")


def _safe_download_filename(filename: str, consumer_number: str, ext: str) -> str:
    """Keep admin downloads in one flat per-user folder without path traversal."""
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "document"
    return f"{_safe_path_component(consumer_number)}_{safe_stem}.{ext}"


# ---------------------------------------------------------------------------
# Low-level R2 helpers
# ---------------------------------------------------------------------------

def _put_object(key: str, body: bytes, content_type: str) -> None:
    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        logger.info("R2 put: %s", key)
    except (BotoCoreError, ClientError) as exc:
        logger.error("R2 put failed %s: %s", key, exc)
        raise


def _get_object_bytes(key: str) -> bytes | None:
    client = _get_client()
    try:
        resp = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        return resp["Body"].read()
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        logger.error("R2 get failed %s: %s", key, exc)
        raise


def _delete_object(key: str) -> None:
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        logger.info("R2 delete: %s", key)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("R2 delete failed %s: %s", key, exc)


def get_json_object(key: str) -> object | None:
    """Read a JSON document from R2, returning None only when it does not exist."""
    body = _get_object_bytes(key)
    if body is None:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Invalid JSON in R2 object %s: %s", key, exc)
        raise RuntimeError(f"Invalid JSON in R2 object '{key}'.") from exc


def put_json_object(key: str, value: object) -> None:
    _put_object(
        key,
        json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"),
        "application/json",
    )


# ---------------------------------------------------------------------------
# Admin: upload a document assigned to a specific user
# ---------------------------------------------------------------------------

def admin_upload_document(
    consumer_number: str,
    target_username: str,
    file_data: bytes,
    original_filename: str,
    ext: str,
    uploaded_by: str,
) -> dict:
    year, month = _current_ym()
    prefix = f"{year}/{month:02d}/{_safe_path_component(target_username)}/download/"
    doc_key = f"{prefix}{_safe_download_filename(original_filename, consumer_number, ext)}"
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

    _put_object(doc_key, file_data, content_type)

    record = {
        "assigned_to": target_username,
        "consumer_number": consumer_number,
        "document_key": doc_key,
        "original_filename": original_filename,
        "uploaded_by": uploaded_by,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "downloads": 0,
        "max_downloads": MAX_DOWNLOADS,
        "available": True,
    }

    with _admin_docs_lock:
        docs = _load_admin_docs()
        previous_key = None
        for i, d in enumerate(docs):
            if d["assigned_to"] == target_username and d["consumer_number"] == consumer_number:
                previous_key = d.get("document_key")
                docs[i] = record
                break
        else:
            docs.append(record)
        _save_admin_docs(docs)

    if previous_key and previous_key != doc_key:
        _delete_object(previous_key)

    logger.info(
        "Admin '%s' uploaded for consumer %s → %s (assigned to '%s')",
        uploaded_by, consumer_number, doc_key, target_username,
    )
    return record


# ---------------------------------------------------------------------------
# Username-based document access
# ---------------------------------------------------------------------------

def find_documents_for_user(username: str) -> list[dict]:
    with _admin_docs_lock:
        docs = _load_admin_docs()
    return [d for d in docs if d.get("assigned_to") == username]


def find_consumer_document(consumer_number: str) -> dict | None:
    with _admin_docs_lock:
        docs = _load_admin_docs()
    matches = [d for d in docs if d.get("consumer_number") == consumer_number]
    if not matches:
        return None
    matches.sort(key=lambda d: d.get("uploaded_at", ""), reverse=True)
    return matches[0]


# ---------------------------------------------------------------------------
# Secure download: username-authorised, thread-safe, 3-download limit
# ---------------------------------------------------------------------------

def attempt_download_by_username(
    username: str, doc_key: str
) -> tuple[bytes | None, dict | None, str]:
    lock = _doc_lock(doc_key)
    with lock:
        with _admin_docs_lock:
            docs = _load_admin_docs()
            record = next(
                (d for d in docs if d.get("assigned_to") == username and d.get("document_key") == doc_key),
                None,
            )
            if record is None:
                return None, None, "Document not found or access denied."
            if record.get("downloads", 0) >= MAX_DOWNLOADS:
                return None, dict(record), f"Download limit reached ({MAX_DOWNLOADS}/{MAX_DOWNLOADS})."

        # Fetch from R2 outside the JSON lock — network call must not hold the lock
        file_bytes = _get_object_bytes(doc_key)
        if file_bytes is None:
            return None, dict(record), "Document file not found in storage."

        with _admin_docs_lock:
            docs = _load_admin_docs()
            for d in docs:
                if d.get("assigned_to") == username and d.get("document_key") == doc_key:
                    d["downloads"] += 1
                    d["available"] = d["downloads"] < MAX_DOWNLOADS
                    record = dict(d)
                    break
            _save_admin_docs(docs)

    return file_bytes, record, ""


# ---------------------------------------------------------------------------
# Helpers used by the submissions route
# ---------------------------------------------------------------------------

def generate_object_key(
    ext: str,
    consumer_number: str,
    doc_type: str,
    username: str,
    year: int | None = None,
    month: int | None = None,
) -> str:
    """Build a consumer document key within that consumer's date/user folder."""
    if year is None or month is None:
        year, month = _current_ym()
    safe_num = _safe_path_component(consumer_number)
    safe_user = _safe_path_component(username)
    return f"{year}/{month:02d}/{safe_user}/{safe_num}/{safe_num}_{doc_type}.{ext}"


def generate_metadata_key(
    consumer_number: str,
    username: str,
    year: int | None = None,
    month: int | None = None,
) -> str:
    if year is None or month is None:
        year, month = _current_ym()
    safe_num = _safe_path_component(consumer_number)
    safe_user = _safe_path_component(username)
    return f"{year}/{month:02d}/{safe_user}/{safe_num}/{safe_num}.json"


def upload_file(data: bytes, object_key: str, content_type: str) -> None:
    _put_object(object_key, data, content_type)


def upload_metadata(meta: dict, object_key: str) -> None:
    """Upload submission JSON and propagate failures to the submission transaction."""
    put_json_object(object_key, meta)


def delete_file(object_key: str) -> None:
    _delete_object(object_key)
