# Security model

Atlas uses defense in depth: verified identity in FastAPI, ownership predicates in SQL, backend-only application tables, and row-level policies on PostgreSQL and browser-accessible Storage.

## Trust boundaries

| Boundary | Control |
| --- | --- |
| Browser → API | Supabase bearer token verified by JWKS or the Auth user endpoint; user ID comes only from verified `sub` |
| Browser → Storage | Private bucket; first object-path segment must equal `auth.uid()` |
| API → database | Parameterized SQL and an ownership predicate on every user operation; browser roles have no application-table privileges |
| Retrieved document → model | Evidence is explicitly untrusted and cannot override the system instruction |
| Model → persisted citation | Unknown citation markers are replaced; only retrieved chunk IDs can be saved |
| Public config → secrets | Only publishable Supabase/site keys use `NEXT_PUBLIC_`; Gemini/service-role keys stay server-side |

## Threats and mitigations

- **Cross-user access:** backend-only table grants, table RLS defense in depth, Storage policies, verified user-scoped queries, private signed source links, and cascade ownership.
- **Prompt injection in documents:** source text is delimited as untrusted evidence; the system prompt rejects source instructions; evaluation includes an adversarial fixture.
- **Malicious uploads:** strict extension/MIME pairing, size/page/chunk quotas, content parsing, UTF-8 checks, ZIP/DOCX validation, HTML executable-element removal, scanned-PDF rejection, and private storage.
- **Job duplication/restarts:** one active job per document, `SKIP LOCKED` claims, leases/heartbeats, exponential retry, stable versions, and atomic publication.
- **Deletion races:** a deleting document cannot be moved back to processing or published; database cascades remove vectors/citations and Storage is deleted separately.
- **Abuse/cost:** per-user chat/upload limits, document/storage quotas, email verification, optional Turnstile, bounded outputs, and no anonymous uploads.
- **Browser attacks:** CSP, frame denial, MIME sniffing denial, restricted referrers/permissions, and short-lived source links.
- **Supply chain:** npm/pip advisory checks, Dependabot, secret scanning, and Trivy image scanning in CI.

## Secret handling

Never log authorization headers, tokens, model prompts, complete document bodies, database URLs, or provider responses. Structured logs contain request IDs, safe paths, statuses, durations, document/job IDs, and error codes only.

If a secret is committed, rotate it immediately, remove it from Git history, invalidate active sessions if relevant, and redeploy. Do not rely on deleting the current file alone.

## Remaining free-tier limitations

- The rate limiter is memory-local. It is correct for the intended single API process, not a multi-instance deployment.
- The embedded worker is recoverable, not highly available.
- Uploaded content reaches Supabase and Gemini. The product explicitly tells users not to upload confidential data.
- Local two-account acceptance verifies API isolation, forged-row rejection, and private Storage isolation; the same checklist must be repeated on the deployed Supabase project.
