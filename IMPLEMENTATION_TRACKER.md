# Atlas RAG implementation tracker

This file is the persistent source of truth for the project. Update it whenever a work item is completed, blocked, superseded, or verified. On every resumed session, read this file before changing code.

## Status legend

- `[ ]` Pending
- `[~]` In progress
- `[x]` Completed and verified
- `[!]` Blocked (include the blocker and exact next action)

## Current state

- Last updated: 2026-08-23
- Current work item: 11.2 Complete remaining Render and Cloudflare configuration after hosted Supabase validation
- Overall status: repository published; hosted Supabase migrated and connected locally; Render and Cloudflare publication remain
- Blocking issues: none; a blank-label landing-page CTA is deferred until after the deployment path is complete
- Last successful verification: 23 backend tests, 2 component tests, 4 desktop/mobile browser tests, frontend build, strict type/lint checks, both dependency audits, both production images, local Supabase migration, and authenticated isolation/lifecycle probes passed
- Next action: commit and push the hosted-ingestion fixes and verification tracker, then continue Render deployment one user-operated step at a time

## Approved product decisions

- Authenticated, user-specific RAG application; there is no anonymous document upload.
- React + TypeScript frontend and FastAPI backend.
- Supabase Auth, PostgreSQL/pgvector, and private Storage in production.
- Gemini free-tier generation and embeddings behind provider interfaces.
- Cloudflare Workers-with-Assets frontend and Render-compatible backend. ADR 0004 explains why the server-rendered Vinext output cannot be a Pages-only static upload.
- Docker-based local development is optional and separate from production.
- Production-grade engineering practices on hobby-tier infrastructure; no uptime SLA is claimed.
- The public application saves each user's documents, conversations, messages, rolling summaries, citations, and feedback.
- Every user-owned database record is protected by ownership checks and PostgreSQL row-level security.
- Supported inputs: text PDFs, DOCX, TXT, Markdown, and HTML. Scanned PDFs are rejected with a clear OCR-required error.

## Implementation order

### 1. Repository, architecture, and configuration

- [x] 1.1 Initialize the web project and create this tracker.
- [x] 1.2 Establish frontend, backend, Supabase, infrastructure, evaluation, and documentation directories.
- [x] 1.3 Add environment templates with safe validation and no committed secrets.
- [x] 1.4 Record architecture decisions and trust boundaries.
- [x] 1.5 Define frontend/backend API contracts and shared error conventions.
- [x] 1.6 Verify clean dependency installation and baseline builds.

### 2. Database, migrations, RLS, and authentication

- [x] 2.1 Define profiles, documents, versions, chunks, ingestion jobs, conversations, messages, summaries, citations, feedback, and audit tables.
- [x] 2.2 Enable pgvector and full-text search support.
- [x] 2.3 Add indexes, constraints, update triggers, and lifecycle functions.
- [x] 2.4 Add row-level security policies for all user-owned data.
- [x] 2.5 Implement Supabase JWT verification in FastAPI.
- [x] 2.6 Implement frontend registration, login, verification, reset, session restoration, logout, and optional Turnstile.
- [x] 2.7 Static policy tests and a live local two-account API/Storage isolation probe pass; production repetition is item 11.3.

### 3. Document storage and durable ingestion

- [x] 3.1 Implement private, RLS-scoped direct uploads, confirmation tokens, and user storage paths.
- [x] 3.2 Enforce file, page, document-count, and storage quotas.
- [x] 3.3 Implement PDF, DOCX, TXT, Markdown, and HTML parsers.
- [x] 3.4 Implement scanned-PDF detection and safe rejection.
- [x] 3.5 Implement structure-aware chunking and stable source locations.
- [x] 3.6 Implement durable, idempotent, resumable ingestion jobs and expired-intent cleanup.
- [x] 3.7 Implement batched Gemini embeddings and atomic publication.
- [x] 3.8 Implement reprocessing, retry, deletion-based cancellation, race protection, and complete deletion.
- [x] 3.9 Parser/chunking/storage/security tests and a real local database upload/job/retry/deletion lifecycle pass.

### 4. Hybrid retrieval and Gemini orchestration

