import { Suspense } from 'react';
import { AuthCard } from '@/components/auth-card';

export default function ResetPasswordPage() {
  return <Suspense fallback={<main className="auth-page"><p>Loading…</p></main>}><AuthCard initialMode="update" /></Suspense>;
}
