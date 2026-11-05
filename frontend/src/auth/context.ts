// frontend/src/auth/context.ts
import { createContext, useContext } from 'react'
import type { User } from '../api/types'

export type Status = 'loading' | 'anonymous' | 'authenticated'

export interface AuthValue {
  status: Status
  user: User | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setUser: (user: User) => void
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth doit être utilisé dans AuthProvider')
  return value
}
