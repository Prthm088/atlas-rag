'use client';

import { Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { getSupabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();
  useEffect(() => {
    getSupabase().auth.getSession().then(({ data }) => router.replace(data.session ? '/workspace' : '/auth'));
  }, [router]);
  return <main className="auth-page"><div className="callback-status"><Loader2 className="spin" /><p>Securing your session…</p></div></main>;
}
