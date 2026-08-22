# ADR 0001: Modular monolith with an embedded durable worker

- Status: accepted
- Date: 2026-08-21

## Decision

Use one FastAPI deployable containing the HTTP API, RAG orchestration, and a background job runner. Keep modules separated by contracts, but do not deploy microservices.

## Why

Render does not provide a separate always-on worker in the approved zero-cost architecture. A database-backed job state machine gives retries and restart recovery without introducing an unavailable queue service. The low expected traffic does not justify distributed operations.

## Consequences

- A process restart can interrupt current work; the job lease expires and work resumes.
- Parsing is bounded by strict file/page/chunk quotas.
- Modules remain replaceable if a paid worker or queue is introduced later.
