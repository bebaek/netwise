import { FormEvent, type ReactNode, useEffect, useState } from 'react';

import {
  type AuthStatus,
  type User,
  getAuthStatus,
  login,
  logout,
  register,
} from '../api';

type AuthMode = 'login' | 'register';

export function AuthGate({
  children,
}: {
  children: (user: User, onLogout: () => Promise<void>) => ReactNode;
}) {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [mode, setMode] = useState<AuthMode>('login');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getAuthStatus()
      .then((result) => {
        setAuthStatus(result);
        if (result.setup_required) setMode('register');
      })
      .catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get('email') ?? '').trim();
    const password = String(form.get('password') ?? '');
    setSubmitting(true);
    setError('');
    try {
      const user = mode === 'register'
        ? await register({
            display_name: String(form.get('display_name') ?? '').trim(),
            email,
            password,
          })
        : await login({ email, password });
      setAuthStatus((current) => ({
        setup_required: false,
        public_signup_enabled: current?.public_signup_enabled ?? false,
        user,
      }));
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    setError('');
    try {
      await logout();
      setAuthStatus((current) => ({
        setup_required: false,
        public_signup_enabled: current?.public_signup_enabled ?? false,
        user: null,
      }));
      setMode('login');
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  if (authStatus?.user) return children(authStatus.user, handleLogout);

  const setupRequired = authStatus?.setup_required ?? false;
  const registering = setupRequired || mode === 'register';
  const signupAvailable = authStatus?.public_signup_enabled ?? false;

  return (
    <main className="app-shell">
      <section className="card narrow auth-card" aria-labelledby="auth-heading">
        <p className="eyebrow">Netwise</p>
        <h1 id="auth-heading">{setupRequired ? 'Set up Netwise' : registering ? 'Create account' : 'Sign in'}</h1>
        <p className="muted">
          {setupRequired
            ? 'Create the initial owner account. It will own existing households on this installation.'
            : 'Use your Netwise account to access your household finances.'}
        </p>

        {error && <div className="error" role="alert">{error}</div>}
        {!authStatus && !error && <div role="status">Checking authentication…</div>}

        {authStatus && (
          <form onSubmit={handleSubmit} className="form-grid compact-form">
            {registering && (
              <label>
                Display name
                <input name="display_name" autoComplete="name" required maxLength={200} />
              </label>
            )}
            <label>
              Email
              <input name="email" type="email" autoComplete="email" required maxLength={320} />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={registering ? 'new-password' : 'current-password'}
                required
                minLength={registering ? 12 : 1}
                maxLength={128}
              />
            </label>
            {registering && <p className="muted">Use at least 12 characters.</p>}
            <button type="submit" disabled={submitting}>
              {submitting ? 'Please wait…' : setupRequired ? 'Create owner account' : registering ? 'Create account' : 'Sign in'}
            </button>
          </form>
        )}

        {!setupRequired && signupAvailable && authStatus && (
          <button className="button-link" type="button" onClick={() => setMode(registering ? 'login' : 'register')}>
            {registering ? 'Already have an account? Sign in' : 'Create an account'}
          </button>
        )}
      </section>
    </main>
  );
}
