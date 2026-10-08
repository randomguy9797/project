import re
from fastapi import UploadFile

MOBILE_RE = re.compile(r"^[6-9][0-9]{9}$")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg"}

# Magic bytes for file type detection
_MAGIC = {
    b"%PDF": "pdf",
    b"\xff\xd8\xff": "jpg",
}


def validate_mobile(number: str) -> bool:
    return bool(MOBILE_RE.match(number))


def detect_file_type(header: bytes) -> str | None:
    for magic, ext in _MAGIC.items():
        if header.startswith(magic):
            return ext
    return None


async def validate_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """
    Reads the file, validates size and type.
    Returns (file_bytes, detected_extension, original_filename).
    Raises ValueError with a user-friendly message on failure.
    """
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 10 MB maximum size.")

    if not data:
        raise ValueError("Uploaded file is empty.")

    ext = detect_file_type(data[:8])
    if ext is None:
        raise ValueError("Invalid file type. Allowed formats: PDF, JPG, JPEG.")

    filename = file.filename or "upload"
    name_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if name_ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Invalid file type. Allowed formats: PDF, JPG, JPEG.")

    return data, ext, filename
