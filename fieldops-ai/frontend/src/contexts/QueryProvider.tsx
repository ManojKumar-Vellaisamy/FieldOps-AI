import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import type { ReactNode } from 'react';
import { APP_CONSTANTS } from '@/config/constants';
import { env } from '@/config/env';

// ── Query Client ─────────────────────────────────────────────────────────────
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: APP_CONSTANTS.QUERY.STALE_TIME,
      gcTime: APP_CONSTANTS.QUERY.CACHE_TIME,
      retry: APP_CONSTANTS.QUERY.RETRY_COUNT,
      retryDelay: (attempt) => Math.min(APP_CONSTANTS.QUERY.RETRY_DELAY * 2 ** attempt, 30_000),
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

// ── Provider ─────────────────────────────────────────────────────────────────
interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {env.isDevelopment && <ReactQueryDevtools initialIsOpen={false} position="bottom" />}
    </QueryClientProvider>
  );
}
