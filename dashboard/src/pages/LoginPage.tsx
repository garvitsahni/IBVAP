import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldCheck, User, Lock, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import loginBackground from '../assets/login-background.png';

// BorderEye login page — background image on the left + credential card on the right.

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [officerId, setOfficerId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!officerId.trim() || !password) {
      setError('Enter your officer ID and password.');
      return;
    }

    setSubmitting(true);

    try {
      await login(officerId.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err?.message || 'Officer ID or password is incorrect.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full font-sans lg:flex">
      {/* Hero image panel */}
      <div
        className="relative hidden min-h-screen w-1/2 overflow-hidden bg-cover bg-center bg-no-repeat lg:block"
        style={{
          backgroundImage: `url(${loginBackground})`,
        }}
        aria-label="BorderEye border surveillance background"
      />

      {/* Credential card */}
      <div className="flex min-h-screen w-full items-center justify-center bg-surface-bg px-4 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-2 lg:hidden">
            <ShieldCheck size={20} className="text-brand-primary" />
            <span className="text-sm font-medium text-surface-text">
              Ministry of Home Affairs
            </span>
          </div>

          <div className="rounded-xl border border-surface-border bg-surface-card p-7 shadow-card">
            <div className="mb-6 flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-primary/10 text-brand-primary">
                <ShieldCheck size={18} />
              </div>
              <span className="text-lg font-semibold text-surface-text">
                BorderEye
              </span>
            </div>

            <p className="mb-1 text-xs uppercase tracking-wide text-surface-muted">
              Video Analytics Platform
            </p>

            <h1 className="mb-1 mt-3 text-xl font-semibold text-surface-text">
              Officer Login
            </h1>

            <p className="mb-6 text-sm text-surface-muted">
              Access restricted to authorized personnel only
            </p>

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <div>
                <label
                  htmlFor="officerId"
                  className="mb-1.5 block text-xs font-medium text-surface-muted"
                >
                  Officer ID
                </label>

                <div className="relative">
                  <User
                    size={16}
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-surface-muted"
                  />

                  <input
                    id="officerId"
                    type="text"
                    autoComplete="username"
                    autoFocus
                    value={officerId}
                    onChange={(e) => setOfficerId(e.target.value)}
                    placeholder="Enter your Officer ID"
                    className="w-full rounded-lg border border-surface-border bg-white py-2.5 pl-9 pr-3 text-sm text-surface-text placeholder:text-surface-muted/70 outline-none transition-colors focus:border-brand-primary focus:ring-1 focus:ring-brand-primary"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="mb-1.5 block text-xs font-medium text-surface-muted"
                >
                  Password
                </label>

                <div className="relative">
                  <Lock
                    size={16}
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-surface-muted"
                  />

                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full rounded-lg border border-surface-border bg-white py-2.5 pl-9 pr-10 text-sm text-surface-text placeholder:text-surface-muted/70 outline-none transition-colors focus:border-brand-primary focus:ring-1 focus:ring-brand-primary"
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-surface-muted transition-colors hover:text-surface-text"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs">
                <label className="flex items-center gap-1.5 text-surface-muted">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-surface-border text-brand-primary focus:ring-brand-primary"
                  />
                  Remember me
                </label>

                <button
                  type="button"
                  className="text-brand-primary hover:underline"
                >
                  Forgot password?
                </button>
              </div>

              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-3 py-2 text-xs text-severity-critical"
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-primary px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-primaryLight disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Verifying…
                  </>
                ) : (
                  'Login'
                )}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-surface-muted">
              Ministry of Home Affairs, Government of India
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
