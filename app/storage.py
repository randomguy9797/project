import uuid
import json
import logging
from datetime import datetime, timezone
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def generate_object_key(ext: str) -> str:
    now = datetime.now(timezone.utc)
    return f"uploads/{now.year}/{now.month:02d}/{uuid.uuid4()}.{ext}"


def upload_file(data: bytes, object_key: str, content_type: str) -> None:
    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("Uploaded file to R2: %s", object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.error("R2 upload failed for key %s: %s", object_key, exc)
        raise


def upload_metadata(meta: dict, base_key: str) -> str:
    """Upload a JSON sidecar file next to the uploaded document.
    base_key example: uploads/2024/01/<uuid>.pdf
    Returns the metadata object key.
    """
    meta_key = base_key.rsplit(".", 1)[0] + ".json"
    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=meta_key,
            Body=json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Uploaded metadata to R2: %s", meta_key)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("R2 metadata upload failed for key %s: %s", meta_key, exc)
    return meta_key


def delete_file(object_key: str) -> None:
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_key)
        logger.info("Deleted R2 object: %s", object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("R2 delete failed for key %s: %s", object_key, exc)


CONTENT_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}
