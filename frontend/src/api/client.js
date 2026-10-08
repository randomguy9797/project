/**
 * Centralised API client.
 *
 * CSRF strategy: the FastAPI backend sets a non-HttpOnly `csrf_token` cookie
 * (see app/csrf.py). We read it here and send it as the X-CSRF-Token header
 * on every state-changing request. This matches what the backend validates.
 *
 * All requests use credentials: 'include' so the session_id cookie is sent.
 */

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

/**
 * Ensure a CSRF cookie exists. Call once on app mount.
 * The /api/csrf endpoint sets the cookie and returns the token value.
 */
export async function initCsrf() {
  const res = await fetch('/api/csrf', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to initialise CSRF token.')
}

/**
 * GET /api/<path>
 * Returns parsed JSON or throws { error: string }.
 */
export async function apiGet(path) {
  const res = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'X-CSRF-Token': getCsrfToken() },
  })
  const data = await res.json()
  if (!res.ok) throw data
  return data
}

/**
 * POST /api/<path> with FormData body.
 * Returns parsed JSON or throws { error: string }.
 */
export async function apiPost(path, formData) {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': getCsrfToken() },
    body: formData,
  })

  // Downloads return a binary stream, not JSON
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const data = await res.json()
    if (!res.ok) throw data
    return data
  }

  // Binary response (file download)
  if (!res.ok) throw { error: 'Download failed.' }
  return res
}
