import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.user_store import get_user
from app.sessions import get_current_username
from app.csrf import generate_csrf_token, validate_csrf
from app.validators import validate_mobile, validate_upload
from app.storage import upload_file, upload_metadata, delete_file, generate_object_key, CONTENT_TYPES

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_user(request: Request) -> dict | None:
    username = get_current_username(request)
    if not username:
        return None
    user = get_user(username)
    if not user or not user.get("is_active"):
        return None
    return user


@router.get("/form", response_class=HTMLResponse)
async def form_get(request: Request, response: Response):
    if not _require_user(request):
        return RedirectResponse("/login", status_code=302)
    csrf_token = generate_csrf_token(response)
    logout_csrf = generate_csrf_token(response)
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "csrf_token": csrf_token, "logout_csrf": logout_csrf, "error": None, "values": {}},
        headers=dict(response.headers),
    )


@router.post("/form", response_class=HTMLResponse)
async def form_post(
    request: Request,
    response: Response,
    consumer_number: str = Form(...),
    consumer_new_name: str = Form(...),
    mobile_number: str = Form(...),
    csrf_token: str = Form(...),
    upload_file_field: UploadFile = File(..., alias="upload_file"),
):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    def re_render(error: str, values: dict):
        new_csrf = generate_csrf_token(response)
        logout_csrf = generate_csrf_token(response)
        return templates.TemplateResponse(
            "form.html",
            {"request": request, "csrf_token": new_csrf, "logout_csrf": logout_csrf, "error": error, "values": values},
            status_code=422,
            headers=dict(response.headers),
        )

    values = {
        "consumer_number": consumer_number,
        "consumer_new_name": consumer_new_name,
        "mobile_number": mobile_number,
    }

    if not validate_csrf(request, csrf_token):
        return re_render("Invalid request. Please try again.", values)

    consumer_number = consumer_number.strip()
    consumer_new_name = consumer_new_name.strip()
    mobile_number = mobile_number.strip()

    if not consumer_number:
        return re_render("Consumer Number is required.", values)
    if not consumer_new_name:
        return re_render("Consumer New Name is required.", values)
    if not mobile_number:
        return re_render("Mobile Number is required.", values)
    if not validate_mobile(mobile_number):
        return re_render("Mobile Number must be a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.", values)

    try:
        file_data, ext, original_filename = await validate_upload(upload_file_field)
    except ValueError as exc:
        return re_render(str(exc), values)

    object_key = generate_object_key(ext)
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

    try:
        upload_file(file_data, object_key, content_type)
    except Exception:
        return re_render("We couldn't submit your form. Please try again.", values)

    submitted_at = datetime.now(timezone.utc).isoformat()

    upload_metadata(
        {
            "consumer_number": consumer_number,
            "consumer_new_name": consumer_new_name,
            "mobile_number": mobile_number,
            "original_filename": original_filename,
            "file_size_bytes": len(file_data),
            "submitted_by": user["username"],
            "submitted_at": submitted_at,
            "r2_object_key": object_key,
        },
        object_key,
    )

    logger.info("Submission by '%s' uploaded to R2: %s", user["username"], object_key)

    new_csrf = generate_csrf_token(response)
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "csrf_token": new_csrf},
        headers=dict(response.headers),
    )
