import axios from 'axios'

const TOKEN_KEY = 'stormsense_token'

// localStorage can throw (private windows, blocked storage), so every access is guarded.
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token) {
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
}

export const api = axios.create({ baseURL: '/api/v1', timeout: 120000 })

api.interceptors.request.use((cfg) => {
  const t = getToken()
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

// Turn any failure into a readable string (FastAPI sends {detail: string | [{msg, loc}]}).
export function errorMessage(err) {
  if (err?.code === 'ECONNABORTED') return 'The request timed out. Try a smaller sample size.'
  if (!err?.response) return 'Cannot reach the StormSense API. Is the backend running on port 8000?'
  const d = err.response.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join('; ')
  return `Request failed (${err.response.status})`
}

// Remove empty values so optional filters are not sent as "undefined" or "".
export function clean(params = {}) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined))
}
