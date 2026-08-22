# Zero-cost deployment

Deploy in this order: Supabase, Render, frontend, then Auth callbacks and Turnstile. This ensures each later service can point at a real earlier URL.

## 1. Supabase

Apply the migration as described in [setup.md](setup.md). Use the Shared Supavisor **session** pooler on port 5432 for Render; the direct database hostname may require IPv6. Never place the service-role key in Cloudflare's browser build variables.

## 2. Render backend

Create a Render Blueprint from `render.yaml` or a Docker web service rooted at the repository. Provide every `sync: false` value:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://...` session-pooler URL |
| `SUPABASE_URL` | project URL |
| `SUPABASE_PUBLISHABLE_KEY` | browser-safe project key |
| `SUPABASE_SERVICE_ROLE_KEY` | server-only service-role key |
| `GEMINI_API_KEY` | server-only AI Studio key |
| `CORS_ORIGINS` | final frontend origin, no path |
| `TRUSTED_HOSTS` | Render hostname, comma-separated if custom domain is added |

The health check is `/api/v1/health`. Render's free service can sleep after inactivity. The frontend converts long first-request timeouts into a clear warm-up message, and ingestion jobs recover after restarts.

## 3. Cloudflare frontend

This Vinext build contains a small server-rendered app-router worker plus static assets. Therefore deployment uses Cloudflare Workers with Assets rather than a Pages-only static export. It remains on Cloudflare's free edge tier and keeps all browser functionality; the choice is recorded in ADR 0004.

Set these **build-time** values in the shell or Cloudflare build environment:

```dotenv
NEXT_PUBLIC_API_URL=https://YOUR_RENDER_HOST/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
NEXT_PUBLIC_STORAGE_BUCKET=documents
NEXT_PUBLIC_TURNSTILE_SITE_KEY=YOUR_OPTIONAL_SITE_KEY
NEXT_PUBLIC_SITE_URL=https://YOUR_FRONTEND_HOST
```

Authenticate Wrangler and deploy locally:

```bash
npx wrangler login
npm install --global npm@11.6.2
npm ci
npm run deploy:cloudflare
```

The generated deployment config is `dist/server/wrangler.json`; the build embeds only browser-safe public values. Cloudflare serves the `dist/client` assets and `dist/server` worker together.

Alternatively configure the variables and token listed in `.github/workflows/deploy-frontend.yml`, then run that manual production workflow. Supabase type generation and migrations have a separate approval-gated manual workflow in `.github/workflows/supabase.yml`.

## 4. Final cross-service configuration

1. Set Render `CORS_ORIGINS` to the exact Cloudflare HTTPS origin.
2. Set Render `TRUSTED_HOSTS` to the Render service hostname.
3. Add the frontend site URL and `/auth/callback` plus `/reset-password` URLs in Supabase Auth.
4. If using Turnstile, add the production hostname to the widget and enable its secret in Supabase.
5. Trigger a clean Render deploy and a clean frontend build after URL changes.

## 5. Live verification

Use two different email accounts:

1. Register and verify both.
2. Upload `evaluation/fixtures/atlas-handbook.md` as user A and wait for 100% processing.
3. Ask a dataset question and open its citation.
4. Confirm user B cannot see user A's document, conversation, or source URL.
5. Restart/redeploy Render during a fresh ingestion and verify the job recovers.
6. Delete a document and confirm retrieval no longer cites it.
7. Delete the test account and confirm login no longer works.

Record the verified URLs and date in `IMPLEMENTATION_TRACKER.md`.

## Free-tier expectations

- There is no uptime or latency SLA.
- The first API request after sleep can be slow.
- Supabase may pause an inactive free project and free database backups are limited.
- Gemini free quotas can change. The application surfaces provider failures safely and preserves queued work.
