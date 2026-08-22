# ADR 0004: Cloudflare Workers with Assets for the frontend

- Status: accepted
- Date: 2026-08-22

## Decision

Deploy the Vinext frontend as a Cloudflare Worker with its generated static asset binding instead of forcing a Pages-only static export.

## Why

The approved objective is a free Cloudflare-hosted frontend. Vinext produces React Server Component and app-router server output in addition to static assets. A Pages-only export would either fail or remove routing/runtime behavior. Workers with Assets hosts both outputs on Cloudflare's free edge tier and uses the generated `dist/server/wrangler.json` without a second server.

## Consequences

- Browser-safe environment variables are embedded at build time.
- FastAPI remains on Render; the edge worker does not contain database or AI credentials.
- The deployment command is `npm run deploy:cloudflare` rather than a Pages static-directory upload.
- Moving to a static SPA later remains possible, but would be a frontend build-system change with no backend/data migration.
