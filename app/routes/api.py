"""
JSON API layer for the Vue 3 frontend.

All business logic, validation, and storage operations are delegated to the
same modules used by the existing HTML routes. No logic is duplicated here.

CSRF strategy: the csrf_token cookie is non-HttpOnly (see app/csrf.py), so
Vue reads it via document.cookie and sends it as the X-CSRF-Token header.
Every state-changing endpoint reads the token from that header.
"""
import logging
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Request, Response, Form, UploadFile, File, Query
from fastapi.responses import JSONResponse, StreamingResponse

from app.auth import verify_password, hash_password
from app.csrf import generate_csrf_token, validate_csrf
from app.sessions import create_session, delete_session, get_current_username
from app.user_store import get_user, get_all_users, create_user, update_user, delete_user
from app.validators import validate_mobile, validate_upload
from app.storage import (
    CONTENT_TYPES, MAX_DOWNLOADS,
    current_year_month, upload_file, upload_metadata, delete_file,
    generate_object_key, generate_metadata_key,
    find_documents_for_user, attempt_download_by_username,
    admin_upload_document, find_consumer_document,
    list_consumer_users, get_consumer_details, get_consumer_doc_bytes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _csrf_header(request: Request) -> str:
    return request.headers.get("X-CSRF-Token", "")


def _require_user(request: Request) -> dict | None:
    username = get_current_username(request)
    if not username:
        return None
    user = get_user(username)
    if not user or not user.get("is_active"):
        return None
    return user


def _require_admin(request: Request) -> dict | None:
    user = _require_user(request)
    if not user or not user.get("is_admin"):
        return None
    return user


def _unauth() -> JSONResponse:
    return JSONResponse({"error": "Unauthorized"}, status_code=401)


def _forbidden() -> JSONResponse:
    return JSONResponse({"error": "Forbidden"}, status_code=403)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.get("/csrf")
async def api_csrf(response: Response):
    """Issue a fresh CSRF token. Vue calls this once on app mount."""
    token = generate_csrf_token(response)
    return JSONResponse({"csrf_token": token}, headers=dict(response.headers))


@router.get("/me")
async def api_me(request: Request):
    user = _require_user(request)
    if not user:
        return _unauth()
    return JSONResponse({
        "username": user["username"],
        "is_admin": bool(user.get("is_admin")),
    })


@router.post("/login")
async def api_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    user = get_user(username)
    if not user or not user.get("is_active") or not verify_password(password, user["password_hash"]):
        logger.warning("Failed API login attempt for username: %s", username)
        return JSONResponse({"error": "Invalid username or password."}, status_code=401)

    result = JSONResponse({"ok": True, "is_admin": bool(user.get("is_admin"))})
    create_session(result, user["username"])
    logger.info("User '%s' logged in via API.", user["username"])
    return result


@router.get("/logout")
async def api_logout(request: Request):
    response = JSONResponse({"ok": True})
    delete_session(request, response)
    return response


# ---------------------------------------------------------------------------
# Submission form
# ---------------------------------------------------------------------------

@router.get("/form-data")
async def api_form_data(request: Request):
    """Return the data needed to render the form: admin docs for this user."""
    user = _require_user(request)
    if not user:
        return _unauth()
    docs = find_documents_for_user(user["username"])
    return JSONResponse({"admin_docs": docs, "max_downloads": MAX_DOWNLOADS})


@router.post("/form")
async def api_form_post(
    request: Request,
    wss_service: str = Form(""),
    consumer_number: str = Form(""),
    consumer_first_name: str = Form(""),
    consumer_second_name: str = Form(""),
    consumer_last_name: str = Form(""),
    application_id: str = Form(""),
    new_first_name: str = Form(""),
    new_second_name: str = Form(""),
    new_last_name: str = Form(""),
    email: str = Form(""),
    mobile_number: str = Form(""),
    reason_name_change: str = Form(""),
    category: str = Form(""),
    address: str = Form(""),
    account_number: str = Form(""),
    ifsc_code: str = Form(""),
    upload_aadhar: UploadFile | None = File(None),
    upload_pan: UploadFile | None = File(None),
    upload_ownership: UploadFile | None = File(None),
    upload_bond: UploadFile | None = File(None),
    upload_energy_bill: UploadFile | None = File(None),
    upload_other: UploadFile | None = File(None),
):
    user = _require_user(request)
    if not user:
        return _unauth()

    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    if mobile_number.strip() and not validate_mobile(mobile_number.strip()):
        return JSONResponse(
            {"error": "Phone Number must be a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9."},
            status_code=422,
        )

    username = user["username"]
    normalized_consumer_number = consumer_number.strip() or f"submission-{uuid4().hex}"
    submission_year, submission_month = current_year_month()
    uploaded_keys = []

    async def process_upload(uf, label, doc_type_slug):
        try:
            file_data, ext, original_filename = await validate_upload(uf)
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc
        key = generate_object_key(
            ext, normalized_consumer_number, doc_type_slug, username, submission_year, submission_month
        )
        upload_file(file_data, key, CONTENT_TYPES.get(ext, "application/octet-stream"))
        return key, original_filename, len(file_data)

    try:
        for uf, label, slug in [
            (upload_aadhar,    "Aadhar",             "aadhar"),
            (upload_pan,       "PAN Card",           "pan"),
            (upload_ownership, "Ownership Document", "ownership"),
            (upload_bond,        "Bond",            "bond"),
            (upload_energy_bill, "Energy Bill",     "energy_bill"),
            (upload_other,       "Other Documents", "other_documents"),
        ]:
            if uf and uf.filename:
                key, fname, size = await process_upload(uf, label, slug)
                uploaded_keys.append((key, fname, size, label))
    except ValueError as exc:
        for key, _, _, _ in uploaded_keys:
            try:
                delete_file(key)
            except Exception:
                pass
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception:
        logger.exception("API form upload failed for '%s' / %s", username, normalized_consumer_number)
        for key, _, _, _ in uploaded_keys:
            delete_file(key)
        return JSONResponse({"error": "We couldn't submit your form. Please try again."}, status_code=503)

    metadata_key = generate_metadata_key(
        normalized_consumer_number, username, submission_year, submission_month
    )
    metadata = {
        "wss_service": wss_service,
        "consumer_number": consumer_number,
        "consumer_name": f"{consumer_first_name} {consumer_second_name} {consumer_last_name}".strip(),
        "application_id": application_id,
        "consumer_new_name": f"{new_first_name} {new_second_name} {new_last_name}".strip(),
        "email": email,
        "mobile_number": mobile_number,
        "reason_name_change": reason_name_change,
        "category": category,
        "address": address,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "uploaded_files": [{"label": lbl, "key": k, "filename": fn, "size": sz} for k, fn, sz, lbl in uploaded_keys],
        "submitted_by": username,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "r2_object_key": metadata_key,
    }
    try:
        upload_metadata(metadata, metadata_key)
    except Exception:
        logger.exception("API metadata upload failed for '%s' / %s", username, normalized_consumer_number)
        for key, _, _, _ in uploaded_keys:
            delete_file(key)
        delete_file(metadata_key)
        return JSONResponse({"error": "We couldn't submit your form. Please try again."}, status_code=503)

    logger.info("API submission by '%s', metadata R2 key: %s", username, metadata_key)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Document download (user)
# ---------------------------------------------------------------------------

@router.post("/download")
async def api_download(
    request: Request,
    doc_key: str = Form(...),
):
    user = _require_user(request)
    if not user:
        return _unauth()

    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    file_bytes, record, err_msg = attempt_download_by_username(user["username"], doc_key)
    if err_msg:
        return JSONResponse({"error": err_msg}, status_code=403)

    ext = doc_key.rsplit(".", 1)[-1].lower() if "." in doc_key else "pdf"
    filename = record.get("original_filename", f"document.{ext}")

    logger.info("API download by '%s': '%s'. Count: %d/%d",
                user["username"], doc_key, record["downloads"], MAX_DOWNLOADS)

    return StreamingResponse(
        iter([file_bytes]),
        media_type=CONTENT_TYPES.get(ext, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Admin — document upload
# ---------------------------------------------------------------------------

@router.post("/admin/upload")
async def api_admin_upload(
    request: Request,
    target_username: str = Form(...),
    consumer_number: str = Form(...),
    upload_doc: UploadFile = File(...),
):
    admin = _require_admin(request)
    if not admin:
        return _forbidden()

    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    target_username = target_username.strip()
    consumer_number = consumer_number.strip()

    if not target_username:
        return JSONResponse({"error": "Username is required."}, status_code=422)
    target_user = get_user(target_username)
    if not target_user or not target_user.get("is_active"):
        return JSONResponse({"error": f"User '{target_username}' does not exist or is inactive."}, status_code=422)
    if not consumer_number:
        return JSONResponse({"error": "Consumer Number is required."}, status_code=422)

    try:
        file_data, ext, original_filename = await validate_upload(upload_doc)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    existing = find_consumer_document(consumer_number)
    replacing = existing is not None and existing.get("assigned_to") == target_username

    try:
        admin_upload_document(
            consumer_number=consumer_number,
            target_username=target_username,
            file_data=file_data,
            original_filename=original_filename,
            ext=ext,
            uploaded_by=admin["username"],
        )
    except Exception as exc:
        logger.exception("API admin upload failed for consumer %s: %s", consumer_number, exc)
        return JSONResponse({"error": f"Upload failed: {exc}"}, status_code=500)

    msg = (
        f"Document replaced for '{target_username}' / Consumer {consumer_number}. Downloads reset to 0/{MAX_DOWNLOADS}."
        if replacing
        else f"Document uploaded for '{target_username}' / Consumer {consumer_number}."
    )
    return JSONResponse({"ok": True, "message": msg})


# ---------------------------------------------------------------------------
# Admin — user management
# ---------------------------------------------------------------------------

@router.get("/admin/users")
async def api_admin_users(request: Request):
    if not _require_admin(request):
        return _forbidden()
    return JSONResponse({"users": get_all_users()})


@router.post("/admin/user/add")
async def api_admin_user_add(
    request: Request,
    new_username: str = Form(...),
    new_password: str = Form(...),
    new_is_admin: str = Form(""),
):
    if not _require_admin(request):
        return _forbidden()
    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    new_username = new_username.strip()
    if not new_username or not new_password:
        return JSONResponse({"error": "Username and password are required."}, status_code=422)

    try:
        create_user(new_username, hash_password(new_password), is_admin=bool(new_is_admin))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    return JSONResponse({"ok": True, "message": f"User '{new_username}' created."})


@router.post("/admin/user/edit")
async def api_admin_user_edit(
    request: Request,
    edit_username: str = Form(...),
    edit_new_username: str = Form(""),
    edit_new_password: str = Form(""),
):
    if not _require_admin(request):
        return _forbidden()
    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    edit_username = edit_username.strip()
    edit_new_username = edit_new_username.strip() or None
    new_hash = hash_password(edit_new_password) if edit_new_password.strip() else None

    if not edit_new_username and not new_hash:
        return JSONResponse({"error": "Provide a new username or new password to update."}, status_code=422)

    try:
        update_user(edit_username, edit_new_username, new_hash)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    return JSONResponse({"ok": True, "message": f"User '{edit_username}' updated."})


@router.post("/admin/user/delete")
async def api_admin_user_delete(
    request: Request,
    del_username: str = Form(...),
):
    admin = _require_admin(request)
    if not admin:
        return _forbidden()
    if not validate_csrf(request, _csrf_header(request)):
        return JSONResponse({"error": "Invalid request. Please try again."}, status_code=400)

    del_username = del_username.strip()
    if del_username == admin["username"]:
        return JSONResponse({"error": "You cannot delete your own account."}, status_code=422)

    try:
        delete_user(del_username)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    return JSONResponse({"ok": True, "message": f"User '{del_username}' deleted."})


# ---------------------------------------------------------------------------
# Admin — consumer data (proxied from existing admin routes, same auth)
# ---------------------------------------------------------------------------

@router.get("/admin/user-data")
async def api_admin_user_data(request: Request):
    if not _require_admin(request):
        return _forbidden()
    try:
        users = list_consumer_users()
    except Exception as exc:
        logger.exception("API: failed to list consumer users: %s", exc)
        return JSONResponse({"error": "Failed to load user data."}, status_code=500)
    return JSONResponse({"users": users})


@router.get("/admin/consumer-details")
async def api_admin_consumer_details(request: Request, username: str = Query(...)):
    if not _require_admin(request):
        return _forbidden()
    username = username.strip()
    if not username:
        return JSONResponse({"error": "Username is required."}, status_code=400)
    try:
        consumers = get_consumer_details(username)
    except Exception as exc:
        logger.exception("API: failed to get consumer details for '%s': %s", username, exc)
        return JSONResponse({"error": "Failed to load consumer details."}, status_code=500)
    return JSONResponse({"username": username, "consumers": consumers})


@router.get("/admin/consumer-doc")
async def api_admin_consumer_doc(
    request: Request,
    key: str = Query(...),
    disposition: str = Query("inline"),
):
    if not _require_admin(request):
        return _forbidden()

    key = key.strip()
    if not key or ".." in key or key.startswith("/"):
        return JSONResponse({"error": "Invalid document key."}, status_code=400)

    try:
        data, content_type = get_consumer_doc_bytes(key)
    except Exception as exc:
        logger.exception("API: failed to fetch consumer doc '%s': %s", key, exc)
        return JSONResponse({"error": "Failed to retrieve document."}, status_code=500)

    if data is None or not content_type:
        return JSONResponse({"error": "Document not found or access denied."}, status_code=404)

    filename = key.rsplit("/", 1)[-1]
    cd = "inline" if disposition == "inline" else "attachment"
    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={"Content-Disposition": f'{cd}; filename="{quote(filename)}"'},
    )
