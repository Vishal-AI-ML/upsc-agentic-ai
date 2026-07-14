import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import {
  api,
  clearTokens,
  getToken,
  type CurrentUser,
  type RegisterResult,
} from "./api"

interface AuthState {
  user: CurrentUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<RegisterResult>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function boot() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const me = await api.me()
        if (active) setUser(me)
      } catch {
        clearTokens()
      } finally {
        if (active) setLoading(false)
      }
    }
    void boot()
    return () => {
      active = false
    }
  }, [])

  async function login(email: string, password: string) {
    await api.login(email, password)
    setUser(await api.me())
  }

  async function register(email: string, password: string, name: string) {
    const res = await api.register(email, password, name)
    if (res.access_token) setUser(await api.me())
    return res
  }

  async function logout() {
    await api.logout()
    setUser(null)
  }

  async function refreshUser() {
    if (!getToken()) return
    setUser(await api.me())
  }

  const value: AuthState = { user, loading, login, register, logout, refreshUser }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
