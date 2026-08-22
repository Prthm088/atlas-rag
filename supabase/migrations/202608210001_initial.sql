create extension if not exists pgcrypto with schema extensions;
create extension if not exists vector with schema extensions;

create type public.document_status as enum (
  'awaiting_upload', 'queued', 'processing', 'ready', 'failed', 'deleting'
);
create type public.version_status as enum ('pending', 'processing', 'published', 'failed');
create type public.job_status as enum ('pending', 'running', 'retrying', 'succeeded', 'failed', 'cancelled');
create type public.message_role as enum ('user', 'assistant');
create type public.message_status as enum ('pending', 'streaming', 'completed', 'failed', 'cancelled');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text check (char_length(display_name) <= 120),
  terms_accepted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 240),
  mime_type text not null check (char_length(mime_type) between 1 and 120),
  size_bytes bigint not null check (size_bytes > 0 and size_bytes <= 10485760),
  storage_path text not null unique,
  checksum_sha256 text check (checksum_sha256 ~ '^[a-f0-9]{64}$'),
  status public.document_status not null default 'awaiting_upload',
  active_version_id uuid,
  upload_token_hash text,
  upload_token_expires_at timestamptz,
  error_code text,
  error_message text check (char_length(error_message) <= 1000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index documents_user_created_idx on public.documents (user_id, created_at desc)
  where deleted_at is null;
create index documents_user_status_idx on public.documents (user_id, status)
  where deleted_at is null;

create table public.document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  version_number integer not null check (version_number > 0),
  status public.version_status not null default 'pending',
  parser_version text not null default 'atlas-parser-v1',
  embedding_model text,
  embedding_dimensions integer check (embedding_dimensions between 128 and 4096),
  chunk_count integer not null default 0 check (chunk_count >= 0),
  character_count integer not null default 0 check (character_count >= 0),
  page_count integer check (page_count >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  published_at timestamptz,
  unique (document_id, version_number)
);

alter table public.documents
  add constraint documents_active_version_fk
  foreign key (active_version_id) references public.document_versions(id) on delete set null;

create index document_versions_user_document_idx
  on public.document_versions (user_id, document_id, version_number desc);

create table public.chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  version_id uuid not null references public.document_versions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content text not null check (char_length(content) > 0),
  content_tsv tsvector generated always as (
    to_tsvector('english'::regconfig, coalesce(content, ''))
  ) stored,
  page_start integer check (page_start is null or page_start > 0),
  page_end integer check (page_end is null or page_end >= page_start),
  section_path text[] not null default '{}',
  token_count integer not null check (token_count > 0),
  content_hash text not null check (content_hash ~ '^[a-f0-9]{64}$'),
  embedding extensions.vector(768),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (version_id, chunk_index)
);

create index chunks_user_document_idx on public.chunks (user_id, document_id);
create index chunks_version_idx on public.chunks (version_id, chunk_index);
create index chunks_content_tsv_idx on public.chunks using gin (content_tsv);
create index chunks_embedding_hnsw_idx on public.chunks
  using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create table public.ingestion_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid not null references public.documents(id) on delete cascade,
  version_id uuid not null references public.document_versions(id) on delete cascade,
  status public.job_status not null default 'pending',
  stage text not null default 'queued',
  progress integer not null default 0 check (progress between 0 and 100),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  available_at timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  heartbeat_at timestamptz,
  error_code text,
  error_message text check (char_length(error_message) <= 1000),
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create unique index ingestion_jobs_active_document_idx
  on public.ingestion_jobs (document_id)
  where status in ('pending', 'running', 'retrying');
create index ingestion_jobs_claim_idx
  on public.ingestion_jobs (available_at, created_at)
  where status in ('pending', 'retrying');

create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New conversation' check (char_length(title) between 1 and 120),
  summary text check (char_length(summary) <= 12000),
  summary_message_count integer not null default 0 check (summary_message_count >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index conversations_user_updated_idx on public.conversations (user_id, updated_at desc);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.message_role not null,
  status public.message_status not null default 'pending',
  content text not null default '' check (char_length(content) <= 100000),
  model text,
  input_tokens integer check (input_tokens is null or input_tokens >= 0),
  output_tokens integer check (output_tokens is null or output_tokens >= 0),
  latency_ms integer check (latency_ms is null or latency_ms >= 0),
  error_code text,
  error_message text check (char_length(error_message) <= 1000),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index messages_conversation_created_idx
  on public.messages (conversation_id, created_at asc);
create index messages_user_created_idx on public.messages (user_id, created_at desc);

create table public.citations (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.messages(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid not null references public.documents(id) on delete cascade,
  version_id uuid not null references public.document_versions(id) on delete cascade,
  chunk_id uuid not null references public.chunks(id) on delete cascade,
  label integer not null check (label > 0),
  rank integer not null check (rank >= 0),
  document_name text not null,
  page_start integer,
  page_end integer,
  section_path text[] not null default '{}',
  quote text not null check (char_length(quote) between 1 and 1200),
  created_at timestamptz not null default now(),
  unique (message_id, label),
  unique (message_id, chunk_id)
);

create index citations_message_idx on public.citations (message_id, label);

create table public.feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  message_id uuid not null references public.messages(id) on delete cascade,
  rating smallint not null check (rating in (-1, 1)),
  comment text check (char_length(comment) <= 1000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, message_id)
);

create table public.audit_events (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  action text not null check (char_length(action) between 1 and 100),
  target_type text not null check (char_length(target_type) between 1 and 80),
  target_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index audit_events_user_created_idx on public.audit_events (user_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger documents_set_updated_at before update on public.documents
  for each row execute function public.set_updated_at();
create trigger ingestion_jobs_set_updated_at before update on public.ingestion_jobs
  for each row execute function public.set_updated_at();
create trigger conversations_set_updated_at before update on public.conversations
  for each row execute function public.set_updated_at();
create trigger feedback_set_updated_at before update on public.feedback
  for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, nullif(new.raw_user_meta_data ->> 'display_name', ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.document_versions enable row level security;
alter table public.chunks enable row level security;
alter table public.ingestion_jobs enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.citations enable row level security;
alter table public.feedback enable row level security;
alter table public.audit_events enable row level security;

create policy profiles_own on public.profiles for all to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));
create policy documents_own on public.documents for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy document_versions_own on public.document_versions for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy chunks_own_select on public.chunks for select to authenticated
  using (user_id = (select auth.uid()));
create policy ingestion_jobs_own_select on public.ingestion_jobs for select to authenticated
  using (user_id = (select auth.uid()));
create policy conversations_own on public.conversations for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy messages_own on public.messages for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy citations_own_select on public.citations for select to authenticated
  using (user_id = (select auth.uid()));
create policy feedback_own on public.feedback for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy audit_events_own_select on public.audit_events for select to authenticated
  using (user_id = (select auth.uid()));

-- Application tables are a backend-only data plane. The browser talks to
-- FastAPI for records and directly to Supabase only for Auth and private
-- Storage. Explicit revokes prevent a user from bypassing API quotas or
-- lifecycle rules through PostgREST; RLS remains defense in depth if a future
-- feature deliberately grants a narrow table permission.
revoke all privileges on all tables in schema public from anon, authenticated;
revoke all privileges on all sequences in schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documents',
  'documents',
  false,
  10485760,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'text/markdown',
    'text/html'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy documents_storage_insert on storage.objects for insert to authenticated
  with check (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
create policy documents_storage_select on storage.objects for select to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
create policy documents_storage_update on storage.objects for update to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  )
  with check (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
create policy documents_storage_delete on storage.objects for delete to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
