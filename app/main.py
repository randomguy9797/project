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

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

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


_SPA_INDEX = Path("app/static/dist/index.html")
_SPA_ROUTES = {"/", "/login", "/form", "/success", "/admin", "/403"}


@app.middleware("http")
async def serve_spa_routes(request: Request, call_next):
    """Prefer Vue on its navigable routes once a production build exists.

    Before the first frontend build, requests continue to the established
    Jinja routes. This keeps the server usable during the staged migration.
    """
    if request.method == "GET" and request.url.path in _SPA_ROUTES and _SPA_INDEX.is_file():
        return FileResponse(_SPA_INDEX)
    return await call_next(request)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Serve the Vue SPA for any path not matched by an API or static route."""
    # Do not turn an unknown API or infrastructure URL into the SPA.  Clients
    # calling these paths must receive a normal 404 response instead.
    if full_path == "api" or full_path.startswith(("api/", "static/", "health/")):
        raise HTTPException(status_code=404)
    if _SPA_INDEX.is_file():
        return FileResponse(_SPA_INDEX)
    # Vue not built yet — let FastAPI's 404 handler respond
    raise HTTPException(status_code=404)


@app.on_event("startup")
async def startup():
    logger.info("Application starting up.")
