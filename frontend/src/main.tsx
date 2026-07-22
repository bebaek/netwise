import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthGate } from './components/AuthGate';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthGate>
        {(user, onLogout) => <App authenticatedUser={user} onLogout={onLogout} />}
      </AuthGate>
    </BrowserRouter>
  </React.StrictMode>,
);
