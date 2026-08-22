# ADR 0002: Supabase for auth, PostgreSQL/pgvector, and private files

- Status: accepted
- Date: 2026-08-21

## Decision

Use Supabase Auth, PostgreSQL with pgvector, and private Storage. The backend connects through the free IPv4 session pooler in production.

## Why

This consolidates three durable capabilities into one free service and keeps vector data next to ownership metadata. Row-level security is available as defense in depth.

## Consequences

- The free database and storage quotas constrain per-user usage.
- Free projects may pause and do not provide a production SLA or managed backup retention.
- Database migrations, data export instructions, and a warm-up UI are required.
