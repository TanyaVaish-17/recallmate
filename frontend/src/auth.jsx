import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, clearToken, getToken, setToken } from './api';
const Ctx = createContext(null);
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(!!getToken());
    const refresh = useCallback(async () => {
        if (!getToken()) {
            setUser(null);
            setLoading(false);
            return;
        }
        try {
            setUser(await api.me());
        }
        catch {
            clearToken();
            setUser(null);
        }
        setLoading(false);
    }, []);
    useEffect(() => {
        void refresh();
        const onLogout = () => setUser(null);
        window.addEventListener('recallmate-logout', onLogout);
        return () => window.removeEventListener('recallmate-logout', onLogout);
    }, [refresh]);
    const login = async (email, password) => {
        const t = await api.login(email, password);
        setToken(t.access_token);
        setUser(await api.me());
    };
    const register = async (email, password, name) => {
        await api.register(email, password, name);
        await login(email, password);
    };
    const logout = () => { clearToken(); setUser(null); };
    return <Ctx.Provider value={{ user, loading, login, register, logout, refresh }}>{children}</Ctx.Provider>;
}
export function useAuth() {
    const v = useContext(Ctx);
    if (!v)
        throw new Error('useAuth must be used inside AuthProvider');
    return v;
}
