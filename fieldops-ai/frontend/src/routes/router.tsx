import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { routes } from './index';

const router = createBrowserRouter(routes, {
  future: {
    v7_relativeSplatPath: true,
  },
});

/**
 * Root router component — renders the React Router provider with all app routes.
 */
export function AppRouter() {
  return <RouterProvider router={router} />;
}
