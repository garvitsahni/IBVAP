import { createContext, useContext, useEffect, useState } from "react";

const AuthContext = createContext(null);
const STORAGE_KEY = "sih26187-officer-session";

// Simulates network latency so loading/error states can be built now.
// Swap the body of login() for a real apiClient.post('/auth/login', ...)
// call once the backend exists -- the rest of the app only depends on
// the { officer, token } shape returned here.
function fakeRequest(payload) {
  return new Promise((resolve) => setTimeout(() => resolve(payload), 500));
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) setSession(JSON.parse(stored));
    setLoading(false);
  }, []);

  function persist(nextSession) {
    setSession(nextSession);
    if (nextSession) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }

  async function login(officerId, _password) {
    const result = await fakeRequest({
      token: "mock-token",
      officer: {
        id: officerId,
        name: officerId.toUpperCase(),
        post: "Sector 7 Control Room",
      },
    });
    persist(result);
    return result;
  }

  function logout() {
    persist(null);
  }

  const value = {
    officer: session?.officer ?? null,
    token: session?.token ?? null,
    isAuthenticated: Boolean(session?.token),
    loading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside an AuthProvider");
  return ctx;
}
