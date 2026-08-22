# Operational runbook

## Health and readiness

- `GET /api/v1/health` is liveness plus safe configuration diagnostics; it remains available while degraded.
- `GET /api/v1/ready` executes a database query and returns 503 when required runtime configuration is missing. Render and Docker use this endpoint.
- Every HTTP response includes `X-Request-ID`; ask for this value when investigating a user-visible error.

## First request is slow

Likely cause: Render free-service sleep. Wait up to one minute, check `/api/v1/health`, then retry. A persistent failure is not normal warm-up; inspect Render deploy and runtime logs.

## Ingestion is queued or processing too long

1. Check Render is awake and `/ready` succeeds.
2. Inspect the latest `ingestion_jobs` row: stage, progress, attempts, heartbeat, and error code.
3. If the worker restarted, wait for the ten-minute stale lease to be recovered.
4. Provider/server errors retry automatically. Validation errors require a corrected document or manual reprocess.
5. Never edit vectors by hand; re-index through the API/UI.

## Gemini quota/provider failure

Chat returns a stable provider error and ingestion returns to the retry queue with exponential backoff. Do not delete pending jobs. Confirm model names and API-key quota, then let the retry run or use Re-index after the final attempt.

## Database connection failure

Confirm Render uses the Shared Supavisor session-pooler hostname on port 5432 and the `postgresql+asyncpg://` scheme. Test `/ready`. A password reset requires updating `DATABASE_URL` and redeploying.

## Authentication failure

Check project URL, publishable key, JWT mode, Supabase Auth health, allowed redirect URLs, and system time. JWKS is the default. `AUTH_VERIFY_MODE=remote` is a compatibility fallback for legacy symmetric tokens.

## Storage failure

Check bucket name, service-role key, private bucket policies, and object path ownership. Never make the bucket public as a workaround.

## User reports missing citations

A deliberate insufficient-evidence answer has no citations. Otherwise inspect the persisted assistant message and citation rows. Invalid model markers are changed to `[citation unavailable]`; run the evaluator if this rate increases.

## Backup and recovery

The source of truth for schema is the migration directory. Free Supabase backup guarantees are limited; important portfolio fixtures belong in Git, not only in the database. Before a breaking migration, create a manual export if the project contains data worth retaining.

## Rollback

Revert the application commit and redeploy. Database migrations are forward-only by default: create a compensating migration after confirming data impact. Never rewrite a migration already applied to production.
