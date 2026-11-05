// frontend/src/auth/AuthContext.tsx
// Session rétablie au chargement par le cookie de renouvellement, sans redemander le mot de passe
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { API, api, refreshSession, setAccessToken } from '../api/client'
import type { TokenOut, User } from '../api/types'
import { AuthContext, type Status } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading')
  const [user, setUser] = useState<User | null>(null)

  const loadMe = useCallback(async () => {
    const me = await api<User>('/auth/me')
    setUser(me)
    setStatus('authenticated')
  }, [])

  useEffect(() => {
    refreshSession()
      .then((ok) => (ok ? loadMe() : setStatus('anonymous')))
      .catch(() => setStatus('anonymous'))
  }, [loadMe])

  const login = useCallback(
    async (email: string, password: string) => {
      const form = new URLSearchParams({ username: email, password })
      const token = await api<TokenOut>('/auth/token', { method: 'POST', form, retry: false })
      setAccessToken(token.access_token)
      await loadMe()
    },
    [loadMe],
  )

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      await api<User>('/auth/register', { method: 'POST', json: { name, email, password } })
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(async () => {
    await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'same-origin' }).catch(() => undefined)
    setAccessToken(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo(() => ({ status, user, login, register, logout, setUser }),
    [status, user, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
