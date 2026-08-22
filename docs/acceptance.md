# Acceptance checklist

## Automated (credential-free)

- [x] Frontend ESLint and TypeScript pass.
- [x] Frontend component tests pass.
- [x] Desktop and mobile Chromium tests pass.
- [x] Vinext production build passes.
- [x] Backend import, Ruff, strict MyPy, and pytest pass.
- [x] npm production audit reports zero known vulnerabilities.
- [x] Python local dependency audit reports zero known third-party vulnerabilities.
- [x] Docker Compose configuration resolves.
- [x] Migration policy/static-schema tests pass.
- [x] Versioned RAG evaluator and safe fixture exist.

## Credential-dependent local/live

- [ ] Migration applies to a real Supabase project.
- [ ] New user verification and password recovery email work.
- [ ] Two users cannot read each other's documents, rows, conversations, or signed URLs.
- [ ] Every supported document type reaches `ready`.
- [ ] Invalid, oversized, scanned, and mismatched-MIME files fail safely.
- [ ] Render restart during ingestion recovers the job.
- [ ] Re-index keeps the previous active version searchable until publication.
- [ ] Grounded questions stream cited answers; unknown questions refuse.
- [ ] Source links open the correct private original and expire.
- [ ] Conversation memory survives sign-out/sign-in.
- [ ] Document, conversation, and account deletion remove their data.
- [ ] Online evaluation dataset passes.
- [ ] Final Cloudflare and Render URLs are recorded in the tracker.
