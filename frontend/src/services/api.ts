let _getToken: (() => string | null) | null = null
let _getGoogleToken: (() => string | null) | null = null

export function setTokenGetter(getter: () => string | null) {
  _getToken = getter
}

export function setGoogleTokenGetter(getter: () => string | null) {
  _getGoogleToken = getter
}

const API_BASE = '/api'

async function waitForToken(maxMs = 3000): Promise<string | null> {
  // Poll up to maxMs for the token getter to return a non-null value.
  // This fixes races where a component's initial useEffect fires before
  // Firebase's onAuthStateChanged has set the token.
  const start = Date.now()
  while (Date.now() - start < maxMs) {
    const t = _getToken?.()
    if (t) return t
    await new Promise((r) => setTimeout(r, 50))
  }
  return _getToken?.() ?? null
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await waitForToken()
  // Always read fresh from localStorage to avoid stale closures
  const googleToken = _getGoogleToken?.() || localStorage.getItem('masteko_google_access_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (googleToken) {
    // Custom header intentionally not prefixed X-Google-* — Firebase Hosting's
    // Fastly edge strips X-Google-* headers before they reach Cloud Run.
    headers['X-MFM-Drive-Token'] = googleToken
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
