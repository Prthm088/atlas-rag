'use client';

import { useEffect, useRef } from 'react';

type TurnstileApi = {
  render: (
    element: HTMLElement,
    options: {
      sitekey: string;
      theme: 'light';
      size: 'flexible';
      callback: (token: string) => void;
      'expired-callback': () => void;
      'error-callback': () => void;
    },
  ) => string;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const scriptId = 'atlas-turnstile-script';

export function Turnstile({ onToken }: { onToken: (token: string | null) => void }) {
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!siteKey || !container.current) return;
    let cancelled = false;
    let widgetId: string | null = null;

    const render = () => {
      if (cancelled || !container.current || !window.turnstile || widgetId) return;
      widgetId = window.turnstile.render(container.current, {
        sitekey: siteKey,
        theme: 'light',
        size: 'flexible',
        callback: (token) => onToken(token),
        'expired-callback': () => onToken(null),
        'error-callback': () => onToken(null),
      });
    };

    const existing = document.getElementById(scriptId) as HTMLScriptElement | null;
    if (window.turnstile) {
      render();
    } else if (existing) {
      existing.addEventListener('load', render, { once: true });
    } else {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.addEventListener('load', render, { once: true });
      document.head.appendChild(script);
    }

    return () => {
      cancelled = true;
      if (existing) existing.removeEventListener('load', render);
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
      onToken(null);
    };
  }, [onToken, siteKey]);

  if (!siteKey) return null;
  return <div className="turnstile-slot" ref={container} aria-label="Bot protection" />;
}
