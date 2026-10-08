# Consumer Portal

A production-ready web application for submitting consumer details and file uploads. Built with FastAPI (backend), Vue 3 (frontend), Cloudflare D1 (user database), and Cloudflare R2 (file storage).

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Technology Stack](#technology-stack)
5. [Requirements](#requirements)
6. [Project Structure](#project-structure)
7. [Local Development Setup](#local-development-setup)
   - [Clone & Virtual Environment](#1-clone--virtual-environment)
   - [Install Dependencies](#2-install-dependencies)
   - [Configure Environment Variables](#3-configure-environment-variables)
   - [Apply D1 Schema](#4-apply-d1-schema)
   - [Seed Initial Users](#5-seed-initial-users)
   - [Run Locally](#6-run-locally)
8. [User Management](#user-management)
9. [Cloudflare R2 Setup](#cloudflare-r2-setup)
10. [Cloudflare D1 Setup](#cloudflare-d1-setup)
11. [Render Deployment](#render-deployment)
12. [Vercel Deployment](#vercel-deployment)
13. [Testing](#testing)
14. [Environment Variables Reference](#environment-variables-reference)
15. [Troubleshooting](#troubleshooting)
16. [Security Notes](#security-notes)

---

## Project Overview

Consumer Portal allows authenticated users to submit consumer details along with document uploads (PDF/JPG). The admin can upload documents for users to download (with a 2-download limit). User accounts are stored in Cloudflare D1 (SQLite). All files and submission metadata are stored in Cloudflare R2 and automatically deleted after 10 days.

Expected traffic: fewer than ~500 submissions per month.

---

## Features

- Secure login with Argon2id password hashing
- Server-side session authentication (1-hour expiry, HTTPOnly cookies)
- CSRF protection on all state-changing requests
- Vue 3 SPA frontend (served by FastAPI in production)
- Admin panel: upload documents for users, manage user accounts
- Per-user document download with a 2-download limit
- Submission form with server-side validation
- Indian 10-digit mobile number validation
- File upload (PDF, JPG, JPEG) with magic-byte type detection
- 10 MB file size limit
- Private Cloudflare R2 file storage with structured object keys
- Automatic R2 file deletion after 10 days via lifecycle rules
- Submission metadata stored as JSON in R2
- User accounts stored in Cloudflare D1 (SQLite REST API)
- Partial failure handling (R2 orphan cleanup on metadata failure)
- Mobile-first responsive UI
- Friendly 403 / 404 / 500 error pages
- CLI tools for user seeding and management

---

## Architecture

```
Browser (Vue 3 SPA)
   |
   v
FastAPI (Render / Vercel)
   |
   +---- Cloudflare D1 (users table)
   |
   +---- Cloudflare R2
            |
            +---- Submission documents  (YYYY/MM/<user>/<consumer>/)
            +---- Admin-assigned docs   (YYYY/MM/<user>/download/)
            +---- Submission metadata   (YYYY/MM/<user>/<consumer>/<consumer>.json)
            +---- Admin docs index      (admin_docs.json)
            |
            +---- Automatic deletion after 10 days
```

Authentication flow:

```
Browser → /api/csrf → GET CSRF token
Browser → /api/login (POST) → FastAPI → D1 user verification
       → Secure HTTPOnly session cookie → Vue SPA navigates to /form
```

---

## Technology Stack

| Layer         | Technology                        |
|---------------|-----------------------------------|
| Language      | Python 3.12+                      |
| Web framework | FastAPI                           |
| Frontend      | Vue 3 + Vue Router (Vite build)   |
| Templates     | Jinja2 (legacy HTML routes)       |
| Database      | Cloudflare D1 (SQLite REST API)   |
| File storage  | Cloudflare R2 (S3-compatible)     |
| R2 client     | boto3                             |
| D1 client     | httpx (REST API)                  |
| Password hash | Argon2id (argon2-cffi)            |
| Server        | Uvicorn                           |
| Hosting       | Render or Vercel                  |

---

## Requirements

- Python 3.12 or higher
- Node.js 18 or higher (for frontend build)
- A Cloudflare account with R2 and D1 enabled

---

## Project Structure

```
project/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routers, SPA serving, error handlers
│   ├── config.py        # Settings loaded from environment variables
│   ├── auth.py          # Argon2id password hashing/verification
│   ├── sessions.py      # Server-side session management
│   ├── csrf.py          # CSRF token generation and validation
│   ├── storage.py       # Cloudflare R2 upload/download/delete via boto3
│   ├── validators.py    # Mobile number and file type validation
│   ├── user_store.py    # User CRUD (delegates to d1.py)
│   ├── d1.py            # Cloudflare D1 REST API client
│   │
│   ├── routes/
│   │   ├── api.py           # JSON API for Vue frontend (/api/*)
│   │   ├── auth.py          # Legacy HTML login/logout routes
│   │   ├── submissions.py   # Legacy HTML form route
│   │   └── admin.py         # Legacy HTML admin routes
│   │
│   ├── templates/           # Jinja2 HTML templates (legacy / fallback)
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── form.html
│   │   ├── success.html
│   │   ├── admin.html
│   │   └── errors/
│   │       ├── 403.html
│   │       ├── 404.html
│   │       └── 500.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── dist/            # Vue production build output (git-ignored)
│           └── index.html
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js    # Axios-style fetch wrapper for /api/*
│   │   ├── views/
│   │   │   ├── LoginView.vue
│   │   │   ├── FormView.vue
│   │   │   ├── AdminView.vue
│   │   │   └── SuccessView.vue
│   │   ├── router/
│   │   │   └── index.js
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js       # Builds to ../app/static/dist/
│
├── migrations/
│   └── d1/
│       └── 0001_users.sql   # D1 users table schema
│
├── scripts/
│   ├── seed_users.py        # Create the initial 3 users in D1
│   ├── manage_user.py       # Change username, password, or consumer number
│   ├── apply_d1_schema.py   # Apply D1 migrations via REST API
│   ├── migrate_users_r2_to_d1.py
│   └── cleanup_r2_users.py
│
├── tests/
│   ├── __init__.py
│   └── test_d1_user_store.py
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Local Development Setup

### 1. Clone & Virtual Environment

```bash
git clone <your-repo-url>
cd project

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Python backend
pip install -r requirements.txt

# Vue frontend
cd frontend
npm install
cd ..
```

### 3. Configure Environment Variables

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your values:

```env
APP_ENV=development
SECRET_KEY=replace-with-a-long-random-secret

SESSION_MAX_AGE=3600

R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<r2_access_key_id>
R2_SECRET_ACCESS_KEY=<r2_secret_access_key>
R2_BUCKET_NAME=<r2_bucket_name>

CLOUDFLARE_ACCOUNT_ID=<cloudflare_account_id>
CLOUDFLARE_D1_DATABASE_ID=<d1_database_id>
CLOUDFLARE_API_TOKEN=<cloudflare_api_token_with_d1_edit_permission>
```

> To generate a strong SECRET_KEY:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 4. Apply D1 Schema

Create the `users` and `submissions` tables in your D1 database. The
`submissions` table tracks payment status for every completed form.

**Option A — via the Cloudflare Dashboard SQL console:**

Copy and run `migrations/d1/0001_users.sql`, then
`migrations/d1/0002_submissions.sql`, in the D1 SQL console.

**Option B — via Wrangler CLI:**

```bash
wrangler d1 execute <YOUR_DB_NAME> --file=migrations/d1/0001_users.sql
wrangler d1 execute <YOUR_DB_NAME> --file=migrations/d1/0002_submissions.sql
```

**Option C — via the apply script:**

```bash
python scripts/apply_d1_schema.py
```

### 4a. Backfill existing submissions

After applying the new submissions migration to an existing deployment, import
payment records for metadata already in R2:

```bash
python scripts/backfill_submissions.py
```

The backfill is idempotent: it creates only missing rows and never overwrites a
payment status already set by an administrator. Use `--dry-run` to review the
R2 records first.

### 5. Seed Initial Users

```bash
python scripts/seed_users.py
```

You will be prompted to enter a username and password for each of the 3 users. The first user created is automatically the admin.

Example session:

```
Creating 3 users. The first user will be an admin.

Username for user 1: alice
Password for user 1:
Confirm password for user 1:
User 1 created as admin.

Username for user 2: bob
Password for user 2:
Confirm password for user 2:
User 2 created as standard user.

Username for user 3: carol
Password for user 3:
Confirm password for user 3:
User 3 created as standard user.

All 3 users created successfully.
```

### 6. Run Locally

**Backend only (uses legacy Jinja2 templates):**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend + Vue frontend (recommended):**

In one terminal:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
cd frontend
npm run dev
```

Open your browser at **http://localhost:5173** (Vite dev server). API requests are proxied to FastAPI at port 8000.

**Production build (Vue served by FastAPI):**

```bash
cd frontend
npm run build
cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The build outputs to `app/static/dist/`. FastAPI detects `app/static/dist/index.html` and serves the Vue SPA for all navigable routes.

---

## User Management

To change the username, password, or consumer number of any existing user:

```bash
python scripts/manage_user.py
```

Example session:

```
Existing users:
  1. alice (active) [admin] — Consumer#: (not set)
  2. bob (active) — Consumer#: 1234567890
  3. carol (active) — Consumer#: (not set)

Select user (1, 2, or 3): 2

Selected: bob
  1. Change username
  2. Change password
  3. Change both
  4. Set Consumer Number
  5. Cancel

Choice: 2
New password:
Confirm new password:

Changes saved successfully.
```

---

## Cloudflare R2 Setup

### 1. Create the Bucket

1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Go to **R2 Object Storage** → **Create bucket**
3. Enter a bucket name (e.g. `consumer-portal-uploads`)
4. Click **Create bucket**

### 2. Create API Credentials

1. Go to **R2 Object Storage** → **Manage R2 API tokens**
2. Click **Create API token**
3. Set permissions to **Object Read & Write**, scoped to your bucket
4. Copy the **Access Key ID**, **Secret Access Key**, and **Endpoint URL**

Update your `.env`:

```env
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=consumer-portal-uploads
```

### 3. Keep the Bucket Private

Ensure **Public access** is disabled in the bucket **Settings**. Do not enable R2.dev subdomain or a custom domain. Files are never served publicly.

### 4. Configure 10-Day Lifecycle Rule

1. Go to your bucket → **Settings** → **Object lifecycle rules** → **Add rule**
2. Configure:
   - **Rule name**: `delete-uploads-after-10-days`
   - **Prefix filter**: *(leave empty to apply to all objects)*
   - **Action**: Delete object
   - **Days after upload**: `10`
3. Click **Save**

---

## Cloudflare D1 Setup

### 1. Create the D1 Database

1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Go to **Workers & Pages** → **D1 SQL Database** → **Create database**
3. Enter a name (e.g. `consumer-portal-db`) and click **Create**
4. Copy the **Database ID** shown on the database page

### 2. Create an API Token with D1 Permission

1. Go to **My Profile** → **API Tokens** → **Create Token**
2. Use **Edit Cloudflare Workers** template, or create a custom token with:
   - **D1**: Edit
3. Copy the token

### 3. Apply the Schema

Run both `migrations/d1/0001_users.sql` and
`migrations/d1/0002_submissions.sql` via the Cloudflare Dashboard SQL console,
Wrangler, or the apply script (see [Apply D1 Schema](#4-apply-d1-schema)). If
the R2 bucket already contains form metadata, run
`python scripts/backfill_submissions.py` afterward.

### 4. Update `.env`

```env
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_D1_DATABASE_ID=your_d1_database_id
CLOUDFLARE_API_TOKEN=your_api_token
```

---

## Render Deployment

### 1. Create Render Web Service

1. Log in to [Render](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Runtime**: Python 3
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && cd frontend && npm install && npm run build && cd ..
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```

### 2. Set Environment Variables on Render

In your Render web service → **Environment**, add all variables from the [Environment Variables Reference](#environment-variables-reference) table, with `APP_ENV=production`.

### 3. Seed Users on Render

In the Render **Shell** tab:

```bash
python scripts/seed_users.py
```

> To change a user later, run `python scripts/manage_user.py` in the Render Shell.

---

## Vercel Deployment

The project is deployed as a **single Vercel project**: Vercel runs the FastAPI backend via a Python serverless function and serves the Vue SPA build output as static files.

### 1. Build the Vue Frontend Locally (or in CI)

```bash
cd frontend
npm install
npm run build
cd ..
```

This outputs the Vue SPA to `app/static/dist/`. Commit this directory (or let Vercel build it — see step 3).

### 2. Create `vercel.json`

Create `vercel.json` in the project root:

```json
{
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/app/main.py"
    },
    {
      "src": "/api/(.*)",
      "dest": "/app/main.py"
    },
    {
      "src": "/(.*)",
      "dest": "/app/main.py"
    }
  ]
}
```

All requests are routed to FastAPI. FastAPI serves the Vue SPA for navigable routes and the static files from `app/static/`.

### 3. Create `api/index.py` (Vercel entry point)

Vercel's Python runtime requires the ASGI app to be importable from a file in the `api/` directory. Create `api/index.py`:

```python
from app.main import app
```

Update `vercel.json` to point to this entry:

```json
{
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/api/index.py" }
  ]
}
```

### 4. Add a Build Command for the Frontend

In `vercel.json`, add an `installCommand` and `buildCommand` so Vercel builds the Vue app automatically:

```json
{
  "installCommand": "pip install -r requirements.txt && cd frontend && npm install",
  "buildCommand": "cd frontend && npm run build",
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/api/index.py" }
  ]
}
```

### 5. Deploy to Vercel

**Option A — Vercel CLI:**

```bash
npm install -g vercel
vercel login
vercel --prod
```

**Option B — Vercel Dashboard:**

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repository
3. Set **Framework Preset** to **Other**
4. Set **Root Directory** to `.` (project root)
5. Click **Deploy**

### 6. Set Environment Variables on Vercel

In your Vercel project → **Settings** → **Environment Variables**, add all variables from the [Environment Variables Reference](#environment-variables-reference) table, with `APP_ENV=production`.

### 7. Seed Users

After the first deployment, use the Vercel CLI to run the seed script:

```bash
vercel env pull .env.production.local
python scripts/seed_users.py
```

Or run it locally with production environment variables pointing to your live D1 database.

### Notes on Vercel Limitations

- Vercel serverless functions have a **10-second timeout** on the Hobby plan (60 seconds on Pro). Large file uploads may time out — consider upgrading to Pro or using Render for heavy workloads.
- Vercel functions are **stateless** — server-side sessions stored in memory will not persist across invocations. The current session implementation uses signed cookies (via `itsdangerous`), which works correctly on Vercel.
- The `/health` endpoint works normally on Vercel.

---

## Testing

Tests use mocked D1 responses — no live Cloudflare credentials are needed.

Run all tests:

```bash
pytest tests/ -v
```

---

## Environment Variables Reference

| Variable                    | Required | Description                                              |
|-----------------------------|----------|----------------------------------------------------------|
| `APP_ENV`                   | Yes      | `development` or `production`                            |
| `SECRET_KEY`                | Yes      | Long random string for CSRF and session signing          |
| `SESSION_MAX_AGE`           | No       | Session lifetime in seconds (default: `3600`)            |
| `R2_ENDPOINT_URL`           | Yes      | Cloudflare R2 endpoint URL                               |
| `R2_ACCESS_KEY_ID`          | Yes      | R2 API access key ID                                     |
| `R2_SECRET_ACCESS_KEY`      | Yes      | R2 API secret access key                                 |
| `R2_BUCKET_NAME`            | Yes      | R2 bucket name                                           |
| `CLOUDFLARE_ACCOUNT_ID`     | Yes      | Cloudflare account ID                                    |
| `CLOUDFLARE_D1_DATABASE_ID` | Yes      | D1 database ID                                           |
| `CLOUDFLARE_API_TOKEN`      | Yes      | Cloudflare API token with D1 Edit permission             |

> In `production` mode (`APP_ENV=production`), session cookies are set with `Secure=True`, requiring HTTPS.

---

## Troubleshooting

**Login always fails**
- Make sure you ran `python scripts/seed_users.py` and it completed successfully
- Verify D1 credentials (`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_D1_DATABASE_ID`, `CLOUDFLARE_API_TOKEN`) are correct

**D1 request timed out**
- Check your `CLOUDFLARE_API_TOKEN` has D1 Edit permission
- Verify `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_D1_DATABASE_ID` are correct

**R2 upload fails**
- Check `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` in `.env`
- Ensure the R2 API token has **Object Read & Write** permission on the correct bucket

**Vue SPA not loading (shows Jinja template instead)**
- Run `cd frontend && npm run build` — FastAPI only serves the SPA when `app/static/dist/index.html` exists

**`Secure cookie` warning in development**
- Set `APP_ENV=development` in `.env` — secure cookies are only enforced in production

**`seed_users.py` says "3 users already exist"**
- Use `python scripts/manage_user.py` to change existing users instead

**Vercel deployment: module not found**
- Ensure `api/index.py` exists and `vercel.json` points to it
- Check that `requirements.txt` is in the project root

---

## Security Notes

- Passwords are hashed with **Argon2id** — never stored in plaintext
- Sessions are signed with `itsdangerous` using `SECRET_KEY`; only a signed session ID is in the cookie
- Cookies are **HTTPOnly**, **SameSite=Lax**, and **Secure** in production
- **CSRF tokens** are required on all POST requests; Vue reads the token from a non-HttpOnly cookie and sends it as `X-CSRF-Token`
- File type is validated using **magic bytes**, not just the file extension or browser MIME type
- R2 object keys are structured and sanitised — original filenames are never used directly as keys
- The R2 bucket is **private** — no public URLs are ever generated or exposed
- All validation happens **server-side** — frontend attributes are UX helpers only
- Error messages are **generic** — no stack traces, internal paths, or D1 errors are shown to users
- There is **no public signup page** and **no password reset page**
- Admin routes require `is_admin=1` in D1 — regular users cannot access `/admin` or `/api/admin/*`
