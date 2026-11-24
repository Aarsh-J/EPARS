import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  getCurrentUser as fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
} from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const clearUser = () => {
      if (active) {
        setUser(null);
        setLoading(false);
      }
    };

    window.addEventListener("epars:unauthorized", clearUser);
    fetchCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((error) => {
        if (active && error.status !== 401) {
          console.error("Unable to check the current session:", error);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      window.removeEventListener("epars:unauthorized", clearUser);
    };
  }, []);

  const login = useCallback(async (username, password) => {
    const result = await loginRequest(username, password);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}
