import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

interface AuthState {
  isAuthenticated: boolean
  token: string | null
  officer: { id: string; name: string; post: string } | null
  login: (officerId: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(() => {
    const saved = localStorage.getItem("ibvap-session")
    return saved ? JSON.parse(saved) : { isAuthenticated: false, token: null, officer: null }
  })

  const login = async (officerId: string, password: string) => {
    // TODO: Wire to real backend auth endpoint when available
    // For now, accept any credentials
    const session = {
      isAuthenticated: true,
      token: "mock-token",
      officer: { id: officerId, name: "Officer " + officerId, post: "Field Operator" },
    }
    setState(session)
    localStorage.setItem("ibvap-session", JSON.stringify(session))
  }

  const logout = () => {
    setState({ isAuthenticated: false, token: null, officer: null })
    localStorage.removeItem("ibvap-session")
  }

  return <AuthContext.Provider value={{ ...state, login, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)!
