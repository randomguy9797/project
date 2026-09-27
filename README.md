# Consumer Portal

A lightweight, production-ready web application for submitting consumer details and file uploads. Built with FastAPI, PostgreSQL, and Cloudflare R2 for file storage.

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
   - [PostgreSQL Setup](#4-postgresql-setup)
   - [Run Alembic Migrations](#5-run-alembic-migrations)
   - [Seed Initial Users](#6-seed-initial-users)
   - [Run Locally](#7-run-locally)
8. [User Management](#user-management)
9. [Cloudflare R2 Setup](#cloudflare-r2-setup)
   - [Create the Bucket](#1-create-the-bucket)
   - [Create API Credentials](#2-create-api-credentials)
   - [Configure Bucket as Private](#3-configure-bucket-as-private)
   - [Configure 10-Day Lifecycle Rule](#4-configure-10-day-lifecycle-rule)
10. [Render Deployment](#render-deployment)
    - [Create Render PostgreSQL](#1-create-render-postgresql)
    - [Create Render Web Service](#2-create-render-web-service)
    - [Set Environment Variables on Render](#3-set-environment-variables-on-render)
    - [Run Migrations on Render](#4-run-migrations-on-render)
    - [Seed Users on Render](#5-seed-users-on-render)
11. [Testing](#testing)
12. [Environment Variables Reference](#environment-variables-reference)
13. [Future Migrations](#future-migrations)
14. [Troubleshooting](#troubleshooting)
15. [Security Notes](#security-notes)

---

## Project Overview

Consumer Portal is a small personal-use application that allows exactly 3 authenticated users to submit consumer details along with a PDF or JPG file. Uploaded files are stored privately in Cloudflare R2 and automatically deleted after 10 days. Submission metadata is stored permanently in PostgreSQL.

Expected traffic: fewer than ~500 submissions per month.

---

## Features

- Secure login with Argon2id password hashing
- Server-side session authentication (1-hour expiry, HTTPOnly cookies)
- CSRF protection on all state-changing requests
- Submission form with server-side validation
- Indian 10-digit mobile number validation
- File upload (PDF, JPG, JPEG) with magic-byte type detection
- 10 MB file size limit
- Private Cloudflare R2 file storage with UUID-based object keys
- Automatic R2 file deletion after 10 days via lifecycle rules
- PostgreSQL submission metadata storage
- Partial failure handling (R2 orphan cleanup on DB failure)
- Mobile-first responsive UI with plain HTML5 + CSS3
- No JavaScript required
- CLI tools for user seeding and management
- Friendly 403 / 404 / 500 error pages

---

## Architecture

```
Browser
   |
   v
FastAPI (Render)
   |
   +---- PostgreSQL (Render)
   |        |
   |        +---- users
   |        +---- submissions
   |
   +---- Cloudflare R2
            |
            +---- uploaded documents (uploads/YYYY/MM/<uuid>.ext)
            |
            +---- automatic deletion after 10 days
```

Authentication flow:

```
Browser → Login page → FastAPI → PostgreSQL user verification
       → Secure HTTPOnly session cookie → Submission form
```

---

## Technology Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| Language     | Python 3.12+                      |
| Web framework| FastAPI                           |
| Templates    | Jinja2 (server-rendered HTML)     |
| Frontend     | Plain HTML5 + CSS3 (no JS)        |
| Database     | PostgreSQL                        |
| ORM          | SQLAlchemy 2.x                    |
| Migrations   | Alembic                           |
| File storage | Cloudflare R2 (S3-compatible)     |
| R2 client    | boto3                             |
| Password hash| Argon2id (argon2-cffi)            |
| Server       | Uvicorn                           |
| Hosting      | Render                            |

---

## Requirements

- Python 3.12 or higher
- PostgreSQL 14 or higher
- A Cloudflare account with R2 enabled
- A Render account (for deployment)

---

## Project Structure

```
project/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routers, error handlers
│   ├── config.py        # Settings loaded from environment variables
│   ├── database.py      # SQLAlchemy engine and session
│   ├── models.py        # User and Submission ORM models
│   ├── schemas.py       # Pydantic schemas
│   ├── auth.py          # Argon2id password hashing/verification
│   ├── sessions.py      # Server-side session management
│   ├── csrf.py          # CSRF token generation and validation
│   ├── storage.py       # Cloudflare R2 upload/delete via boto3
│   ├── validators.py    # Mobile number and file type validation
│   │
│   ├── routes/
│   │   ├── auth.py          # GET/POST /login, POST /logout
│   │   └── submissions.py   # GET/POST /form
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── form.html
│   │   ├── success.html
│   │   └── errors/
│   │       ├── 403.html
│   │       ├── 404.html
│   │       └── 500.html
│   │
│   └── static/
│       └── css/
│           └── style.css
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_validators.py
│
├── scripts/
│   ├── seed_users.py     # Create the initial 3 users
│   └── manage_user.py    # Change username or password
│
├── alembic.ini
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
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
pip install -r requirements.txt
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

DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/consumer_portal

SESSION_MAX_AGE=3600

R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=your_bucket_name
```

> To generate a strong SECRET_KEY:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 4. PostgreSQL Setup

Make sure PostgreSQL is running, then create the database:

```bash
psql -U postgres -c "CREATE DATABASE consumer_portal;"
```

Or using pgAdmin / any PostgreSQL client — just create a database and update `DATABASE_URL` in `.env`.

### 5. Run Alembic Migrations

```bash
alembic upgrade head
```

This creates the `users` and `submissions` tables with all constraints and indexes.

### 6. Seed Initial Users

```bash
python scripts/seed_users.py
```

You will be prompted to enter a username and password for each of the 3 users. Passwords are not echoed to the terminal.

Example session:

```
Creating 3 users.

Username for user 1: alice
Password for user 1:
Confirm password for user 1:
User 1 prepared.

Username for user 2: bob
Password for user 2:
Confirm password for user 2:
User 2 prepared.

Username for user 3: carol
Password for user 3:
Confirm password for user 3:
User 3 prepared.

All 3 users created successfully.
```

> The script refuses to create a 4th user if 3 already exist.

### 7. Run Locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open your browser at: **http://localhost:8000**

The root URL redirects to `/login` automatically.

---

## User Management

To change the username or password of any existing user:

```bash
python scripts/manage_user.py
```

Example session:

```
Existing users:
  1. alice (active)
  2. bob (active)
  3. carol (active)

Select user (1, 2, or 3): 2

Selected: bob
  1. Change username
  2. Change password
  3. Change both
  4. Cancel

Choice: 2
New password:
Confirm new password:
Password updated.

Changes saved successfully.
```

Rules enforced by the script:
- Cannot create a 4th user
- New usernames must be unique
- Passwords are hashed with Argon2id before storing
- Existing passwords are never displayed

---

## Cloudflare R2 Setup

### 1. Create the Bucket

1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Go to **R2 Object Storage** in the left sidebar
3. Click **Create bucket**
4. Enter a bucket name (e.g. `consumer-portal-uploads`)
5. Choose a region (or leave as automatic)
6. Click **Create bucket**

### 2. Create API Credentials

1. In the Cloudflare Dashboard, go to **R2 Object Storage**
2. Click **Manage R2 API tokens** (top right)
3. Click **Create API token**
4. Give it a name (e.g. `consumer-portal-token`)
5. Set permissions to **Object Read & Write**
6. Under **Specify bucket**, select your bucket
7. Click **Create API token**
8. Copy the **Access Key ID** and **Secret Access Key** — you will not see the secret again
9. Also copy the **Endpoint URL** shown on that page (format: `https://<account_id>.r2.cloudflarestorage.com`)

Update your `.env`:

```env
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=consumer-portal-uploads
```

### 3. Configure Bucket as Private

By default, R2 buckets are private (no public access). Confirm this:

1. Go to your bucket in the Cloudflare Dashboard
2. Click **Settings**
3. Under **Public access**, ensure it is **not enabled**
4. Do NOT connect a custom domain or enable R2.dev subdomain

Files are never served publicly. The application only uploads to R2 — it never generates public URLs.

### 4. Configure 10-Day Lifecycle Rule

1. Go to your bucket in the Cloudflare Dashboard
2. Click **Settings**
3. Scroll to **Object lifecycle rules**
4. Click **Add rule**
5. Configure:
   - **Rule name**: `delete-uploads-after-10-days`
   - **Prefix filter**: `uploads/`
   - **Action**: Delete object
   - **Days after upload**: `10`
6. Click **Save**

This automatically deletes all objects under `uploads/` after 10 days. No application-level scheduled deletion is needed.

> The submission metadata in PostgreSQL is kept permanently even after the file is deleted from R2.

---

## Render Deployment

### 1. Create Render PostgreSQL

1. Log in to [Render](https://render.com)
2. Click **New** → **PostgreSQL**
3. Fill in:
   - **Name**: `consumer-portal-db`
   - **Region**: choose closest to your users
   - **Plan**: Free (or Starter for production)
4. Click **Create Database**
5. Once created, copy the **External Database URL** — it looks like:
   ```
   postgresql://user:password@host/dbname
   ```
6. Change the scheme to `postgresql+psycopg://` for SQLAlchemy:
   ```
   postgresql+psycopg://user:password@host/dbname
   ```

### 2. Create Render Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `consumer-portal`
   - **Region**: same as your database
   - **Branch**: `main`
   - **Runtime**: Python 3
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
4. Click **Create Web Service**

### 3. Set Environment Variables on Render

In your Render web service, go to **Environment** and add:

| Key                  | Value                                              |
|----------------------|----------------------------------------------------|
| `APP_ENV`            | `production`                                       |
| `SECRET_KEY`         | a long random string (use `secrets.token_hex(32)`) |
| `DATABASE_URL`       | your Render PostgreSQL URL (with `+psycopg`)       |
| `SESSION_MAX_AGE`    | `3600`                                             |
| `R2_ENDPOINT_URL`    | your R2 endpoint URL                               |
| `R2_ACCESS_KEY_ID`   | your R2 access key                                 |
| `R2_SECRET_ACCESS_KEY` | your R2 secret key                               |
| `R2_BUCKET_NAME`     | your R2 bucket name                                |

### 4. Run Migrations on Render

After the first deploy, open the Render **Shell** tab for your web service and run:

```bash
alembic upgrade head
```

Or add it to the build command so it runs automatically on every deploy:

```bash
pip install -r requirements.txt && alembic upgrade head
```

### 5. Seed Users on Render

In the Render **Shell** tab:

```bash
python scripts/seed_users.py
```

Follow the prompts to create the 3 users.

> To change a user later, run `python scripts/manage_user.py` in the Render Shell.

---

## Testing

Tests use SQLite in-memory so no PostgreSQL setup is needed.

Run all tests:

```bash
pytest tests/ -v
```

Run a specific test file:

```bash
pytest tests/test_auth.py -v
pytest tests/test_validators.py -v
```

Test coverage includes:
- Valid and invalid login
- CSRF validation
- Unauthenticated access to `/form`
- Session expiry
- Logout
- Mobile number validation (valid and invalid)
- File type detection (PDF, JPG, unknown)

---

## Environment Variables Reference

| Variable              | Required | Description                                              |
|-----------------------|----------|----------------------------------------------------------|
| `APP_ENV`             | Yes      | `development` or `production`                            |
| `SECRET_KEY`          | Yes      | Long random string for CSRF signing                      |
| `DATABASE_URL`        | Yes      | PostgreSQL connection string (`postgresql+psycopg://...`)|
| `SESSION_MAX_AGE`     | No       | Session lifetime in seconds (default: `3600`)            |
| `R2_ENDPOINT_URL`     | Yes      | Cloudflare R2 endpoint URL                               |
| `R2_ACCESS_KEY_ID`    | Yes      | R2 API access key ID                                     |
| `R2_SECRET_ACCESS_KEY`| Yes      | R2 API secret access key                                 |
| `R2_BUCKET_NAME`      | Yes      | R2 bucket name                                           |

> In `production` mode (`APP_ENV=production`), session cookies are set with `Secure=True`, requiring HTTPS.

---

## Future Migrations

To create a new migration after changing `app/models.py`:

```bash
alembic revision --autogenerate -m "describe your change"
```

Review the generated file in `alembic/versions/`, then apply it:

```bash
alembic upgrade head
```

To roll back one migration:

```bash
alembic downgrade -1
```

---

## Troubleshooting

**`alembic upgrade head` fails with connection error**
- Check that PostgreSQL is running
- Verify `DATABASE_URL` in `.env` is correct
- Ensure the database exists: `psql -U postgres -c "CREATE DATABASE consumer_portal;"`

**`ModuleNotFoundError` when running scripts**
- Make sure your virtual environment is activated
- Run `pip install -r requirements.txt`

**Login always fails**
- Make sure you ran `python scripts/seed_users.py` and it completed successfully
- Verify the user exists: `psql -U postgres -d consumer_portal -c "SELECT username FROM users;"`

**R2 upload fails**
- Check `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` in `.env`
- Ensure the R2 API token has **Object Read & Write** permission on the correct bucket
- The app will show "We couldn't submit your form. Please try again." and log the error server-side

**`Secure cookie` warning in development**
- Set `APP_ENV=development` in `.env` — secure cookies are only enforced in production

**Port already in use**
- Change the port: `uvicorn app.main:app --reload --port 8001`

**`seed_users.py` says "3 users already exist"**
- Use `python scripts/manage_user.py` to change existing users instead

---

## Security Notes

- Passwords are hashed with **Argon2id** — never stored in plaintext
- Sessions are stored server-side; only a random session ID is in the cookie
- Cookies are **HTTPOnly**, **SameSite=Lax**, and **Secure** in production
- **CSRF tokens** are required on all POST requests (login, form submit, logout)
- File type is validated using **magic bytes**, not just the file extension or browser MIME type
- R2 object keys are **UUID-based** — original filenames are never used as keys
- The R2 bucket is **private** — no public URLs are ever generated or exposed
- All validation happens **server-side** — HTML5 attributes are UX helpers only
- Error messages are **generic** — no stack traces, SQL errors, or internal paths are shown to users
- There is **no public signup page** and **no password reset page**
- The application enforces **exactly 3 users** at all times
