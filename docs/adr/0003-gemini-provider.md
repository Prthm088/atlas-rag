# ADR 0003: Configurable Gemini provider

- Status: accepted
- Date: 2026-08-21

## Decision

Use Gemini's free-tier chat and embedding APIs behind application-owned interfaces. Store the embedding model and dimension with every document version.

## Why

The portfolio must not require paid API usage. Provider interfaces prevent Gemini-specific response types from leaking into retrieval and storage modules.

## Consequences

- Free-tier rate limits and data-use terms must be visible to users.
- Provider failures produce retryable jobs or explicit chat errors.
- A model change is evaluated and re-indexed rather than silently mixed with existing vectors.
