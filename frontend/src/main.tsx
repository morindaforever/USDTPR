import React from 'react';
import ReactDOM from 'react-dom/client';
import { AuthProvider } from '@/context/AuthContext';
import App from './App';
import './index.css';

// Routing comes from the data router in src/routes (createBrowserRouter),
// which manages its own history — no <BrowserRouter> wrapper here.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
