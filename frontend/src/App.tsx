import { RouterProvider } from 'react-router-dom';
import { router } from './routes';

/**
 * App root. All routing is declared in `src/routes`
 * so new sections can register pages without touching this file.
 */
export default function App() {
  return <RouterProvider router={router} />;
}
