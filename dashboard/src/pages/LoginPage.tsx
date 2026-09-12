import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldCheck, User, Lock, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { DotPattern } from '@/registry/magicui/dot-pattern';
import { AnimatedGradientText } from '@/registry/magicui/animated-gradient-text';
import { ShimmerButton } from '@/registry/magicui/shimmer-button';

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
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="flex min-h-screen items-center justify-center bg-bg"
    >
      {/* Background dot pattern */}
      <DotPattern className="opacity-50" />

      {/* Login card */}
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="relative z-10 w-full max-w-md px-4"
      >
        <div className="rounded-2xl border border-border bg-surface/80 p-8 shadow-2xl backdrop-blur-sm">
          {/* Logo */}
          <div className="mb-8 flex flex-col items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10">
              <ShieldCheck size={28} className="text-accent" />
            </div>
            <div className="text-center">
              <AnimatedGradientText className="text-2xl font-bold">
                IBVAP
              </AnimatedGradientText>
              <p className="mt-1 text-sm text-text-muted">
                Intelligent Border Video Analytics Platform
              </p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label htmlFor="officerId" className="mb-1.5 block text-xs font-medium text-text-muted">
                Officer ID
              </label>
              <div className="relative">
                <User size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  id="officerId"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={officerId}
                  onChange={(e) => setOfficerId(e.target.value)}
                  placeholder="Enter your Officer ID"
                  className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-9 pr-3 text-sm text-text placeholder:text-text-muted/50 outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-text-muted">
                Password
              </label>
              <div className="relative">
                <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-9 pr-10 text-sm text-text placeholder:text-text-muted/50 outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-text-muted transition-colors hover:text-text"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                role="alert"
                className="rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-3 py-2 text-xs text-severity-critical"
              >
                {error}
              </motion.div>
            )}

            <ShimmerButton
              type="submit"
              disabled={submitting}
              className="w-full"
              background="linear-gradient(110deg, #3da5d9 0%, #2b8cb8 50%, #3da5d9 100%)"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  Verifying...
                </span>
              ) : (
                'Secure Login'
              )}
            </ShimmerButton>
          </form>

          <p className="mt-6 text-center text-xs text-text-muted">
            Ministry of Home Affairs, Government of India
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
