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
    csrf_token: str = Form(...),
    wss_service: str = Form(...),
    consumer_number: str = Form(...),
    consumer_first_name: str = Form(...),
    consumer_second_name: str = Form(""),
    consumer_last_name: str = Form(...),
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
    upload_aadhar: UploadFile = File(...),
    upload_pan: UploadFile = File(...),
    upload_ownership: UploadFile = File(...),
    upload_bond: UploadFile = File(None),
    upload_energy_bill: UploadFile = File(None),
    upload_other: UploadFile = File(None),
):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    values = {
        "wss_service": wss_service, "consumer_number": consumer_number,
        "consumer_first_name": consumer_first_name, "consumer_second_name": consumer_second_name,
        "consumer_last_name": consumer_last_name, "application_id": application_id,
        "new_first_name": new_first_name, "new_second_name": new_second_name,
        "new_last_name": new_last_name, "email": email, "mobile_number": mobile_number,
        "reason_name_change": reason_name_change, "category": category,
        "address": address, "account_number": account_number, "ifsc_code": ifsc_code,
    }

    def re_render(error: str):
        new_csrf = generate_csrf_token(response)
        logout_csrf = generate_csrf_token(response)
        return templates.TemplateResponse(
            "form.html",
            {"request": request, "csrf_token": new_csrf, "logout_csrf": logout_csrf, "error": error, "values": values},
            status_code=422,
            headers=dict(response.headers),
        )

    if not validate_csrf(request, csrf_token):
        return re_render("Invalid request. Please try again.")
    if not wss_service.strip():
        return re_render("WSS Service is required.")
    if not consumer_number.strip():
        return re_render("Consumer Number is required.")
    if not consumer_first_name.strip() or not consumer_last_name.strip():
        return re_render("Consumer First Name and Last Name are required.")
    if mobile_number.strip() and not validate_mobile(mobile_number.strip()):
        return re_render("Phone Number must be a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")

    uploaded_keys = []
    mandatory_uploads = [
        (upload_aadhar, "Aadhar"),
        (upload_pan, "PAN Card"),
        (upload_ownership, "Ownership Document"),
    ]
    optional_uploads = [
        (upload_bond, "Bond"),
        (upload_energy_bill, "Energy Bill"),
        (upload_other, "Other Documents"),
    ]

    async def process_upload(uf, label):
        try:
            file_data, ext, original_filename = await validate_upload(uf)
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc
        key = generate_object_key(ext)
        ct = CONTENT_TYPES.get(ext, "application/octet-stream")
        upload_file(file_data, key, ct)
        return key, original_filename, len(file_data)

    try:
        for uf, label in mandatory_uploads:
            key, fname, size = await process_upload(uf, label)
            uploaded_keys.append((key, fname, size, label))
        for uf, label in optional_uploads:
            if uf and uf.filename:
                key, fname, size = await process_upload(uf, label)
                uploaded_keys.append((key, fname, size, label))
    except ValueError as exc:
        for key, _, _, _ in uploaded_keys:
            try:
                delete_file(key)
            except Exception:
                pass
        return re_render(str(exc))
    except Exception:
        for key, _, _, _ in uploaded_keys:
            try:
                delete_file(key)
            except Exception:
                pass
        return re_render("We couldn't submit your form. Please try again.")

    submitted_at = datetime.now(timezone.utc).isoformat()
    primary_key = uploaded_keys[0][0] if uploaded_keys else ""

    upload_metadata(
        {
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
            "submitted_by": user["username"],
            "submitted_at": submitted_at,
            "r2_object_key": primary_key,
        },
        primary_key,
    )

    logger.info("Submission by '%s', primary R2 key: %s", user["username"], primary_key)

    new_csrf = generate_csrf_token(response)
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "csrf_token": new_csrf},
        headers=dict(response.headers),
    )
