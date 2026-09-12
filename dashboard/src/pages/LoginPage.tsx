import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldCheck, User, Lock, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [officerId, setOfficerId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: string })?.from || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
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
      setError((err as Error)?.message || 'Officer ID or password is incorrect.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="w-full max-w-sm px-4">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2 border border-border">
            <ShieldCheck size={22} className="text-accent" />
          </div>
          <div className="text-center">
            <h1 className="font-display text-xl font-semibold text-text-primary">IBVAP</h1>
            <p className="mt-0.5 text-xs text-text-muted">
              Border Video Analytics
            </p>
          </div>
        </div>

        {/* Form */}
        <div className="rounded-lg border border-border bg-surface p-6">
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label htmlFor="officerId" className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-text-muted">
                Officer ID
              </label>
              <div className="relative">
                <User size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  id="officerId"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={officerId}
                  onChange={(e) => setOfficerId(e.target.value)}
                  placeholder="e.g. OFF-001"
                  className="w-full rounded-md border border-border bg-surface-2 py-2 pl-9 pr-3 text-sm text-text placeholder:text-text-muted/50 outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent/30"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-text-muted">
                Password
              </label>
              <div className="relative">
                <Lock size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="w-full rounded-md border border-border bg-surface-2 py-2 pl-9 pr-10 text-sm text-text placeholder:text-text-muted/50 outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent/30"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-text-muted transition-colors hover:text-text"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-md border border-severity-critical/20 bg-severity-critical/5 px-3 py-2 text-xs text-severity-critical"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-md bg-accent py-2.5 text-sm font-medium text-bg transition-colors hover:bg-accent-hover disabled:opacity-50"
            >
              {submitting ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  Verifying
                </span>
              ) : (
                'Sign In'
              )}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-[10px] text-text-muted">
          Ministry of Home Affairs · Government of India
        </p>
      </div>
    </div>
  );
}
