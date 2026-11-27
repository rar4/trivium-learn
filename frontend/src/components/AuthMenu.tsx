"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { LogIn, LogOut, UserRound, X } from "lucide-react";
import {
  AUTH_CHANGED_EVENT, AuthUser, getAuthMe, getToken, loginUser,
  logoutUser, registerUser, setAuthToken,
} from "@/lib/api";

/** Notify the gamification panel that the active learner changed. */
function notifyLearnerChanged() {
  window.dispatchEvent(new CustomEvent("trivium:profile-updated"));
}

/**
 * Account switcher. Without a token the app keeps using the legacy local
 * learner, so existing installs and the single-user flow stay unchanged.
 */
export default function AuthMenu() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [en, setEn] = useState(false);

  const refresh = useCallback(() => {
    if (!getToken()) { setUser(null); return; }
    getAuthMe().then(setUser).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    setEn(typeof window !== "undefined" && localStorage.getItem("trivium_ui_lang") === "en-US");
    refresh();
    window.addEventListener(AUTH_CHANGED_EVENT, refresh);
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, refresh);
  }, [refresh]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const data = mode === "login"
        ? await loginUser(username.trim(), password)
        : await registerUser(username.trim(), password, displayName.trim() || undefined);
      setAuthToken(data.token);
      setUser(data.user);
      setOpen(false); setPassword(""); setDisplayName("");
      notifyLearnerChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : (en ? "Sign-in failed" : "Falha ao entrar"));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    await logoutUser();
    setUser(null); setOpen(false); setUsername(""); setPassword("");
    notifyLearnerChanged();
    setBusy(false);
  }

  const inputClass = "w-full bg-[#0e0e10] border border-[#333338] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#ffe500]";

  return (
    <div className="fixed bottom-3 left-3 z-[90]" data-testid="auth-menu">
      {open && (
        <div className="absolute bottom-11 left-0 w-[19rem] max-w-[calc(100vw-1.5rem)] bg-[#141416] border border-[#333338] rounded-2xl shadow-2xl shadow-black/60 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-black text-[#ffe500]">
              {en ? (user ? "Your account" : "Sign in") : (user ? "Sua conta" : "Entrar")}
            </span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="text-neutral-500 hover:text-white cursor-pointer">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {user ? (
            <div className="space-y-3">
              <div className="text-sm text-white font-bold">{user.display_name}</div>
              <div className="text-[11px] text-neutral-500">@{user.username}</div>
              <Link
                href="/mastery"
                onClick={() => setOpen(false)}
                className="block text-center w-full bg-[#ffe500] hover:bg-[#fff000] text-black font-extrabold text-xs px-3 py-2 rounded-xl transition-all"
              >
                {en ? "Mastery dashboard" : "Painel de domínio"}
              </Link>
              <button
                type="button" onClick={signOut} disabled={busy}
                className="w-full flex items-center justify-center gap-2 bg-[#1f1f23] hover:bg-[#27272a] text-neutral-300 font-bold text-xs px-3 py-2 rounded-xl cursor-pointer disabled:opacity-50"
              >
                <LogOut className="w-3.5 h-3.5" /> {en ? "Sign out" : "Sair"}
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-2.5">
              <div className="flex gap-1 rounded-lg bg-[#0e0e10] p-1">
                {(["login", "register"] as const).map((m) => (
                  <button
                    key={m} type="button" onClick={() => { setMode(m); setError(null); }}
                    className={`flex-1 text-[11px] font-bold py-1.5 rounded-md cursor-pointer ${mode === m ? "bg-[#ffe500] text-black" : "text-neutral-400 hover:text-white"}`}
                  >
                    {m === "login" ? (en ? "Sign in" : "Entrar") : (en ? "Create account" : "Criar conta")}
                  </button>
                ))}
              </div>
              <input className={inputClass} placeholder={en ? "Username" : "Usuário"} value={username}
                onChange={(e) => setUsername(e.target.value)} autoComplete="username" required minLength={3} />
              {mode === "register" && (
                <input className={inputClass} placeholder={en ? "Display name (optional)" : "Nome (opcional)"}
                  value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              )}
              <input className={inputClass} type="password" placeholder={en ? "Password" : "Senha"}
                value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={8} />
              {error && <p className="text-[11px] text-red-400 break-words">{error}</p>}
              <button type="submit" disabled={busy}
                className="w-full flex items-center justify-center gap-2 bg-[#ffe500] hover:bg-[#fff000] text-black font-extrabold text-xs px-3 py-2 rounded-xl cursor-pointer disabled:opacity-50">
                <LogIn className="w-3.5 h-3.5" />
                {busy ? (en ? "Please wait..." : "Aguarde...") : (mode === "login" ? (en ? "Sign in" : "Entrar") : (en ? "Create account" : "Criar conta"))}
              </button>
              <p className="text-[10px] text-neutral-500">
                {en ? "No account? Your progress stays on this device." : "Sem conta? Seu progresso fica neste dispositivo."}
              </p>
            </form>
          )}
        </div>
      )}

      <button
        type="button" onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 bg-[#141416] hover:bg-[#1f1f23] border border-[#333338] hover:border-[#ffe500]/50 text-neutral-200 px-2.5 py-1.5 rounded-full text-[11px] font-bold shadow-lg shadow-black/40 cursor-pointer"
        aria-label={en ? "Account" : "Conta"}
      >
        <UserRound className="w-3.5 h-3.5 text-[#ffe500]" />
        <span className="max-w-[9rem] truncate">{user ? user.display_name : (en ? "Sign in" : "Entrar")}</span>
      </button>
    </div>
  );
}
