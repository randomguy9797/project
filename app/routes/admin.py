import logging
from fastapi import APIRouter, Request, Response, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.sessions import get_current_username
from app.user_store import get_user
from app.csrf import generate_csrf_token, validate_csrf
from app.validators import validate_upload
from app.storage import admin_upload_document, find_consumer_document

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


@router.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request, response: Response):
    user = _require_admin(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    csrf_token = generate_csrf_token(response)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "success": None,
            "error": None,
            "target_username": "",
            "consumer_number": "",
        },
        headers=dict(response.headers),
    )


@router.post("/admin", response_class=HTMLResponse)
async def admin_post(
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    target_username: str = Form(...),
    consumer_number: str = Form(...),
    upload_doc: UploadFile = File(...),
):
    user = _require_admin(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    def re_render(error: str, success: str = None):
        new_csrf = generate_csrf_token(response)
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "csrf_token": new_csrf,
                "success": success,
                "error": error,
                "target_username": target_username,
                "consumer_number": consumer_number,
            },
            status_code=422 if error else 200,
            headers=dict(response.headers),
        )

    if not validate_csrf(request, csrf_token):
        return re_render("Invalid request. Please try again.")

    target_username = target_username.strip()
    if not target_username:
        return re_render("Username is required.")

    target_user = get_user(target_username)
    if not target_user or not target_user.get("is_active"):
        return re_render(f"User '{target_username}' does not exist or is inactive.")

    consumer_number = consumer_number.strip()
    if not consumer_number:
        return re_render("Consumer Number is required.")

    try:
        file_data, ext, original_filename = await validate_upload(upload_doc)
    except ValueError as exc:
        return re_render(str(exc))

    # Check if replacing an existing record for this username+consumer
    existing = find_consumer_document(consumer_number)
    replacing = existing is not None and existing.get("assigned_to") == target_username

    try:
        admin_upload_document(
            consumer_number=consumer_number,
            target_username=target_username,
            file_data=file_data,
            original_filename=original_filename,
            ext=ext,
            uploaded_by=user["username"],
        )
    except Exception:
        logger.exception("Admin upload failed for consumer %s", consumer_number)
        return re_render("Upload failed. Please check R2 configuration and try again.")

    msg = (
        f"Document replaced for '{target_username}' / Consumer {consumer_number}. Download count reset to 0/3."
        if replacing
        else f"Document uploaded for '{target_username}' / Consumer {consumer_number}."
    )
    logger.info("Admin '%s' %s for user '%s', consumer %s", user["username"], "replaced" if replacing else "uploaded", target_username, consumer_number)
    return re_render(error=None, success=msg)