- [x] 4.1 Implement user-scoped PostgreSQL keyword retrieval.
- [x] 4.2 Implement user-scoped pgvector similarity retrieval.
- [x] 4.3 Implement reciprocal-rank fusion, overlap removal, and evidence selection.
- [x] 4.4 Implement configurable Gemini generation and embedding providers.
- [x] 4.5 Implement grounded prompting and insufficient-evidence refusal.
- [x] 4.6 Implement citation generation and server-side citation validation.
- [x] 4.7 Add retrieval, grounding, refusal, prompt-injection, and citation tests.

### 5. Conversation persistence and memory

- [x] 5.1 Implement conversation and message APIs.
- [x] 5.2 Implement recent-turn context and rolling summaries.
- [x] 5.3 Implement SSE answer streaming with disconnect handling.
- [x] 5.4 Persist answer status, evidence, citations, usage, and latency.
- [x] 5.5 Implement conversation rename and deletion.
- [x] 5.6 Ownership, persistence, and two-account conversation isolation pass locally; Gemini-backed production restoration is item 11.3.

### 6. Complete React interface

- [x] 6.1 Establish the final responsive design system and product shell.
- [x] 6.2 Implement landing, registration, login, reset, and verification screens.
- [x] 6.3 Implement the document library, upload flow, live job progress, retry/re-index, and deletion.
- [x] 6.4 Implement streaming chat, conversation navigation, and empty/error states.
- [x] 6.5 Implement citation/source viewer and feedback controls.
- [x] 6.6 Implement account, privacy, quota, and data-deletion screens.
- [x] 6.7 Implement warm-up, offline, rate-limit, and service-error experiences.
- [x] 6.8 Verify desktop/mobile rendering and keyboard focus in Chromium; semantic roles are component-tested.

### 7. Security, quotas, evaluation, and automated tests

- [x] 7.1 Add request IDs, structured safe logs, security headers/CSP, CORS, and trusted hosts.
- [x] 7.2 Add per-user rate limits, email verification guidance, and optional Turnstile.
- [x] 7.3 Add filename, MIME, content-size, and prompt-injection defenses.
- [x] 7.4 Add backend, component, desktop/mobile end-to-end, schema, and security test suites.
- [x] 7.5 Add a versioned RAG evaluation dataset, safe fixture, scoring, and online runner.
- [x] 7.6 Add npm/pip audits, Dependabot, Gitleaks, and Trivy CI scanning.
- [x] 7.7 Review structured log callsites: no secrets, prompts, answers, or document bodies are logged.

### 8. Docker development environment

- [x] 8.1 Production frontend/backend images build, boot as non-root users, and pass their HTTP health checks.
- [x] 8.2 Supabase CLI supplies verified local Auth, PostgreSQL 17/pgvector, private Storage, and API services.
- [x] 8.3 Add container health checks and deterministic startup ordering; `docker compose config` passes.
- [x] 8.4 Document local Supabase, hosted-Supabase, process, and Docker modes.
- [x] 8.5 Docker Desktop validation completed: images built, local migration reset cleanly, runtime probes passed, temporary services were torn down, and Docker Desktop was returned to its prior stopped state.

### 9. CI/CD and production configuration

- [x] 9.1 Add GitHub Actions for linting, type checks, tests, browser checks, builds, and security checks.
- [x] 9.2 Add generated Cloudflare Worker/Assets deployment configuration and a manual deployment workflow.
- [x] 9.3 Add Render Blueprint configuration for FastAPI.
- [x] 9.4 Add approval-gated Supabase migration and type-generation workflows.
- [x] 9.5 Document required production secrets, public build variables, and callback URLs.
- [x] 9.6 Frontend build, Compose/Render configuration, and both production container images verify.

### 10. Portfolio documentation and final validation

- [x] 10.1 Write the portfolio README, architecture explanation, feature list, and tradeoffs.
- [x] 10.2 Add setup, deployment, security, privacy, and operational runbooks.
- [x] 10.3 Add architecture and data-flow diagrams.
- [x] 10.4 Add an original evaluation document and versioned questions under the MIT license.
- [x] 10.5 All credential-free code, build, audit, migration, container, runtime, and local-service checks pass.
- [~] 10.6 Credential-free browser and authenticated local Auth/API/Storage acceptance pass; Gemini-backed live production acceptance remains item 11.3.
- [x] 10.7 Record all credential-dependent setup and deployment steps for the user.

### 11. Publication

