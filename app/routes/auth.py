import logging
from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import verify_password
from app.user_store import get_user
from app.sessions import create_session, delete_session, get_current_username
from app.csrf import generate_csrf_token, validate_csrf

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, response: Response):
    if get_current_username(request):
        return RedirectResponse("/form", status_code=302)
    csrf_token = generate_csrf_token(response)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "csrf_token": csrf_token, "error": None},
        headers=dict(response.headers),
    )


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    if not validate_csrf(request, csrf_token):
        new_csrf = generate_csrf_token(response)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": new_csrf, "error": "Invalid request. Please try again."},
            status_code=400,
            headers=dict(response.headers),
        )

    user = get_user(username)
    if not user or not user.get("is_active") or not verify_password(password, user["password_hash"]):
        logger.warning("Failed login attempt for username: %s", username)
        new_csrf = generate_csrf_token(response)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": new_csrf, "error": "Invalid username or password."},
            status_code=401,
            headers=dict(response.headers),
        )

    redirect = RedirectResponse("/form", status_code=302)
    create_session(redirect, user["username"])
    logger.info("User '%s' logged in successfully.", user["username"])
    return redirect


@router.post("/logout")
async def logout(request: Request, response: Response, csrf_token: str = Form(...)):
    if not validate_csrf(request, csrf_token):
        return RedirectResponse("/login", status_code=302)
    redirect = RedirectResponse("/login", status_code=302)
    delete_session(request, redirect)
    return redirect
