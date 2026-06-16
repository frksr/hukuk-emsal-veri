"use client";
import { createContext, useContext, type ReactNode } from "react";

export type AuthUser = { name: string | null; email: string | null; role: string | null } | null;

const AuthContext = createContext<AuthUser>(null);

/**
 * Sunucuda `auth()` ile çözülen kullanıcıyı ilk render'a taşır. Böylece Header
 * ve usePlan, giriş durumunu client fetch'i BEKLEMEDEN doğru gösterir —
 * "çıkış-yapmış → giriş-yapmış" titremesi olmaz.
 */
export function AuthProvider({
  initialUser,
  children,
}: {
  initialUser: AuthUser;
  children: ReactNode;
}) {
  return <AuthContext.Provider value={initialUser}>{children}</AuthContext.Provider>;
}

export function useAuthUser(): AuthUser {
  return useContext(AuthContext);
}
