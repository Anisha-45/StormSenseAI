import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, errorMessage, getToken, setToken } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [guest, setGuest] = useState(() => {
    try { return sessionStorage.getItem('stormsense_guest') === '1' } catch { return false }
  })

  useEffect(() => {
    if (!getToken()) { setReady(true); return }
    api.get('/auth/profile')
      .then((r) => setUser(r.data))
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [])

  const login = useCallback(async (email, password) => {
    try {
      const r = await api.post('/auth/login', { email, password })
      setToken(r.data.access_token)
      setUser(r.data.user)
      return null
    } catch (e) { return errorMessage(e) }
  }, [])

  const register = useCallback(async (email, name, password, role) => {
    try {
      await api.post('/auth/register', { email, name, password, role })
      return await login(email, password)
    } catch (e) { return errorMessage(e) }
  }, [login])

  const continueAsGuest = useCallback(() => {
    try { sessionStorage.setItem('stormsense_guest', '1') } catch { /* storage unavailable: guest lasts until reload */ }
    setGuest(true)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    try { sessionStorage.removeItem('stormsense_guest') } catch { /* ignore */ }
    setGuest(false)
  }, [])

  const value = useMemo(() => ({ user, ready, guest, login, register, logout, continueAsGuest }), [user, ready, guest, login, register, logout, continueAsGuest])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
