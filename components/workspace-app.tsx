'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle, ArrowUp, BookOpen, Check, ChevronRight, FileText, FolderOpen,
  Loader2, LogOut, Menu, MessageSquare, MoreHorizontal, Plus, RefreshCw,
  Search, Settings, ShieldCheck, Sparkles, ThumbsDown, ThumbsUp, Trash2, Upload, X,
} from 'lucide-react';
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { AnswerContent, citationSummary } from '@/components/answer-content';
import { apiFetch, streamChat } from '@/lib/api';
import { getSupabase, isSupabaseConfigured } from '@/lib/supabase';
import type { ApiList, Citation, Conversation, DocumentItem, IngestionJob, Message, Profile } from '@/lib/types';

type View = 'chat' | 'documents' | 'settings';
type StreamState = { user: Message; assistant: Message } | null;

const acceptedTypes = '.pdf,.docx,.txt,.md,.markdown,.html,.htm';
const mimeByExtension: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.txt': 'text/plain',
  '.md': 'text/markdown',
  '.markdown': 'text/markdown',
  '.html': 'text/html',
  '.htm': 'text/html',
};

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function statusLabel(status: DocumentItem['status']): string {
  return ({ awaiting_upload: 'Awaiting upload', queued: 'Queued', processing: 'Indexing', ready: 'Ready', failed: 'Needs attention', deleting: 'Deleting' })[status];
}

function FullPageLoader({ label }: { label: string }) {
  return <main className="workspace-loader"><span className="brand-mark">A</span><Loader2 className="spin" /><p>{label}</p></main>;
}

