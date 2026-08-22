# API contract conventions

All application endpoints are below `/api/v1`. Authenticated endpoints require `Authorization: Bearer <Supabase access token>`.

## Success responses

JSON uses `snake_case`. Timestamps are UTC ISO-8601 strings. IDs are UUID strings.

## Errors

Errors use a stable envelope:

```json
{
  "error": {
    "code": "document_not_found",
    "message": "The document does not exist or is not accessible.",
    "request_id": "...",
    "details": null
  }
}
```

Messages are safe for display. Stack traces, SQL, credentials, provider payloads, and document contents are never returned.

## Streaming

Chat responses use Server-Sent Events. Event types are `meta`, `token`, `citation`, `done`, and `error`. Every event has JSON data. The final `done` event contains the persisted message ID.

## Primary resources

- `/account/me`: profile/quota read and confirmed permanent account deletion.
- `/documents`: list, private upload intents, completion, job status, source links, reprocess/retry, and delete.
- `/conversations`: create, list, rename, delete, and persisted message history.
- `/chat/stream`: evidence-grounded SSE answer stream.
- `/feedback`: idempotent helpful/not-helpful feedback on owned assistant messages.

Document list items include the latest `job_stage` and `job_progress`. Reprocessing creates a new immutable version; the previous active version remains available to retrieval until the new version publishes atomically.
