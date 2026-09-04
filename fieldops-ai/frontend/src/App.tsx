import { AppLayout } from '@/layouts/AppLayout';
import { AppRouter } from '@/routes/router';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { QueryProvider } from '@/contexts/QueryProvider';
import { AuthProvider } from '@/contexts/AuthContext';

/**
 * Root application component.
 * Composes global providers in the correct dependency order:
 *  1. ThemeProvider   — CSS class + localStorage
 *  2. QueryProvider   — React Query client
 *  3. AuthProvider    — JWT Session state & RBAC
 *  4. AppLayout       — Suspense boundary
 *  5. AppRouter       — React Router
 */
function App() {
  return (
    <ThemeProvider>
      <QueryProvider>
        <AuthProvider>
          <AppLayout>
            <AppRouter />
          </AppLayout>
        </AuthProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}

export default App;

