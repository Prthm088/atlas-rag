# Privacy and data lifecycle

Atlas requires registration because saved documents and conversation memory need a stable owner. Anonymous upload is intentionally unsupported.

## Stored data

- Supabase Auth stores account identity and password credentials.
- Private Storage stores original documents below `<user-id>/<document-id>/original/...`.
- PostgreSQL stores document metadata, chunks, embeddings, jobs, conversations, rolling summaries, messages, citations, feedback, and audit events.
- FastAPI sends selected document chunks, the question, and limited conversation context to Gemini for embeddings/generation.

The application should be used only with non-sensitive portfolio content. The free Gemini tier may use submitted content to improve provider products; this notice appears during authentication and in account settings.

## Retention and deletion

- Uploaded files and derived data remain until the user deletes the document or account.
- Expired, unconfirmed upload intents are cleaned automatically.
- Document deletion removes the private object and cascades through versions, chunks, jobs, and citations.
- Conversation deletion cascades through its messages, citations, and feedback.
- Account deletion removes stored objects, then deletes the Supabase Auth user; database rows cascade from that identity.

Deletion is permanent from the live application. Provider logs/backups may follow the provider's own retention policy and free-tier limitations.

## Access

Users can see only records owned by their verified account. Source links are generated on demand and expire after five minutes. The service-role and Gemini credentials never enter the browser bundle.
