import json
import logging
import os
import threading
from datetime import datetime, timezone
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local JSON store for admin-assigned document access
# ---------------------------------------------------------------------------

_ADMIN_DOCS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "admin_docs.json")
_admin_docs_lock = threading.Lock()


def _load_admin_docs() -> list[dict]:
    if not os.path.exists(_ADMIN_DOCS_FILE):
        return []
    with open(_ADMIN_DOCS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_admin_docs(docs: list[dict]) -> None:
    with open(_ADMIN_DOCS_FILE, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)


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
    now = datetime.now(timezone.utc)
    return now.year, now.month


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


def _list_prefix(prefix: str) -> list[str]:
    client = _get_client()
    keys = []
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.R2_BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
    except (BotoCoreError, ClientError) as exc:
        logger.error("R2 list failed prefix=%s: %s", prefix, exc)
    return keys


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
    prefix = f"{year}/{month:02d}/{consumer_number}/"
    doc_key = f"{prefix}document.{ext}"
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

    for k in _list_prefix(prefix):
        _delete_object(k)

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
        for i, d in enumerate(docs):
            if d["assigned_to"] == target_username and d["consumer_number"] == consumer_number:
                docs[i] = record
                break
        else:
            docs.append(record)
        _save_admin_docs(docs)

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

def generate_object_key(ext: str, consumer_number: str, doc_type: str) -> str:
    safe_num = consumer_number.strip().replace("/", "-")
    return f"uploads/{safe_num}_{doc_type}.{ext}"


def upload_file(data: bytes, object_key: str, content_type: str) -> None:
    _put_object(object_key, data, content_type)


def upload_metadata(meta: dict, base_key: str) -> None:
    meta_key = base_key.rsplit(".", 1)[0] + ".json"
    try:
        _put_object(
            meta_key,
            json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json",
        )
    except Exception:
        pass


def delete_file(object_key: str) -> None:
    _delete_object(object_key)
