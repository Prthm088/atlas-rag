export type Profile = {
  id: string;
  email: string | null;
  display_name: string | null;
  document_count: number;
  storage_bytes: number;
  max_documents: number;
  max_storage_bytes: number;
};

export type DocumentItem = {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  status: 'awaiting_upload' | 'queued' | 'processing' | 'ready' | 'failed' | 'deleting';
  error_code: string | null;
  error_message: string | null;
  chunk_count: number;
  job_stage: string | null;
  job_progress: number | null;
  created_at: string;
  updated_at: string;
};

export type IngestionJob = {
  id: string;
  document_id: string;
  status: string;
  stage: string;
  progress: number;
  attempt_count: number;
  error_code: string | null;
  error_message: string | null;
  updated_at: string;
};

export type Conversation = {
  id: string;
  title: string;
  summary: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type Citation = {
  id: string;
  label: number;
  document_id: string;
  document_name: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string[];
  quote: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  status: string;
  content: string;
  created_at: string;
  citations: Citation[];
};

export type ApiList<T> = { items: T[]; total: number };
