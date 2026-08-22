'use client';

import { getSupabase } from './supabase';

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public details?: Record<string, unknown> | null,
  ) {
    super(message);
  }
}

type ErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown> | null;
  };
};

async function accessToken(): Promise<string> {
  const { data, error } = await getSupabase().auth.getSession();
  if (error || !data.session?.access_token) throw new ApiError('authentication_required', 'Please sign in again.', 401);
  return data.session.access_token;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await accessToken();
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 65_000);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
    if (response.status === 204) return undefined as T;
    const body = await response.json().catch(() => ({})) as ErrorPayload;
    if (!response.ok) {
      const error = body?.error ?? {};
      throw new ApiError(error.code ?? 'request_failed', error.message ?? 'The request failed.', response.status, error.details);
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('service_warming', 'The service is taking longer than expected to wake up. Please retry.', 503);
    }
    throw new ApiError('network_error', 'The service is unreachable. It may be waking from its free-tier sleep.', 503);
  } finally {
    window.clearTimeout(timeout);
  }
}

type StreamHandlers = {
  onMeta?: (data: Record<string, string>) => void;
  onToken: (text: string) => void;
  onCitation: (citation: Record<string, unknown>) => void;
  onDone: (data: { message_id: string; content: string; latency_ms: number }) => void;
};

export async function streamChat(
  conversationId: string,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = await accessToken();
  const response = await fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ conversation_id: conversationId, content }),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({})) as ErrorPayload;
    throw new ApiError(body?.error?.code ?? 'chat_failed', body?.error?.message ?? 'The answer could not start.', response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() ?? '';
    for (const frame of frames) {
      let event = 'message';
      const dataLines: string[] = [];
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      const data = JSON.parse(dataLines.join('\n'));
      if (event === 'meta') handlers.onMeta?.(data);
      else if (event === 'token') handlers.onToken(data.text ?? '');
      else if (event === 'citation') handlers.onCitation(data);
      else if (event === 'done') handlers.onDone(data);
      else if (event === 'error') throw new ApiError(data.code ?? 'chat_failed', data.message ?? 'The answer failed.', 503);
    }
    if (done) break;
  }
}
