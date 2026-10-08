import logging
from urllib.parse import quote
from fastapi import APIRouter, Request, Response, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.sessions import get_current_username
from app.user_store import get_user, get_all_users, create_user, update_user, delete_user
from app.auth import hash_password
from app.csrf import generate_csrf_token, validate_csrf
from app.validators import validate_upload
from app.storage import (
    admin_upload_document, find_consumer_document,
    list_consumer_users, get_consumer_details, get_consumer_doc_bytes,
)

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request) -> dict | None:
    username = get_current_username(request)
    if not username:
        return None
    user = get_user(username)
    if not user or not user.get("is_active") or not user.get("is_admin"):
        return None
    return user


def _render(request, response, *, success=None, error=None, upload_values=None, user_success=None, user_error=None):
    csrf_token = generate_csrf_token(response)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "success": success,
            "error": error,
            "upload_values": upload_values or {},
            "user_success": user_success,
            "user_error": user_error,
            "users": get_all_users(),
        },
        headers=dict(response.headers),
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request, response: Response):
    if not _require_admin(request):
        return RedirectResponse("/login", status_code=302)
    return _render(request, response)


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------

@router.post("/admin/upload", response_class=HTMLResponse)
async def admin_upload(
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    target_username: str = Form(...),
    consumer_number: str = Form(...),
    upload_doc: UploadFile = File(...),
):
    if not _require_admin(request):
        return RedirectResponse("/login", status_code=302)

    upload_values = {"target_username": target_username, "consumer_number": consumer_number}

    if not validate_csrf(request, csrf_token):
        return _render(request, response, error="Invalid request. Please try again.", upload_values=upload_values)

    target_username = target_username.strip()
    consumer_number = consumer_number.strip()

    if not target_username:
        return _render(request, response, error="Username is required.", upload_values=upload_values)
    target_user = get_user(target_username)
    if not target_user or not target_user.get("is_active"):
        return _render(request, response, error=f"User '{target_username}' does not exist or is inactive.", upload_values=upload_values)
    if not consumer_number:
        return _render(request, response, error="Consumer Number is required.", upload_values=upload_values)

    try:
        file_data, ext, original_filename = await validate_upload(upload_doc)
    except ValueError as exc:
        return _render(request, response, error=str(exc), upload_values=upload_values)

    existing = find_consumer_document(consumer_number)
    replacing = existing is not None and existing.get("assigned_to") == target_username

    try:
        admin_upload_document(
            consumer_number=consumer_number,
            target_username=target_username,
            file_data=file_data,
            original_filename=original_filename,
            ext=ext,
            uploaded_by=get_current_username(request),
        )
    except Exception as exc:
        logger.exception("Admin upload failed for consumer %s: %s", consumer_number, exc)
        return _render(request, response, error=f"Upload failed: {exc}", upload_values=upload_values)

    msg = (
        f"Document replaced for '{target_username}' / Consumer {consumer_number}. Downloads reset to 0/3."
        if replacing
        else f"Document uploaded for '{target_username}' / Consumer {consumer_number}."
    )
    return _render(request, response, success=msg)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.post("/admin/user/add", response_class=HTMLResponse)
async def admin_user_add(
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    new_username: str = Form(...),
    new_password: str = Form(...),
    new_is_admin: str = Form(""),
):
    if not _require_admin(request):
        return RedirectResponse("/login", status_code=302)
    if not validate_csrf(request, csrf_token):
        return _render(request, response, user_error="Invalid request. Please try again.")

    new_username = new_username.strip()
    if not new_username or not new_password:
        return _render(request, response, user_error="Username and password are required.")

    try:
        create_user(new_username, hash_password(new_password), is_admin=bool(new_is_admin))
    except ValueError as exc:
        return _render(request, response, user_error=str(exc))

    return _render(request, response, user_success=f"User '{new_username}' created.")


@router.post("/admin/user/edit", response_class=HTMLResponse)
async def admin_user_edit(
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    edit_username: str = Form(...),
    edit_new_username: str = Form(""),
    edit_new_password: str = Form(""),
):
    if not _require_admin(request):
        return RedirectResponse("/login", status_code=302)
    if not validate_csrf(request, csrf_token):
        return _render(request, response, user_error="Invalid request. Please try again.")

    edit_username = edit_username.strip()
    edit_new_username = edit_new_username.strip() or None
    new_hash = hash_password(edit_new_password) if edit_new_password.strip() else None

    if not edit_new_username and not new_hash:
        return _render(request, response, user_error="Provide a new username or new password to update.")

    try:
        update_user(edit_username, edit_new_username, new_hash)
    except ValueError as exc:
        return _render(request, response, user_error=str(exc))

    return _render(request, response, user_success=f"User '{edit_username}' updated.")


@router.post("/admin/user/delete", response_class=HTMLResponse)
async def admin_user_delete(
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    del_username: str = Form(...),
):
    admin = _require_admin(request)
    if not admin:
        return RedirectResponse("/login", status_code=302)
    if not validate_csrf(request, csrf_token):
        return _render(request, response, user_error="Invalid request. Please try again.")

    del_username = del_username.strip()
    if del_username == admin["username"]:
        return _render(request, response, user_error="You cannot delete your own account.")

    try:
        delete_user(del_username)
    except ValueError as exc:
        return _render(request, response, user_error=str(exc))

    return _render(request, response, user_success=f"User '{del_username}' deleted.")


# ---------------------------------------------------------------------------
# User Data API — admin-only JSON/stream endpoints, called via fetch from /admin
# ---------------------------------------------------------------------------

@router.get("/admin/user-data")
async def admin_user_data(request: Request):
    if not _require_admin(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    try:
        users = list_consumer_users()
    except Exception as exc:
        logger.exception("Failed to list consumer users: %s", exc)
        return JSONResponse({"error": "Failed to load user data."}, status_code=500)
    return JSONResponse({"users": users})


@router.get("/admin/consumer-details")
async def admin_consumer_details(request: Request, username: str = Query(...)):
    if not _require_admin(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    username = username.strip()
    if not username:
        return JSONResponse({"error": "Username is required."}, status_code=400)
    try:
        consumers = get_consumer_details(username)
    except Exception as exc:
        logger.exception("Failed to get consumer details for '%s': %s", username, exc)
        return JSONResponse({"error": "Failed to load consumer details."}, status_code=500)
    return JSONResponse({"username": username, "consumers": consumers})


@router.get("/admin/consumer-doc")
async def admin_consumer_doc(
    request: Request,
    key: str = Query(...),
    disposition: str = Query("inline"),
):
    if not _require_admin(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    key = key.strip()
    if not key or ".." in key or key.startswith("/"):
        return JSONResponse({"error": "Invalid document key."}, status_code=400)

    try:
        data, content_type = get_consumer_doc_bytes(key)
    except Exception as exc:
        logger.exception("Failed to fetch consumer doc '%s': %s", key, exc)
        return JSONResponse({"error": "Failed to retrieve document."}, status_code=500)

    if data is None or not content_type:
        return JSONResponse({"error": "Document not found or access denied."}, status_code=404)

    filename = key.rsplit("/", 1)[-1]
    cd = "inline" if disposition == "inline" else "attachment"
    headers = {"Content-Disposition": f'{cd}; filename="{quote(filename)}"'}
    return StreamingResponse(iter([data]), media_type=content_type, headers=headers)
