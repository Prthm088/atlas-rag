import { Suspense } from 'react';
import { AuthCard } from '@/components/auth-card';

export default function AuthPage() {
  return <Suspense fallback={<main className="auth-page"><p>Loading secure sign-in…</p></main>}><AuthCard /></Suspense>;
}
