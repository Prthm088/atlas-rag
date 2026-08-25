'use client';

/* eslint-disable @next/next/no-html-link-for-pages -- Vinext beta soft navigation is broken in the production Worker bundle. */

import { ArrowRight, CheckCircle2, Loader2, LockKeyhole, Mail } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { Turnstile } from '@/components/turnstile';
import { getSupabase, isSupabaseConfigured } from '@/lib/supabase';

type Mode = 'login' | 'register' | 'forgot' | 'update';

export function AuthCard({ initialMode = 'login' }: { initialMode?: Mode }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null); setMessage(null);
    try {
      if (!isSupabaseConfigured()) throw new Error('Add the Supabase browser settings before signing in.');
      if (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY && !captchaToken) {
        throw new Error('Complete the bot-protection check and try again.');
      }
      const auth = getSupabase().auth;
      if (mode === 'login') {
        const result = await auth.signInWithPassword({
          email,
          password,
          options: captchaToken ? { captchaToken } : undefined,
        });
        if (result.error) throw result.error;
        const requestedPath = new URLSearchParams(window.location.search).get('next');
        const nextPath = requestedPath?.startsWith('/') && !requestedPath.startsWith('//')
          ? requestedPath
          : '/workspace';
        window.location.replace(nextPath);
      } else if (mode === 'register') {
        const result = await auth.signUp({
          email,
          password,
          options: {
            data: { display_name: displayName.trim() || undefined },
            emailRedirectTo: `${window.location.origin}/auth/callback`,
            captchaToken: captchaToken ?? undefined,
          },
        });
        if (result.error) throw result.error;
        setMessage('Check your inbox to verify your account, then sign in.');
      } else if (mode === 'forgot') {
        const result = await auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
          captchaToken: captchaToken ?? undefined,
        });
        if (result.error) throw result.error;
        setMessage('If that address exists, a password-reset link is on its way.');
      } else {
        const result = await auth.updateUser({ password });
        if (result.error) throw result.error;
        setMessage('Password updated. You can continue to your workspace.');
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Authentication failed.');
    } finally { setBusy(false); }
  };

  const title = mode === 'login' ? 'Welcome back' : mode === 'register' ? 'Create your private workspace' : mode === 'forgot' ? 'Reset your password' : 'Choose a new password';
  const subtitle = mode === 'login' ? 'Continue where your research left off.' : mode === 'register' ? 'Your documents and conversations stay isolated to your account.' : mode === 'forgot' ? 'We’ll send a secure recovery link.' : 'Use at least eight characters.';

  return (
    <main className="auth-page">
      <a className="brand auth-brand" href="/"><span className="brand-mark">A</span><span>Atlas</span></a>
      <section className="auth-card">
        <div className="auth-icon"><LockKeyhole size={20} /></div>
        <p className="eyebrow">Private by account</p>
        <h1>{title}</h1>
        <p className="auth-subtitle">{subtitle}</p>
        {message && <div className="notice success"><CheckCircle2 size={18} /><span>{message}</span></div>}
        {error && <div className="notice error" role="alert"><span>{error}</span></div>}
        <form onSubmit={submit}>
          {mode === 'register' && <label>Display name<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} autoComplete="name" placeholder="Your name" /></label>}
          {mode !== 'update' && <label>Email address<div className="input-icon"><Mail size={16} /><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com" /></div></label>}
          {(mode === 'login' || mode === 'register' || mode === 'update') && <label>Password<input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} placeholder="At least 8 characters" /></label>}
          {mode !== 'update' && <Turnstile onToken={setCaptchaToken} />}
          <button className="primary-button auth-submit" disabled={busy} type="submit">{busy ? <Loader2 className="spin" size={18} /> : <>{mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : mode === 'forgot' ? 'Send recovery link' : 'Update password'}<ArrowRight size={17} /></>}</button>
        </form>
        {mode === 'login' && <button className="text-button" onClick={() => setMode('forgot')}>Forgot password?</button>}
        {(mode === 'forgot' || mode === 'update') && <button className="text-button" onClick={() => setMode('login')}>Back to sign in</button>}
        {(mode === 'login' || mode === 'register') && <div className="auth-switch">{mode === 'login' ? 'New to Atlas?' : 'Already have an account?'} <button onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></div>}
        <p className="privacy-note">Use non-sensitive portfolio documents only. Free-tier AI processing may be used by the provider to improve its products.</p>
      </section>
    </main>
  );
}
