'use client';

import { Loader2 } from 'lucide-react';
import { useEffect } from 'react';
import { getSupabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  useEffect(() => {
    getSupabase().auth.getSession().then(({ data }) => window.location.replace(data.session ? '/workspace' : '/auth'));
  }, []);
  return <main className="auth-page"><div className="callback-status"><Loader2 className="spin" /><p>Securing your session…</p></div></main>;
}