export function WorkspaceApp() {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const messageEnd = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [authReady, setAuthReady] = useState(!isSupabaseConfigured());
  const [view, setView] = useState<View>('chat');
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [streaming, setStreaming] = useState<StreamState>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [notice, setNotice] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    const supabase = getSupabase();
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session); setAuthReady(true);
      if (!data.session) window.location.replace('/auth?next=/workspace');
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      if (!next) window.location.replace('/auth');
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const enabled = Boolean(session);
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => apiFetch<Profile>('/account/me'), enabled });
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: () => apiFetch<ApiList<DocumentItem>>('/documents'),
    enabled,
    refetchInterval: (query) => query.state.data?.items.some((doc) => ['queued', 'processing', 'deleting'].includes(doc.status)) ? 3000 : false,
  });
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: () => apiFetch<ApiList<Conversation>>('/conversations'), enabled });
  const activeConversation = selectedConversation ?? conversations.data?.items[0]?.id ?? null;
  const messages = useQuery({
    queryKey: ['messages', activeConversation],
    queryFn: () => apiFetch<ApiList<Message>>(`/conversations/${activeConversation}/messages`),
    enabled: enabled && Boolean(activeConversation),
  });

  useEffect(() => { messageEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages.data, streaming?.assistant.content]);

  const showError = (caught: unknown) => {
    const text = caught instanceof Error ? caught.message : 'Something went wrong.';
    setNotice({ tone: 'error', text });
  };

  const createConversation = useMutation({
    mutationFn: () => apiFetch<Conversation>('/conversations', { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: (item) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      setSelectedConversation(item.id); setView('chat'); setMobileMenu(false);
    },
    onError: showError,
  });

  const deleteConversation = async (id: string) => {
    if (!window.confirm('Delete this conversation and its messages?')) return;
    try {
      await apiFetch(`/conversations/${id}`, { method: 'DELETE' });
      if (selectedConversation === id) setSelectedConversation(null);
      await queryClient.invalidateQueries({ queryKey: ['conversations'] });
    } catch (error) { showError(error); }
  };

  const uploadFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploading(true); setNotice(null);
    let intent: { document_id: string; storage_bucket: string; storage_path: string; upload_token: string } | null = null;
    try {
      const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      const mimeType = mimeByExtension[extension] ?? file.type;
      intent = await apiFetch<{ document_id: string; storage_bucket: string; storage_path: string; upload_token: string }>('/documents/upload-intents', {
        method: 'POST',
        body: JSON.stringify({ filename: file.name, mime_type: mimeType, size_bytes: file.size }),
      });
      const { error } = await getSupabase().storage.from(intent.storage_bucket).upload(intent.storage_path, file, { contentType: mimeType, upsert: false });
      if (error) throw error;
      await apiFetch<IngestionJob>(`/documents/${intent.document_id}/complete`, {
        method: 'POST', body: JSON.stringify({ upload_token: intent.upload_token }),
      });
      setNotice({ tone: 'success', text: `${file.name} is being indexed. You can stay on this page or continue chatting.` });
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      await queryClient.invalidateQueries({ queryKey: ['profile'] });
    } catch (error) {
      if (intent) await apiFetch(`/documents/${intent.document_id}`, { method: 'DELETE' }).catch(() => undefined);
      showError(error);
    } finally { setUploading(false); }
  };

  const deleteDocument = async (document: DocumentItem) => {
    if (!window.confirm(`Permanently delete “${document.name}” and its index?`)) return;
    try {
      await apiFetch(`/documents/${document.id}`, { method: 'DELETE' });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['documents'] }),
        queryClient.invalidateQueries({ queryKey: ['profile'] }),
      ]);
    } catch (error) { showError(error); }
  };

  const retryDocument = async (document: DocumentItem) => {
    try {
      await apiFetch(`/documents/${document.id}/reprocess`, { method: 'POST' });
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
    } catch (error) { showError(error); }
  };

  const sendQuestion = async (event: FormEvent) => {
    event.preventDefault();
    const content = question.trim();
    if (!content || streaming) return;
    setQuestion(''); setNotice(null); setSelectedCitation(null);
    let conversationId = activeConversation;
    try {
      if (!conversationId) {
        const created = await apiFetch<Conversation>('/conversations', { method: 'POST', body: JSON.stringify({}) });
        conversationId = created.id; setSelectedConversation(created.id);
      }
      const now = new Date().toISOString();
      setStreaming({
        user: { id: `local-user-${Date.now()}`, conversation_id: conversationId, role: 'user', status: 'completed', content, created_at: now, citations: [] },
        assistant: { id: `local-assistant-${Date.now()}`, conversation_id: conversationId, role: 'assistant', status: 'streaming', content: '', created_at: now, citations: [] },
      });
      await streamChat(conversationId, content, {
        onMeta: (data) => setStreaming((current) => current ? { user: { ...current.user, id: data.user_message_id }, assistant: { ...current.assistant, id: data.assistant_message_id } } : current),
        onToken: (text) => setStreaming((current) => current ? { ...current, assistant: { ...current.assistant, content: current.assistant.content + text } } : current),
        onCitation: (data) => setStreaming((current) => current ? { ...current, assistant: { ...current.assistant, citations: [...current.assistant.citations, data as unknown as Citation] } } : current),
        onDone: (data) => setStreaming((current) => current ? { ...current, assistant: { ...current.assistant, id: data.message_id, status: 'completed', content: data.content } } : current),
      });
      setStreaming(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['messages', conversationId] }),
        queryClient.invalidateQueries({ queryKey: ['conversations'] }),
      ]);
    } catch (error) { setStreaming(null); setQuestion(content); showError(error); }
  };

  const saveFeedback = async (messageId: string, rating: -1 | 1) => {
    try {
      await apiFetch('/feedback', { method: 'POST', body: JSON.stringify({ message_id: messageId, rating }) });
      setNotice({ tone: 'success', text: 'Thanks—your feedback was saved.' });
    } catch (error) { showError(error); }
  };

  const openSource = async (citation: Citation) => {
    try {
      const result = await apiFetch<{ url: string }>(`/documents/${citation.document_id}/source-url`);
      window.open(result.url, '_blank', 'noopener,noreferrer');
    } catch (error) { showError(error); }
  };

  const signOut = async () => { await getSupabase().auth.signOut(); window.location.replace('/'); };
  const deleteAccount = async () => {
    if (deleteConfirmation !== 'DELETE MY ACCOUNT') return;
    try {
      await apiFetch('/account/me', { method: 'DELETE', body: JSON.stringify({ confirmation: deleteConfirmation }) });
      await getSupabase().auth.signOut(); window.location.replace('/');
    } catch (error) { showError(error); }
  };

  const displayedMessages = useMemo(() => {
    const base = messages.data?.items ?? [];
    return streaming ? [...base, streaming.user, streaming.assistant] : base;
  }, [messages.data, streaming]);
  const threadCitations = useMemo(() => {
    const unique = new Map<string, Citation>();
    for (const message of displayedMessages) {
      for (const citation of message.citations) unique.set(citation.id, citation);
    }
    return [...unique.values()];
  }, [displayedMessages]);

  if (!authReady) return <FullPageLoader label="Restoring your private workspace" />;
  if (!isSupabaseConfigured()) return <main className="configuration-page"><span className="brand-mark">A</span><h1>Atlas is built and awaiting configuration.</h1><p>Add the browser-safe Supabase values from <code>.env.example</code>, then reload.</p></main>;
  if (!session) return <FullPageLoader label="Redirecting to secure sign-in" />;

  return (
    <main className="workspace-shell">
      <header className="mobile-header"><button onClick={() => setMobileMenu(true)} aria-label="Open navigation"><Menu /></button><span className="brand"><span className="brand-mark">A</span>Atlas</span><button onClick={() => setView('documents')} aria-label="Open documents"><FolderOpen /></button></header>
      <aside className={`workspace-sidebar ${mobileMenu ? 'open' : ''}`}>
        <div className="sidebar-brand"><span className="brand-mark">A</span><span>Atlas</span><button onClick={() => setMobileMenu(false)} aria-label="Close navigation"><X /></button></div>
        <button className="new-chat-button" onClick={() => createConversation.mutate()} disabled={createConversation.isPending}><Plus size={16} /> New conversation</button>
        <nav className="workspace-nav" aria-label="Workspace">
          <button className={view === 'chat' ? 'active' : ''} onClick={() => { setView('chat'); setMobileMenu(false); }}><MessageSquare size={17} /> Ask Atlas</button>
          <button className={view === 'documents' ? 'active' : ''} onClick={() => { setView('documents'); setMobileMenu(false); }}><FolderOpen size={17} /> Documents <span>{documents.data?.total ?? 0}</span></button>
          <button className={view === 'settings' ? 'active' : ''} onClick={() => { setView('settings'); setMobileMenu(false); }}><Settings size={17} /> Settings</button>
        </nav>
        <div className="conversation-heading"><span>Conversations</span><Search size={14} /></div>
        <div className="conversation-list">
          {conversations.isLoading && <div className="side-skeleton" />}
          {conversations.data?.items.map((item) => <button key={item.id} className={activeConversation === item.id ? 'active' : ''} onClick={() => { setSelectedConversation(item.id); setView('chat'); setMobileMenu(false); }}><span>{item.title}</span><MoreHorizontal onClick={(event) => { event.stopPropagation(); deleteConversation(item.id); }} size={15} /></button>)}
          {!conversations.isLoading && !conversations.data?.total && <p className="sidebar-empty">Your saved conversations will appear here.</p>}
        </div>
        <div className="sidebar-account"><span className="account-avatar">{(profile.data?.display_name || profile.data?.email || 'A').slice(0, 2).toUpperCase()}</span><div><strong>{profile.data?.display_name || 'Atlas user'}</strong><small>{profile.data?.email}</small></div><button onClick={signOut} aria-label="Sign out"><LogOut size={16} /></button></div>
      </aside>
      {mobileMenu && <button className="menu-scrim" onClick={() => setMobileMenu(false)} aria-label="Close navigation" />}

      <section className="workspace-content">
        {notice && <div className={`workspace-notice ${notice.tone}`} role={notice.tone === 'error' ? 'alert' : 'status'}>{notice.tone === 'error' ? <AlertCircle size={17} /> : <Check size={17} />}<span>{notice.text}</span><button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={15} /></button></div>}
        {view === 'chat' && <>
          <header className="content-header"><div><small>Research workspace</small><h2>{conversations.data?.items.find((item) => item.id === activeConversation)?.title ?? 'Ask your documents'}</h2></div><button className="header-action" onClick={() => setView('documents')}><BookOpen size={16} /> {documents.data?.items.filter((doc) => doc.status === 'ready').length ?? 0} ready sources</button></header>
          <div className="chat-layout">
            <section className="message-column">
              {!activeConversation || (!messages.isLoading && displayedMessages.length === 0) ? <div className="chat-empty"><span className="spark-orbit"><Sparkles /></span><p className="eyebrow">Evidence first</p><h1>What do you want to understand?</h1><p>Ask across your ready documents. Atlas will answer only when it can show the evidence.</p><div className="prompt-suggestions"><button onClick={() => setQuestion('Summarize the main decisions in my documents.')}><span>01</span> Summarize the main decisions</button><button onClick={() => setQuestion('What risks or limitations are mentioned?')}><span>02</span> Find risks and limitations</button><button onClick={() => setQuestion('Which sources disagree with each other?')}><span>03</span> Compare the sources</button></div></div> : <div className="messages">{messages.isLoading && <div className="message-loading"><Loader2 className="spin" /> Loading conversation…</div>}{displayedMessages.map((message) => <article key={message.id} className={`message ${message.role}`}><div className="message-author">{message.role === 'assistant' ? <><span className="atlas-mini">A</span><strong>Atlas</strong><small>Grounded assistant</small></> : <><span className="user-mini">You</span></>}</div><div className="message-body">{message.role === 'assistant' ? <AnswerContent content={message.content} citations={message.citations} onCitation={setSelectedCitation} /> : message.content}{message.status === 'streaming' && <span className="typing-cursor" />}</div>{message.role === 'assistant' && message.status === 'completed' && <footer><span>{citationSummary(message.content, message.citations)}</span><div><button onClick={() => saveFeedback(message.id, 1)} aria-label="Helpful"><ThumbsUp size={14} /></button><button onClick={() => saveFeedback(message.id, -1)} aria-label="Not helpful"><ThumbsDown size={14} /></button></div></footer>}</article>)}<div ref={messageEnd} /></div>}
              <form className="composer" onSubmit={sendQuestion}><textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} placeholder={documents.data?.items.some((doc) => doc.status === 'ready') ? 'Ask a question about your documents…' : 'Upload a document before asking…'} rows={1} disabled={Boolean(streaming)} /><div><span>Atlas answers only from your sources</span><button disabled={!question.trim() || Boolean(streaming) || !documents.data?.items.some((doc) => doc.status === 'ready')} type="submit" aria-label="Send question">{streaming ? <Loader2 className="spin" size={18} /> : <ArrowUp size={18} />}</button></div></form>
            </section>
            <aside className={`evidence-panel ${selectedCitation ? 'selected' : ''}`}>
              <header>
                <div>
                  <small>Evidence</small>
                  <h3>{selectedCitation ? 'Source detail' : threadCitations.length ? 'Sources in this thread' : 'Citations appear here'}</h3>
                </div>
                {selectedCitation && <button onClick={() => setSelectedCitation(null)} aria-label="Close source"><X size={17} /></button>}
              </header>
              {selectedCitation ? (
                <div className="citation-detail">
                  <span className="file-badge"><FileText /></span>
                  <p className="eyebrow">Citation {selectedCitation.label}</p>
                  <h4>{selectedCitation.document_name}</h4>
                  <p className="source-location">{selectedCitation.page_start ? `Page ${selectedCitation.page_start}${selectedCitation.page_end && selectedCitation.page_end !== selectedCitation.page_start ? `–${selectedCitation.page_end}` : ''}` : 'Document section'}{selectedCitation.section_path.length ? ` · ${selectedCitation.section_path.join(' › ')}` : ''}</p>
                  <blockquote>{selectedCitation.quote}</blockquote>
                  <button className="secondary-button" onClick={() => openSource(selectedCitation)}>Open original <ChevronRight size={15} /></button>
                </div>
              ) : threadCitations.length ? (
                <div className="evidence-list">
                  <p>Select a source to inspect the exact passage used in the answer.</p>
                  {threadCitations.map((citation) => (
                    <button key={citation.id} onClick={() => setSelectedCitation(citation)} type="button">
                      <span>{citation.label}</span>
                      <div>
                        <strong>{citation.document_name}</strong>
                        <small>{citation.page_start ? `Page ${citation.page_start}` : citation.section_path.at(-1) || 'Document section'}</small>
                      </div>
                      <ChevronRight size={14} />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="evidence-empty"><ShieldCheck /><p>Every citation is checked against an authorized chunk before it is saved.</p></div>
              )}
            </aside>
          </div>
        </>}

        {view === 'documents' && <section className="library-view"><header className="content-header"><div><small>Private library</small><h2>Your documents</h2></div><button className="primary-button" onClick={() => fileInput.current?.click()} disabled={uploading || (profile.data ? profile.data.document_count >= profile.data.max_documents : false)}>{uploading ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} Upload document</button><input ref={fileInput} hidden type="file" accept={acceptedTypes} onChange={uploadFile} /></header><div className="quota-card"><div><strong>{profile.data?.document_count ?? 0} / {profile.data?.max_documents ?? 5}</strong><span>documents</span></div><div className="quota-track"><i style={{ width: `${Math.min(100, ((profile.data?.storage_bytes ?? 0) / (profile.data?.max_storage_bytes || 1)) * 100)}%` }} /></div><small>{formatBytes(profile.data?.storage_bytes ?? 0)} of {formatBytes(profile.data?.max_storage_bytes ?? 50 * 1024 * 1024)} used</small></div>{documents.isLoading ? <div className="library-loading"><Loader2 className="spin" /> Loading documents…</div> : documents.data?.items.length ? <div className="document-table"><div className="document-row table-head"><span>Name</span><span>Status</span><span>Size</span><span>Chunks</span><span /></div>{documents.data.items.map((document) => <article className="document-row" key={document.id}><div className="document-name"><span className="file-badge"><FileText /></span><div><strong>{document.name}</strong><small>Added {new Date(document.created_at).toLocaleDateString()}</small></div></div><div><span className={`status-pill ${document.status}`}>{['queued', 'processing', 'deleting'].includes(document.status) && <Loader2 className="spin" size={12} />}{statusLabel(document.status)}</span>{document.job_progress !== null && ['queued', 'processing'].includes(document.status) && <span className="job-progress"><i style={{ width: `${document.job_progress}%` }} />{document.job_stage} · {document.job_progress}%</span>}{document.error_message && <small className="document-error">{document.error_message}</small>}</div><span>{formatBytes(document.size_bytes)}</span><span>{document.chunk_count || '—'}</span><div className="row-actions">{['failed', 'ready'].includes(document.status) && <button onClick={() => retryDocument(document)} aria-label={document.status === 'ready' ? 'Re-index' : 'Retry'} title={document.status === 'ready' ? 'Re-index document' : 'Retry processing'}><RefreshCw size={16} /></button>}<button onClick={() => deleteDocument(document)} aria-label="Delete"><Trash2 size={16} /></button></div></article>)}</div> : <div className="library-empty"><span className="empty-folder"><FolderOpen /></span><h3>Build your private library</h3><p>Upload a text PDF, DOCX, TXT, Markdown, or HTML file. Scanned PDFs require OCR and are not supported on the free deployment.</p><button className="primary-button" onClick={() => fileInput.current?.click()}><Plus size={16} /> Add your first document</button></div>}</section>}

        {view === 'settings' && <section className="settings-view"><header className="content-header"><div><small>Account</small><h2>Settings & privacy</h2></div></header><div className="settings-grid"><article><h3>Account details</h3><p>Your identity is managed securely by Supabase Auth.</p><dl><div><dt>Email</dt><dd>{profile.data?.email}</dd></div><div><dt>User ID</dt><dd className="mono">{profile.data?.id}</dd></div></dl><button className="secondary-button" onClick={signOut}><LogOut size={15} /> Sign out</button></article><article><h3>Privacy boundary</h3><p>Documents, vectors, conversations, citations, and feedback are owned by your account. Row-level policies prevent access by other users.</p><div className="privacy-banner"><ShieldCheck /><span>Do not upload confidential information. The free Gemini tier may use content to improve Google products.</span></div></article><article className="danger-zone"><h3>Delete account</h3><p>This permanently removes your account, documents, vectors, conversations, and stored files. It cannot be undone.</p><label>Type <strong>DELETE MY ACCOUNT</strong><input value={deleteConfirmation} onChange={(e) => setDeleteConfirmation(e.target.value)} /></label><button disabled={deleteConfirmation !== 'DELETE MY ACCOUNT'} onClick={deleteAccount}><Trash2 size={15} /> Permanently delete everything</button></article></div></section>}
      </section>
    </main>
  );
}
