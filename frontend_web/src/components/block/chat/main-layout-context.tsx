import { createContext, createElement, useContext } from 'react';
import type { ReactNode } from 'react';

export interface MainLayoutContext {
  hasChat: boolean;
  isNewChat: boolean;
  isLoadingChats: boolean;
  addChatHandler: () => void;
  refetchChats: () => Promise<unknown>;
}

const MainLayoutContext = createContext<MainLayoutContext | null>(null);

export function MainLayoutProvider({
  value,
  children,
}: {
  value: MainLayoutContext;
  children: ReactNode;
}) {
  return createElement(MainLayoutContext.Provider, { value }, children);
}

export function useMainLayout() {
  const ctx = useContext(MainLayoutContext);
  if (!ctx) throw new Error('useMainLayout must be used within MainLayoutProvider');
  return ctx;
}
