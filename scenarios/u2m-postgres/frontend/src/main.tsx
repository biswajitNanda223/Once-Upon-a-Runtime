import { StrictMode, createContext, useContext, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type User = { id: string; username: string | null; email: string | null };
type AuthState = { user: User | null; loading: boolean; error: string | null };
const AuthContext = createContext<AuthState>({ user: null, loading: true, error: null });

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/me", { credentials: "same-origin", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status === 401 ? "Sign in is required." : "Profile service is unavailable.");
        return response.json() as Promise<User>;
      })
      .then((user) => setState({ user, loading: false, error: null }))
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") setState({ user: null, loading: false, error: (error as Error).message });
      });
    return () => controller.abort();
  }, []);
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

function App() {
  const { user, loading, error } = useContext(AuthContext);
  if (loading) return <main><p>Loading your Databricks identity…</p></main>;
  if (error) return <main><h1>Authentication problem</h1><p role="alert">{error}</p></main>;
  const displayName = user?.username || user?.email || "Databricks user";
  return <main><p className="eyebrow">ONCE UPON A RUNTIME</p><h1>Welcome, {displayName}</h1><p>Your profile was synchronized through a trusted App-to-App channel.</p><dl><dt>Stable user ID</dt><dd>{user?.id}</dd><dt>Email</dt><dd>{user?.email || "Not provided"}</dd></dl></main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><AuthProvider><App /></AuthProvider></StrictMode>);
