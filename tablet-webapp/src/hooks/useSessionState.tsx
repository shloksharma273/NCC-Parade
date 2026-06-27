import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { CurrentSession } from "../types/session";

type SessionContextValue = {
  currentSession: CurrentSession | null;
  setCurrentSession: (session: CurrentSession | null) => void;
  retakeContext: Omit<CreateSessionDefaults, never> | null;
  setRetakeContext: (ctx: CreateSessionDefaults | null) => void;
};

export type CreateSessionDefaults = {
  cadet_id?: string;
  cadet_name: string;
  drill_type: string;
  camera_id: string;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [currentSession, setCurrentSession] = useState<CurrentSession | null>(null);
  const [retakeContext, setRetakeContext] = useState<CreateSessionDefaults | null>(null);

  const value = useMemo(
    () => ({ currentSession, setCurrentSession, retakeContext, setRetakeContext }),
    [currentSession, retakeContext],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSessionState() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSessionState must be used within SessionProvider");
  }
  return ctx;
}
