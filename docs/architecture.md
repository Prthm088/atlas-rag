# Atlas architecture

## Purpose

Atlas is an authenticated retrieval-augmented generation application for a low-traffic portfolio deployment. It applies production engineering practices while explicitly accepting the availability and capacity limits of free hosting.

## Runtime topology

```text
Browser
  ├─ React/Vinext frontend (Cloudflare Worker with static assets)
  ├─ Supabase Auth and private Storage (user JWT + storage RLS)
  └─ FastAPI over HTTPS (Render)
       ├─ Supabase PostgreSQL through the IPv4 session pooler
       ├─ Supabase private Storage through a server-only service credential
       └─ Gemini generation and embedding APIs
```

## Trust boundaries

1. The browser is untrusted. It receives only the Supabase publishable key.
2. FastAPI verifies every access token and derives the user ID from the verified `sub` claim.
3. Client-provided user IDs are never accepted for authorization.
4. Every query includes the verified user ID. Application tables have no browser-role grants; PostgreSQL RLS remains a second authorization boundary if a narrow grant is introduced later.
5. The Supabase service-role credential and Gemini key exist only in the backend environment.
6. Retrieved document text is untrusted content and is delimited as evidence, never interpreted as system instructions.

## Data flow

### Upload and ingestion

1. FastAPI creates a user-owned document record and returns a private storage path.
2. The authenticated browser uploads directly to Supabase Storage. Storage RLS restricts the first path segment to the current user ID.
3. The browser confirms completion. FastAPI verifies the object and queues a persistent database job.
4. The embedded worker claims work with `FOR UPDATE SKIP LOCKED`, downloads the object, validates and parses it, chunks it, embeds it, and atomically publishes a document version.
5. Every stage and retry is recorded. A Render restart leaves the job resumable.

### Question answering

1. FastAPI verifies the user and conversation ownership.
2. It loads the rolling summary and recent turns.
3. It embeds the question and performs user-scoped keyword and vector retrieval.
4. Reciprocal-rank fusion and overlap removal produce the evidence set.
5. Gemini streams an evidence-constrained answer with chunk citation markers.
6. The backend rejects unknown citation markers and stores only validated citations.

## Deliberate constraints

- Text PDFs, DOCX, TXT, Markdown, and HTML are accepted.
- Scanned PDFs are rejected instead of silently producing weak retrieval.
- The database vector dimension is fixed at 768. Changing the embedding model or dimension requires a versioned re-index.
- The free Render service runs API and ingestion worker in one process. Database-backed jobs make this recoverable, but not highly available.
- Free-tier quotas are product requirements, not incidental deployment limits.