- [x] 11.1 Create or choose the user-owned GitHub repository, then commit and push the verified implementation.
- [~] 11.2 Obtain user-owned Supabase, Gemini, Render, and Cloudflare credentials/configuration only after local validation. Supabase and Gemini are configured locally; Render and Cloudflare remain.
- [~] 11.3 Apply migrations and deploy the production services. The hosted Supabase migration and local backend connection are verified; service deployment remains.
- [ ] 11.4 Verify registration, upload, ingestion, retrieval, memory, citations, and deletion on the live URL.
- [ ] 11.5 Record the live URLs and deployment verification date.

## Blocker log

- Resolved 2026-08-22: Docker Desktop was started with approval. Both images and the local Supabase stack now validate.
- The first full Supabase start timed out only in its unused analytics container. Atlas's documented local command excludes `logflare,vector`; this does not disable the PostgreSQL pgvector extension. Auth, PostgreSQL, Storage, REST, and Studio then passed.
- Production publication is intentionally deferred until the user supplies/authorizes the GitHub remote plus Supabase, Gemini, Render, and Cloudflare configuration in item 11.
- Deferred 2026-08-23: the landing page's first dark CTA renders without visible label text; it does not block authentication/deployment validation and will be fixed after the publication path.
- Resolved 2026-08-23: hosted ingestion reached publication but failed because the worker read rows from the preceding `document_versions` update instead of the `documents ... returning` update. The result assignment was corrected and regression-tested.
- Resolved 2026-08-23: the next hosted retry exposed asyncpg's inability to infer polymorphic `jsonb_build_object` parameter types in the audit insert. Audit metadata is now serialized explicitly and cast to `jsonb`, with regression coverage.

## Verification log

- 2026-08-21: Pinned Sites-compatible React scaffold created successfully.
- 2026-08-22: Frontend ESLint, TypeScript, Vitest (2 tests), and Vinext production build passed.
- 2026-08-22: Backend import, Ruff, strict MyPy, and pytest (23 tests) passed; coverage was 55.69% across the full API including database-only paths.
- 2026-08-22: Playwright passed 4/4 public desktop/mobile Chromium acceptance tests.
- 2026-08-22: `npm audit --omit=dev` and `pip-audit --local` reported no known third-party vulnerabilities after upgrades.
- 2026-08-22: Compiled frontend served HTTP 200 with CSP, frame denial, and MIME-sniffing denial; CSP includes the configured API and Supabase origins.
- 2026-08-22: Backend (116.6 MB) and frontend (336.9 MB) images built and ran healthy as the non-root `atlas` user.
- 2026-08-22: Local Supabase migration and clean reset passed on PostgreSQL 17 with pgvector 0.8.2, 10/10 RLS tables, 10 table policies, four private Storage policies, a non-public 10 MiB bucket, and `vector(768)` embeddings.
- 2026-08-22: Browser table mutation was denied with 403; two-account API isolation, private Storage owner/foreign reads, durable upload/job creation, cross-user document denial, database deletion, and object deletion passed.
- 2026-08-22: Final backend image returned HTTP 200 from both liveness and readiness when connected to the local database with complete validation settings.
- 2026-08-22: `docker compose config` passed and the final desktop/mobile Chromium suite passed 4/4.
- 2026-08-22: All validation containers, local Supabase services, localhost test servers, and Docker Desktop were stopped after verification.
- 2026-08-23: GitHub publication and CI completed; the hosted Supabase migration applied successfully, the local backend readiness endpoint returned `status: ok`, and the frontend loaded against the hosted project.
- 2026-08-23: Hosted email registration and authenticated workspace access passed. The ingestion publication regression test, Ruff, strict MyPy, and all 24 backend tests pass after correcting the publication result check.
- 2026-08-23: The hosted fixture upload completed at 100% and reached `ready`; private Storage, parsing, Gemini embeddings, pgvector publication, audit insertion, and durable job completion are verified together.
- 2026-08-23: Hosted hybrid retrieval and grounded chat passed: the answer contained pgvector, PostgreSQL full-text search, reciprocal-rank fusion, validated citation markers, and an authorized source-detail view.

## Resume protocol

1. Read this file completely.
2. Check `git status` without discarding user changes.
3. Run the last recorded successful verification when relevant.
4. Continue the first `[~]` item, or the first pending item if none is active.
5. Update the current state, checklist, blocker log, and verification log before ending work.
