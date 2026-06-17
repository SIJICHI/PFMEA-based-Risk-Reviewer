'use client';
import React from 'react';
import { QueryClientProvider } from '@tanstack/react-query';

import { ThemeProvider } from '@/theme/theme-provider';
import { Toaster } from '@/components/ui/sonner';

import { queryClient } from '@/api/query-client';

export const Layout = ({ children }: { children: React.ReactNode }) => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {({ theme }) => (
          <>
            {children}
            <Toaster theme={theme} />
          </>
        )}
      </ThemeProvider>
    </QueryClientProvider>
  );
};
