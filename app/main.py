import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes import auth, submissions, admin, api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Absolute paths so the app works regardless of working directory
# (local, Render, Vercel serverless)
_BASE_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _BASE_DIR / "static"
_TEMPLATES_DIR = _BASE_DIR / "templates"
_SPA_INDEX = _STATIC_DIR / "dist" / "index.html"
_SPA_ROUTES = {"/", "/login", "/form", "/success", "/admin", "/403"}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app.include_router(api.router)
app.include_router(auth.router)
app.include_router(submissions.router)
app.include_router(admin.router)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return templates.TemplateResponse("errors/403.html", {"request": request}, status_code=403)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path == "/api" or request.url.path.startswith("/api/"):
        return JSONResponse({"error": "API endpoint not found"}, status_code=404)
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.middleware("http")
async def serve_spa_routes(request: Request, call_next):
    if request.method == "GET" and request.url.path in _SPA_ROUTES and _SPA_INDEX.is_file():
        return FileResponse(str(_SPA_INDEX))
    return await call_next(request)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path == "api" or full_path.startswith(("api/", "static/", "health/")):
        raise HTTPException(status_code=404)
    if _SPA_INDEX.is_file():
        return FileResponse(str(_SPA_INDEX))
    raise HTTPException(status_code=404)


@app.on_event("startup")
async def startup():
    logger.info("Application starting up.")
    logger.info("Static dir : %s (exists=%s)", _STATIC_DIR, _STATIC_DIR.exists())
    logger.info("SPA index  : %s (exists=%s)", _SPA_INDEX, _SPA_INDEX.exists())
