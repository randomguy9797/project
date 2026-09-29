import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.user_store import get_user
from app.sessions import get_current_username
from app.csrf import generate_csrf_token, validate_csrf
from app.validators import validate_mobile, validate_upload
from app.storage import (
    current_year_month, upload_file, upload_metadata, delete_file, generate_object_key, generate_metadata_key, CONTENT_TYPES,
    find_documents_for_user, attempt_download_by_username, MAX_DOWNLOADS,
)

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


def _form_context(request: Request, response: Response, username: str, error=None, values=None, status=200):
    csrf_token = generate_csrf_token(response)
    admin_docs = find_documents_for_user(username)
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": error,
            "values": values or {},
            "admin_docs": admin_docs,
            "max_downloads": MAX_DOWNLOADS,
        },
        status_code=status,
        headers=dict(response.headers),
    )


@router.get("/form", response_class=HTMLResponse)
async def form_get(request: Request, response: Response):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return _form_context(request, response, user["username"])


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

    def err(msg, status=422):
        return _form_context(request, response, user["username"], error=msg, values=values, status=status)

    if not validate_csrf(request, csrf_token):
        return err("Invalid request. Please try again.")
    if not wss_service.strip():
        return err("WSS Service is required.")
    if not consumer_number.strip():
        return err("Consumer Number is required.")
    if not consumer_first_name.strip() or not consumer_last_name.strip():
        return err("Consumer First Name and Last Name are required.")
    if mobile_number.strip() and not validate_mobile(mobile_number.strip()):
        return err("Phone Number must be a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")

    username = user["username"]
    normalized_consumer_number = consumer_number.strip()
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
        ]:
            key, fname, size = await process_upload(uf, label, slug)
            uploaded_keys.append((key, fname, size, label))
        for uf, label, slug in [
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
        return err(str(exc))
    except Exception:
        logger.exception("Consumer document upload failed for '%s' / %s", username, normalized_consumer_number)
        for key, _, _, _ in uploaded_keys:
            delete_file(key)
        return err("We couldn't submit your form. Please try again.", status=503)

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
        logger.exception("Submission metadata upload failed for '%s' / %s", username, normalized_consumer_number)
        for key, _, _, _ in uploaded_keys:
            delete_file(key)
        delete_file(metadata_key)
        return err("We couldn't submit your form. Please try again.", status=503)

    logger.info("Submission by '%s', metadata R2 key: %s", username, metadata_key)
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "csrf_token": generate_csrf_token(response)},
        headers=dict(response.headers),
    )


@router.post("/download", response_class=HTMLResponse)
async def download_post(
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    doc_key: str = Form(...),
):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if not validate_csrf(request, csrf_token):
        return _form_context(request, response, user["username"], error="Invalid request. Please try again.", status=403)

    file_bytes, record, err_msg = attempt_download_by_username(user["username"], doc_key)
    if err_msg:
        return _form_context(request, response, user["username"], error=err_msg, status=403)

    ext = doc_key.rsplit(".", 1)[-1].lower() if "." in doc_key else "pdf"
    filename = record.get("original_filename", f"document.{ext}")

    logger.info("User '%s' downloaded '%s'. Count: %d/%d",
                user["username"], doc_key, record["downloads"], MAX_DOWNLOADS)

    return StreamingResponse(
        iter([file_bytes]),
        media_type=CONTENT_TYPES.get(ext, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
